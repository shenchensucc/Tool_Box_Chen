"""
Inspection Report PDF Parser

Extracts Circuit ID, CML ID, thickness readings, and measurement date from UT inspection report PDFs.
Supports Acuren-style reports with multiple table formats:
- Format A: SECTION/DIAM columns, 8"/6" -> CML base, row num -> zone (e.g. 1.01-1)
- Format B: CIRCUIT CML ZONE DIAM. table, CML section headers, multiple readings per zone -> min
Circuit format: NN-NNNXX (e.g. 52-021K); "1-2", "2-3" are breakdown drawing numbers, not circuit.
"""

import base64
import functools
import hashlib
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Tuple

import pdfplumber
import pymupdf

_logger = logging.getLogger(__name__)
_EASYOCR_READER = None
_EASYOCR_INIT_FAILED = False
_PADDLEOCR_READER = None
_PADDLEOCR_INIT_FAILED = False

# Protect singleton initialization: two threads must not race to create the same reader.
_EASYOCR_INIT_LOCK = threading.Lock()
_PADDLEOCR_INIT_LOCK = threading.Lock()

# In-process cache for OCR results: {(pdf_path_str, mtime_ns) -> List[ExtractedReading]}
# Avoids re-running expensive EasyOCR on a file that hasn't changed.
_STRUCT_OCR_CACHE: dict = {}
_STRUCT_OCR_CACHE_LOCK = threading.Lock()

# Limit simultaneous OCR (CPU-bound) threads to 1 so they don't thrash each other.
# pdfplumber threads are not gated by this semaphore and run truly in parallel.
_OCR_SEMAPHORE = threading.Semaphore(1)


@dataclass
class ExtractedReading:
    """Single extracted record from a PDF report."""

    circuit_id: str
    cml_id: str
    measurement_date: str  # YYYY-MM-DD
    min_reading: float  # Used for single reading; same as first of all_readings when row-based
    all_readings: List[float] = field(default_factory=list)
    source_file: str = ""
    extraction_method: str = "pdfplumber"  # "pdfplumber" or "ocr"
    source_page: Optional[int] = None  # 1-based page index
    table_bbox: Optional[Tuple[float, float, float, float]] = None
    table_image_id: str = ""
    table_image_base64: str = ""


def _parse_date(date_str: str) -> Optional[str]:
    """Parse date string to YYYY-MM-DD. Handles formats like 'February 23, 2026', '02/23/2026', 'FEB 23 2026'."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()

    # MM/DD/YYYY or MM-DD-YYYY
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", date_str)
    if m:
        mth, day, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mth <= 12 and 1 <= day <= 31:
            return f"{yr}-{mth:02d}-{day:02d}"

    # Month DD, YYYY (e.g. February 23, 2026)
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})",
        date_str,
        re.I,
    )
    if m:
        mth = months.get(m.group(1).lower()[:3], 0)
        if mth:
            return f"{m.group(3)}-{mth:02d}-{int(m.group(2)):02d}"

    # Month DD YYYY (e.g. FEB 23 2026)
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})\s+(\d{4})", date_str, re.I)
    if m:
        mth = months.get(m.group(1).lower(), 0)
        if mth:
            return f"{m.group(3)}-{mth:02d}-{int(m.group(2)):02d}"

    return None


def _extract_date_from_text(text: str) -> Optional[str]:
    """Extract measurement date from report text (header area)."""
    # DATE: February 23, 2026
    m = re.search(r"DATE\s*:\s*([^\n]+)", text, re.I)
    if m:
        parsed = _parse_date(m.group(1))
        if parsed:
            return parsed

    # DATE (MM/DD/YYYY): 02/23/2026
    m = re.search(r"DATE\s*\([^)]*\)\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
    if m:
        return _parse_date(m.group(1))

    # FEB 23 2026
    m = re.search(r"DATE\s*:\s*([A-Z]{3}\s+\d{1,2}\s+\d{4})", text, re.I)
    if m:
        return _parse_date(m.group(1))

    # Filename: ..._02.23.2026.pdf
    return None


def _extract_circuit_from_text(text: str) -> Optional[str]:
    """Extract circuit ID from report text (e.g. 'Circuit: 52-021K 1-2' or 'Circuit: 52-010B 2-3')."""
    m = re.search(r"Circuit\s*:\s*([^\n]+)", text, re.I)
    if m:
        return m.group(1).strip()
    return None


def _extract_circuit_base(circuit_raw: str) -> str:
    """
    Extract base circuit ID. Format NN-NNNXX (e.g. 52-021K, 57-008U).
    Suffixes like "1-2", "2-3", "1,3-3" are breakdown drawing numbers, not part of circuit.
    """
    if not circuit_raw:
        return "Unknown"
    s = circuit_raw.strip()
    # "52-021K 1-2" -> "52-021K", "57-008U 1,3-3" -> "57-008U"
    m = re.match(r"^(\d+-\w+)(?:\s+[\d,]*-[\d]+)?", s)
    if m:
        return m.group(1).strip()
    return s


def _extract_cml_ids_from_filename(filename: str) -> List[str]:
    """Extract CML bases from filename (e.g. '1.29, 1.37' or 'CML 1.52' or '52-001G 1-1 2.32 UT-...')."""
    cml_ids = []
    # Match "CML 1.52,1.29&4.09" or "1.29, 1.37" before UT- or _
    m = re.search(r"CML\s*([\d.,\s&]+)", filename, re.I)
    if m:
        raw = m.group(1)
    else:
        # "52-012B 2-3 1.29, 1.37 UT-ROBJOS" or "52-001G 1-1 2.32 UT-ROBJOS" or "57-034C 4-7 2.37UT-..."
        m = re.search(r"\d+-\w+\s+[\d,]*-[\d]+\s+([\d.]+)\s*UT", filename, re.I)
        if m:
            raw = m.group(1)
        else:
            m = re.search(r"\d+-\w+\s+[\d,]*-[\d]+\s+([\d.,\s&]+)", filename)
            if m:
                raw = m.group(1)
            else:
                return cml_ids
    for part in re.split(r"[\s,&]+", raw):
        part = part.strip()
        if part and re.match(r"^\d+(\.\d+)?$", part):
            cml_ids.append(part)
    return cml_ids


def _extract_cml_ids_from_text(text: str) -> List[str]:
    """Extract CML IDs from report text (e.g. 'CML 1.01 & 1.05' or 'CML:1.37, 1.29' or 'ITEM(S) EXAMINED: CML 1.01 & 1.05')."""
    cml_ids = []

    # CML 1.01 & 1.05 or CML 1.01 & 1.05
    m = re.search(r"CML\s*:?\s*([\d.\s,&]+)", text, re.I)
    if m:
        raw = m.group(1)
        for part in re.split(r"[\s,&]+", raw):
            part = part.strip()
            if part and re.match(r"^\d+(\.\d+)?$", part):
                cml_ids.append(part)

    # ITEM(S) EXAMINED: CML 1.01 & 1.05
    if not cml_ids:
        m = re.search(r"ITEM\(S\)\s*EXAMINED\s*:\s*CML\s*([\d.\s,&]+)", text, re.I)
        if m:
            raw = m.group(1)
            for part in re.split(r"[\s,&]+", raw):
                part = part.strip()
                if part and re.match(r"^\d+(\.\d+)?$", part):
                    cml_ids.append(part)

    return cml_ids


def _is_date_or_phone_false_positive(v: float) -> bool:
    """
    Exclude values that are likely date fragments or phone/fax OCR noise.
    - 2.2026 from 02.2026 (Feb 2026), 1.2026, etc.
    - 0.9061 from Fax: 780.79 0.9061 (phone number fragment)
    """
    # Date-like: X.20XX where 20XX is year (2020-2035)
    if 1.0 <= v <= 12.5:
        frac = v - int(v)
        if 0.2015 <= frac <= 0.2040:  # .2016 to .2039
            return True
    # Phone/fax fragment: 0.9061 from 780.790.1776 OCR; 0.90-0.92 with 4 decimals often noise
    if 0.904 <= v <= 0.908:  # narrow band for 0.9061
        return True
    return False


def _extract_numeric_readings(text: str) -> List[float]:
    """
    Extract thickness readings from text. Handles normal (0.285) and fragmented PDF (0 . 2 8 5).
    Excludes false positives from phone numbers (e.g. 0.79 in 780.790.1776) via (?<![\\d.]) lookbehind.
    Excludes date fragments (2.2026 from 02.2026) and fax fragments (0.9061 from 780.79 0.9061).
    """
    # Pre-remove phone/fax patterns: "780.79 0.9061" (Fax) - avoid extracting 0.9061
    text = re.sub(r"\d{3}\.\d{2}\s+0\.\d{3,4}\b", " ", text)

    readings = []
    # Normal format: 0.285, 0.380 - not part of longer number (avoid 780.790)
    for m in re.finditer(r"(?<!\d)(?<!\.)0\.\d{2,4}(?!\d)(?!\.\d)", text):
        try:
            v = float(m.group(0))
            if 0.05 <= v <= 3.0 and not _is_date_or_phone_false_positive(v):
                readings.append(v)
        except ValueError:
            pass
    # Fragmented PDF: collapse spaces and try again (0 . 2 8 5 -> 0.285)
    if not readings:
        collapsed = re.sub(r"\s+", "", text)
        for m in re.finditer(r"(?<!\d)0\.\d{2,4}(?!\d)", collapsed):
            try:
                v = float(m.group(0))
                if 0.05 <= v <= 3.0 and not _is_date_or_phone_false_positive(v):
                    readings.append(v)
            except ValueError:
                pass
    # Fallback: X.XXX (exclude 1.0, 2.0 calibration refs, date fragments)
    if not readings:
        for m in re.finditer(r"(?<!\d)(\d+\.\d{3,4})(?!\d)", text):
            try:
                v = float(m.group(1))
                if (
                    0.05 <= v <= 3.0
                    and not (0.99 <= v <= 1.01 or 1.99 <= v <= 2.01)
                    and not _is_date_or_phone_false_positive(v)
                ):
                    readings.append(v)
            except ValueError:
                pass
    return readings


def _dedupe_by_cml_keep_min(results: List[ExtractedReading]) -> List[ExtractedReading]:
    """
    Dedupe by (circuit_id, cml_id). Rule: keep the row with minimum reading (critical for thickness).
    No value-based filtering - 0.79 could be valid. Duplicates indicate parsing read same row twice
    or from overlapping table regions.
    """
    by_cml: dict = {}
    for r in results:
        key = (r.circuit_id, r.cml_id)
        if key not in by_cml:
            by_cml[key] = r
        else:
            existing = by_cml[key]
            if r.min_reading < existing.min_reading:
                by_cml[key] = r
    return list(by_cml.values())


def _validate_and_dedupe_before_export(results: List[ExtractedReading]) -> List[ExtractedReading]:
    """
    Internal validation before returning to user. Dedupe (idempotent) and sort by CML for consistent output.
    """
    deduped = _dedupe_by_cml_keep_min(results)
    return sorted(deduped, key=lambda r: (r.circuit_id, r.cml_id))


# Page filtering: prefer "UT REPORT - TEE/ELBOW/CONNECTIONS" summary tables, skip "UT Grid" detailed readings
# Summary table has final thickness readings; grid pages (6"x6", 3"x3", 1"x1", 2"x2") are detailed scans - do not read
# Fragmented PDFs may have "U T R E P O R T - T E E" (spaces between letters)
_UT_REPORT_SUMMARY = re.compile(
    r"(?:U\s*T\s*R\s*E\s*P\s*O\s*R\s*T|UT\s+REPORT)\s*[-–]\s*"
    r"(?:T\s*E\s*E|TEE|E\s*L\s*B\s*O\s*W|ELBOW|CONNECTIONS?|PIPE|REDUCER|CAP|WELD|STRAIGHT)",
    re.I,
)
# Skip pages with detailed UT Grid (confusing intermediate readings; final readings are in UT REPORT summary)
# Grid cell sizes: 1"x1", 2"x2", 1"X1", 2"X2", etc.
_UT_GRID_SECTION = re.compile(
    r"UT\s+Grid|GRID\s+Reading|Grid\s+Readings|UT\s+Grid\s+|"
    r"GRID\s+STARTS|NOTE:.*GRID\s+STARTS|"
    r'[12]\s*["\']?\s*[xX]\s*[12]\s*["\']?',  # 1"x1" or 2"x2" grid cell size
    re.I,
)


def _should_process_page(page_text: str, summary_page_indices: Optional[List[int]] = None, page_idx: int = 0) -> bool:
    """
    True if this page should be processed for extraction.
    - If summary_page_indices: only process those pages (UT REPORT - TEE/ELBOW etc).
    - Skip pages with UT Grid section (detailed readings, not final summary).
    """
    if summary_page_indices is not None and page_idx not in summary_page_indices:
        return False
    if _UT_GRID_SECTION.search(page_text):
        return False
    return True


@functools.lru_cache(maxsize=32)
def _get_summary_page_indices(pdf_path: Path) -> Optional[List[int]]:
    """
    If any page has "UT REPORT - TEE" or "UT REPORT - ELBOW" etc, return those page indices.
    Fragmented PDFs may have "U T R" and "R T -" (from "UT REPORT -") on the summary page.
    Otherwise return None (process all pages).
    """
    summary_pages = []
    # Fragmented: "U T R" (start of UT REPORT) + "R T" then "-" (hyphen may be on next line)
    _FRAGMENTED_UT_REPORT = re.compile(r"U\s*T\s*R", re.I)
    _FRAGMENTED_REPORT_DASH = re.compile(r"R\s*T\s*[-–]", re.I)
    # "R T" then hyphen within 80 chars (fragmented across lines)
    _FRAGMENTED_REPORT_DASH_FLEX = re.compile(r"R\s*T[\s\S]{0,80}[-–]", re.I)

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if _UT_REPORT_SUMMARY.search(text):
                summary_pages.append(i)
            elif _FRAGMENTED_UT_REPORT.search(text) and (
                _FRAGMENTED_REPORT_DASH.search(text) or _FRAGMENTED_REPORT_DASH_FLEX.search(text)
            ):
                summary_pages.append(i)
    return summary_pages if summary_pages else None


def _iter_tables_with_bbox(page):
    """
    Yield tuples of (rows, bbox) for a pdfplumber page.
    BBox format is (x0, top, x1, bottom) in PDF points.
    """
    settings = {"vertical_strategy": "text", "horizontal_strategy": "text"}
    try:
        for table in page.find_tables(table_settings=settings):
            rows = table.extract() or []
            bbox = None
            if getattr(table, "bbox", None):
                try:
                    bbox = tuple(float(v) for v in table.bbox)
                except Exception:
                    bbox = None
            yield rows, bbox
        return
    except Exception:
        pass

    for rows in page.extract_tables(settings) or []:
        yield rows, None


def _attach_table_images(pdf_path: Path, results: List[ExtractedReading]) -> List[ExtractedReading]:
    """
    Render table crops as base64 PNG for extracted rows that include page+bbox context.
    Reuses one image per unique (page, bbox) to support multi-PDF and multi-table validation.
    """
    indexed = {}
    for r in results:
        if r.source_page and r.table_bbox:
            key = (int(r.source_page), tuple(round(v, 2) for v in r.table_bbox))
            indexed[key] = r.table_bbox
    if not indexed:
        return results

    evidence_by_key = {}
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return results

    try:
        for (page_number, rounded_bbox), raw_bbox in indexed.items():
            page_idx = page_number - 1
            if page_idx < 0 or page_idx >= len(doc):
                continue

            page = doc[page_idx]
            x0, y0, x1, y1 = raw_bbox
            margin = 8
            clip = pymupdf.Rect(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
            clip &= page.rect
            if clip.is_empty:
                continue

            try:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), clip=clip, alpha=False)
                png_bytes = pix.tobytes(output="png")
                table_id_seed = f"{page_number}:{rounded_bbox}"
                table_id = f"tbl_{hashlib.md5(table_id_seed.encode('utf-8')).hexdigest()[:10]}"
                evidence_by_key[(page_number, rounded_bbox)] = (
                    table_id,
                    base64.b64encode(png_bytes).decode("ascii"),
                )
            except Exception:
                continue
    finally:
        doc.close()

    for r in results:
        if not (r.source_page and r.table_bbox):
            continue
        key = (int(r.source_page), tuple(round(v, 2) for v in r.table_bbox))
        if key in evidence_by_key:
            r.table_image_id, r.table_image_base64 = evidence_by_key[key]
    return results


def _finalize_results(pdf_path: Path, source_filename: str, results: List[ExtractedReading]) -> List[ExtractedReading]:
    """Attach source filename and optional table images before returning results."""
    for r in results:
        if not r.source_file:
            r.source_file = source_filename
    return _attach_table_images(pdf_path, results)


def _parse_ut_report_summary_table(
    pdf_path: Path, circuit_base: str, cml_bases: List[str], date_str: str
) -> List[ExtractedReading]:
    """
    Parse UT REPORT - TEE/ELBOW summary table: SECTION column (1-9), DIAM, reading per row.
    Handles fragmented cells like ['0', '.2', '9 7'] -> 0.297. Skips N/A FLANGE rows.
    """
    results = []
    cml_base = cml_bases[0] if cml_bases else "1.01"
    summary_page_indices = _get_summary_page_indices(pdf_path)
    if not summary_page_indices:
        return results

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx in summary_page_indices:
            if page_idx >= len(pdf.pages):
                continue
            page = pdf.pages[page_idx]
            for table, table_bbox in _iter_tables_with_bbox(page):
                for row in table:
                    if not row:
                        continue
                    cells = [str(c or "").strip() for c in row]
                    row_text = " ".join(cells)
                    collapsed = re.sub(r"\s+", "", row_text)

                    # Skip N/A FLANGE rows
                    if re.search(r"N/?A|FLANGE", row_text, re.I):
                        continue

                    # Section/zone number (1-9) - from SECTION column (before DIAM column)
                    # Find DIAM column (4", 6", 8", 10", etc.), then section is 2-3 cols to its left
                    diam_col = None
                    for j, c in enumerate(cells):
                        c_stripped = (c or "").strip()
                        if (
                            re.search(r'[468]\s*["\']', c_stripped)
                            or re.search(r'1\s*0\s*["\']', c_stripped)  # 10"
                            or c_stripped in ('4"', '6"', '8"', '10"', "4'", "6'", "8'", "10'")
                        ):
                            diam_col = j
                            break
                    section_num = None
                    if diam_col is not None:
                        for j in range(diam_col - 1, max(-1, diam_col - 4), -1):
                            if j >= 0 and j < len(cells):
                                c = cells[j]
                                if re.match(r"^[1-9]\d*$", c) and c in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                                    section_num = c
                                    break
                    if section_num is None:
                        # Fallback: first standalone 1-9, skip cells with " or '
                        for c in cells[1:]:
                            if re.match(r"^[1-9]\d*$", c) and c in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                                if '"' not in c and "'" not in c:
                                    section_num = c
                                    break

                    # Reading: 0.XXX (normal or fragmented "0" ".2" "9 7")
                    reading = None
                    for m in re.finditer(r"0\.\d{2,4}", collapsed):
                        try:
                            v = float(m.group(0))
                            if 0.05 <= v <= 3.0:
                                reading = v
                                break
                        except ValueError:
                            pass
                    if reading is None:
                        # Fragmented: "0" ".2" "9 7" or "0 .2 4 7"
                        for m in re.finditer(r"0\s*\.\s*(\d)\s*(\d)\s*(\d)(?:\s*(\d))?", row_text):
                            try:
                                s = f"0.{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4) or ''}"
                                v = float(s)
                                if 0.05 <= v <= 3.0:
                                    reading = v
                                    break
                            except (ValueError, IndexError):
                                pass

                    if section_num and reading is not None:
                        cml_id = f"{cml_base}-{section_num}"
                        results.append(
                            ExtractedReading(
                                circuit_id=circuit_base,
                                cml_id=cml_id,
                                measurement_date=date_str,
                                min_reading=reading,
                                all_readings=[reading],
                                extraction_method="pdfplumber",
                                source_page=page_idx + 1,
                                table_bbox=table_bbox,
                            )
                        )
    return results


def _parse_acuren_results_table(
    pdf_path: Path, circuit_base: str, cml_bases: List[str], date_str: str
) -> List[ExtractedReading]:
    """
    Parse Acuren-style results table: SECTION/DIAM columns, row num, 8"/6" -> CML base.
    For single CML, any diameter maps to that CML. Returns one ExtractedReading per row.
    Prefers pages with "UT REPORT - TEE/ELBOW"; skips "UT Grid" detailed readings.
    """
    results = []
    diam_to_cml = {"8": cml_bases[0] if len(cml_bases) > 0 else "1.01", "6": cml_bases[1] if len(cml_bases) > 1 else "1.05"}
    single_cml = cml_bases[0] if len(cml_bases) == 1 else None

    summary_page_indices = _get_summary_page_indices(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        # Iterate last-to-first: CML summary tables are typically near the end of the report.
        for page_idx, page in reversed(list(enumerate(pdf.pages))):
            page_text = page.extract_text() or ""
            if not _should_process_page(page_text, summary_page_indices, page_idx):
                continue
            for table, table_bbox in _iter_tables_with_bbox(page):
                for row in table:
                    if not row:
                        continue
                    row_text = " ".join(str(c or "").strip() for c in row)
                    collapsed = re.sub(r"\s+", "", row_text)

                    # Skip header rows
                    if re.search(r"CIRCUIT|CML|SECTION|DIAM", row_text, re.I):
                        continue

                    # Diameter: 8", 6", or other. For single CML, optional (some tables have no diameter column).
                    diam = None
                    for d in ["8", "6", "12", "10", "4", "16", "30"]:
                        if re.search(r"(?:^|[^\d.])" + d + r'\s*["\']', row_text) or (d + '"' in collapsed or d + "'" in row_text):
                            diam = d
                            break

                    # Row/zone number (1-9). For multi-CML: cell before diameter. For single CML: any zone cell.
                    # Zone 4 can appear as "4"" (combined with 4" diameter) - must extract from that cell.
                    row_num = None
                    cells = [str(c or "").strip() for c in row]
                    if single_cml:
                        for c in cells:
                            if c in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                                row_num = c
                                break
                            # Zone+diameter combined: "4"" or "4 '" (zone 4, 4" pipe)
                            m = re.match(r"^([1-9]\d*)\s*['\"]", c)
                            if m:
                                row_num = m.group(1)
                                break
                    else:
                        for i, c in enumerate(cells):
                            if c in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                                for j in range(i + 1, len(cells)):
                                    nc = cells[j]
                                    if not nc:
                                        continue
                                    if any(nc.startswith(x) and '"' in nc for x in ("8", "6", "4", "10", "12", "16", "30")):
                                        row_num = c
                                        break
                                    break
                                if row_num:
                                    break

                    # First thickness (column A): 0.XXX
                    reading = None
                    for m in re.finditer(r"0\.\d{2,4}", collapsed):
                        v = float(m.group(0))
                        if 0.05 <= v <= 3.0:
                            reading = v
                            break
                    if reading is None:
                        for m in re.finditer(r"0\s*\.\s*(\d)\s*(\d)\s*(\d)(?:\s*(\d))?", row_text):
                            try:
                                s = f"0.{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4) or ''}"
                                v = float(s)
                                if 0.05 <= v <= 3.0:
                                    reading = v
                                    break
                            except (ValueError, IndexError):
                                pass

                    # For single CML: row_num + reading sufficient (diam optional). For multi-CML: need diam.
                    if row_num and reading is not None:
                        if not single_cml and not diam:
                            pass  # multi-CML requires diameter
                        else:
                            cml_base = diam_to_cml.get(diam) if diam else single_cml
                            if cml_base:
                                cml_id = f"{cml_base}-{row_num}"
                                results.append(
                                    ExtractedReading(
                                        circuit_id=circuit_base,
                                        cml_id=cml_id,
                                        measurement_date=date_str,
                                        min_reading=reading,
                                        all_readings=[reading],
                                        extraction_method="pdfplumber",
                                        source_page=page_idx + 1,
                                        table_bbox=table_bbox,
                                    )
                                )
    return results


def _parse_single_cml_permissive(
    pdf_path: Path, circuit_base: str, cml_base: str, date_str: str
) -> List[ExtractedReading]:
    """
    Fallback for single-CML: extract (zone, reading) from table rows with minimal structure.
    Prefers pages with "UT REPORT - TEE/ELBOW"; skips "UT Grid" detailed readings.
    """
    results = []
    summary_page_indices = _get_summary_page_indices(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        # Iterate last-to-first: CML summary tables are typically near the end of the report.
        for page_idx, page in reversed(list(enumerate(pdf.pages))):
            page_text = page.extract_text() or ""
            if not _should_process_page(page_text, summary_page_indices, page_idx):
                continue
            for table, table_bbox in _iter_tables_with_bbox(page):
                for row in table:
                    if not row:
                        continue
                    cells = [str(c or "").strip() for c in row]
                    row_text = " ".join(cells)
                    collapsed = re.sub(r"\s+", "", row_text)

                    # Skip header-like rows
                    if re.search(r"CIRCUIT|CML|SECTION|DIAM|ZONE|NORTH|SOUTH", row_text, re.I):
                        continue

                    # Find zone numbers (standalone 1-9, "Zone 1", "4"" for zone+diameter, etc.)
                    zones = []
                    readings = []
                    for c in cells:
                        if c in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                            zones.append(c)
                        else:
                            m = re.match(r"^(?:Zone|Loc|Location)?\s*([1-9]\d*)\s*\.?$", c, re.I)
                            if m:
                                zones.append(m.group(1))
                            else:
                                # Zone+diameter combined: "4"" or "4 '" (zone 4, 4" pipe)
                                m = re.match(r"^([1-9]\d*)\s*['\"]", c)
                                if m:
                                    zones.append(m.group(1))
                    for m in re.finditer(r"0\.\d{2,4}", collapsed):
                        try:
                            v = float(m.group(0))
                            if 0.05 <= v <= 3.0:
                                readings.append(v)
                        except ValueError:
                            pass
                    if not readings:
                        for m in re.finditer(r"0\s*\.\s*(\d)\s*(\d)\s*(\d)(?:\s*(\d))?", row_text):
                            try:
                                s = f"0.{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4) or ''}"
                                v = float(s)
                                if 0.05 <= v <= 3.0:
                                    readings.append(v)
                                    break
                            except (ValueError, IndexError):
                                pass

                    # One zone + one reading per row -> one result
                    if zones and readings:
                        zone_num = zones[0]
                        reading = min(readings)  # if multiple, take min
                        results.append(
                            ExtractedReading(
                                circuit_id=circuit_base,
                                cml_id=f"{cml_base}-{zone_num}",
                                measurement_date=date_str,
                                min_reading=reading,
                                all_readings=[reading],
                                extraction_method="pdfplumber",
                                source_page=page_idx + 1,
                                table_bbox=table_bbox,
                            )
                        )
    return results


def _parse_generic_zone_table(
    pdf_path: Path, circuit_base: str, cml_bases: List[str], date_str: str
) -> List[ExtractedReading]:
    """
    Parse generic zone table: CIRCUIT CML ZONE DIAM. columns, CML section headers.
    Prefers pages with "UT REPORT - TEE/ELBOW"; skips "UT Grid" detailed readings.
    """
    results = []
    current_cml_base = None
    cml_idx = 0
    diam_to_cml: dict = {}

    summary_page_indices = _get_summary_page_indices(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if not _should_process_page(page_text, summary_page_indices, page_idx):
                continue
            # Update current CML from page text when page has single CML (e.g. page 5 with "CML 4.09")
            page_cmls = [
                m.group(1)
                for m in re.finditer(r"(?:^|\n)\s*CML\s+(\d+\.\d+)(?:\s*$|\s*\n)", page_text, re.I)
                if m.group(1) in cml_bases
            ]
            if len(page_cmls) == 1:
                current_cml_base = page_cmls[0]
            for table, table_bbox in _iter_tables_with_bbox(page):
                for row in table:
                    if not row:
                        continue
                    row_text = " ".join(str(c or "").strip() for c in row)
                    cells = [str(c or "").strip() for c in row]
                    collapsed = re.sub(r"\s+", "", row_text)

                    # Check for CML section header (cell contains "1.52" or "CML 1.52")
                    for c in cells:
                        m = re.search(r"(?:CML\s+)?(\d+\.\d+)\s*$", c)
                        if m:
                            base = m.group(1)
                            if base in cml_bases:
                                current_cml_base = base
                                break

                    # Skip header rows (but not zone rows starting with 1-9)
                    if re.search(r"CIRCUIT|CML\s+[A-Z]|ZONE|DIAM|SECTION|NORTH|SOUTH", row_text, re.I):
                        if not re.match(r"^\s*[1-9]\d*\s+", row_text):
                            continue

                    # Zone number (1-9 or more). Also "4"" when zone+diameter combined.
                    zone_num = None
                    for c in cells:
                        if re.match(r"^[1-9]\d*$", c):
                            zone_num = c
                            break
                        m = re.match(r"^([1-9]\d*)\s*['\"]", c)
                        if m:
                            zone_num = m.group(1)
                            break

                    # Diameter: 8", 6", 16", 30" etc
                    diam = None
                    for d in ["16", "30", "8", "6", "12", "10", "4"]:
                        if re.search(r"(?:^|[^\d.])" + d + r'\s*["\']', row_text) or (
                            d + '"' in collapsed or d + "'" in row_text
                        ):
                            diam = d
                            break

                    # All thickness readings in row (multiple per zone -> take min)
                    # Use (?!\d) to avoid "0.3574" from "0.357" + "40F" (temp suffix)
                    readings_in_row = []
                    for m in re.finditer(r"0\.\d{2,3}(?!\d)", collapsed):
                        try:
                            v = float(m.group(0))
                            if 0.05 <= v <= 3.0:
                                readings_in_row.append(v)
                        except ValueError:
                            pass
                    if not readings_in_row:
                        for m in re.finditer(r"0\.\d{2,4}", collapsed):
                            try:
                                v = float(m.group(0))
                                if 0.05 <= v <= 3.0:
                                    # Round to 3 decimals to fix 0.3574 from "0.357"+"40F"
                                    v = round(v, 3)
                                    readings_in_row.append(v)
                            except ValueError:
                                pass
                    for m in re.finditer(r"0\s*\.\s*(\d)\s*(\d)\s*(\d)(?:\s*(\d))?", row_text):
                        try:
                            s = f"0.{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4) or ''}"
                            v = float(s)
                            if 0.05 <= v <= 3.0:
                                readings_in_row.append(v)
                        except (ValueError, IndexError):
                            pass

                    if re.search(r"N/A|FLANGE", row_text, re.I) and not readings_in_row:
                        continue

                    # Require diameter when we have multiple CMLs (avoids noise from other tables)
                    if len(cml_bases) > 1 and not diam:
                        continue

                    if zone_num and readings_in_row:
                        min_reading = min(readings_in_row)
                        # When we have diam, use diam_to_cml (heuristic) - ignore page header order
                        cml_base = None
                        if diam and cml_bases:
                            if diam not in diam_to_cml:
                                # Prefer heuristic over page header when we have 16/30/8/6 (multi-section page)
                                if diam in ("16", "12") and "1.52" in cml_bases:
                                    diam_to_cml[diam] = "1.52"
                                elif diam == "30" and "1.29" in cml_bases:
                                    diam_to_cml[diam] = "1.29"
                                elif diam in ("8", "6") and "4.09" in cml_bases:
                                    diam_to_cml[diam] = "4.09"
                                elif current_cml_base and len(page_cmls) == 1:
                                    diam_to_cml[diam] = current_cml_base
                                else:
                                    diam_to_cml[diam] = cml_bases[len(diam_to_cml) % len(cml_bases)]
                            cml_base = diam_to_cml[diam]
                        if not cml_base:
                            # No diam: use row CML or current section header
                            for c in cells:
                                m = re.search(r"(\d+\.\d+)\s*$", c)
                                if m and m.group(1) in cml_bases:
                                    cml_base = m.group(1)
                                    break
                        if not cml_base:
                            cml_base = current_cml_base
                        if not cml_base and cml_bases:
                            cml_base = cml_bases[cml_idx % len(cml_bases)]
                            cml_idx += 1
                        if cml_base:
                            cml_id = f"{cml_base}-{zone_num}"
                            results.append(
                                ExtractedReading(
                                    circuit_id=circuit_base,
                                    cml_id=cml_id,
                                    measurement_date=date_str,
                                    min_reading=min_reading,
                                    all_readings=readings_in_row,
                                    extraction_method="pdfplumber",
                                    source_page=page_idx + 1,
                                    table_bbox=table_bbox,
                                )
                            )

    return results


def _extract_readings_from_tables(pdf_path: Path) -> List[float]:
    """Extract numeric readings from PDF tables using pdfplumber. Iterates last-to-first
    so CML summary tables (typically near the end) are encountered first."""
    all_readings = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in reversed(pdf.pages):
            tables = page.extract_tables()
            for table in tables or []:
                for row in table:
                    for cell in row:
                        if cell is None:
                            continue
                        cell_str = str(cell).strip()
                        # Also try collapsed (0 . 2 8 5 -> 0.285)
                        collapsed = re.sub(r"\s+", "", cell_str)
                        for src in (cell_str, collapsed):
                            m = re.search(r"(0\.\d{2,4})", src)
                            if m:
                                try:
                                    v = float(m.group(1))
                                    if 0.05 <= v <= 3.0:
                                        all_readings.append(v)
                                        break
                                except ValueError:
                                    pass
    return all_readings


def _extract_readings_from_text(pdf_path: Path) -> List[float]:
    """Extract readings from text using pdfplumber. Iterates last-to-first
    so CML summary data (typically near the end) is encountered first."""
    all_readings = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in reversed(pdf.pages):
            text = page.extract_text()
            if text:
                all_readings.extend(_extract_numeric_readings(text))
    return all_readings


def _preprocess_for_ocr(img):
    """Enhance image for better OCR on inspection report tables.

    Pipeline: grayscale → autocontrast → unsharp mask.
    Grayscale removes color noise from scanned pages.
    Autocontrast normalises exposure across different scan qualities.
    UnsharpMask clarifies digit edges (0.285 vs 0.28, 0.358 vs 0.35) without
    introducing halation artefacts that a simple SHARPEN filter can cause.
    """
    try:
        from PIL import ImageEnhance, ImageFilter, ImageOps

        # Grayscale gives a uniform, noise-reduced base for both Tesseract and EasyOCR/Paddle
        gray = img.convert("L")
        # Autocontrast: stretches histogram to [0, 255]; cutoff=1 clips 1% of dark/light pixels
        # to avoid a single dark border or white glare dominating the normalisation.
        gray = ImageOps.autocontrast(gray, cutoff=1)
        # UnsharpMask: radius controls the blur kernel; percent is the boost strength;
        # threshold avoids sharpening already-sharp edges twice.
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=180, threshold=3))
        # Return RGB so pytesseract / EasyOCR / PaddleOCR all accept it without conversion.
        return gray.convert("RGB")
    except Exception:
        return img


def _run_ocr_on_page(page_image: bytes, dpi: int = 300, psm: int = 6) -> str:
    """
    Run OCR on a page image. Returns extracted text.

    Tesseract works best at 300+ DPI. PSM 6 = single block (tables); PSM 11 = sparse text.
    """
    try:
        import io

        import pytesseract
        from PIL import Image

        # Use Windows default install path when Tesseract not in PATH
        _win_path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if _win_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(_win_path)

        img = Image.open(io.BytesIO(page_image))
        # Rescale if small: Tesseract needs ≥1400 px per side for reliable 3-decimal readings.
        w, h = img.size
        if w < 1400 or h < 1400:
            scale = max(1400 / w, 1400 / h, 1.5)
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Preprocessing is on by default; set INSPECTION_REPORT_OCR_PREPROCESS=0 to disable.
        if os.getenv("INSPECTION_REPORT_OCR_PREPROCESS", "1") != "0":
            img = _preprocess_for_ocr(img)
        config = f"--psm {psm} --oem 3"  # OEM 3 = default LSTM
        return pytesseract.image_to_string(img, config=config)
    except Exception:
        return ""


# OCR: detect grid pages (6"x6", 3"x3", 1"x1", 2"x2" etc.) - do not extract readings from these
_OCR_GRID_PAGE = re.compile(
    r"grid\s+scan|grid\s+letters|grid\s+number|"
    r'[1236]\s*["\']?\s*[xX]\s*[1236]\s*["\']?|'
    r"letters\s+[A-Z]\s+to\s+[A-Z]|go\s+with\s+flow",
    re.I,
)


def _extract_with_ocr(pdf_path: Path) -> Tuple[str, List[float], List[str], str]:
    """Fallback: render PDF pages to images and run Tesseract OCR.
    Skips grid-scan pages *before* rendering to avoid wasting time on large detailed-scan pages.
    Only runs dual-PSM when explicitly enabled via INSPECTION_REPORT_OCR_MULTI_PSM=1."""
    doc = pymupdf.open(pdf_path)
    full_text = ""
    all_readings = []
    summary_page_readings: List[float] = []

    ocr_dpi = 400 if os.getenv("INSPECTION_REPORT_OCR_HIGH_DPI") else 300
    dual_psm = os.getenv("INSPECTION_REPORT_OCR_MULTI_PSM") == "1"

    for page_idx, page in enumerate(doc):
        # Quick native-text check (< 1 ms) before expensive pixmap + OCR.
        # Grid/detailed-scan pages can be skipped entirely once we have summary readings.
        if page_idx > 0:
            quick_text = page.get_text() or ""
            is_grid_prelim = bool(
                _OCR_GRID_PAGE.search(quick_text) or _UT_GRID_SECTION.search(quick_text)
            )
            is_summary_prelim = bool(_UT_REPORT_SUMMARY.search(quick_text))
            # Skip grid-only pages as soon as we have at least one summary-table reading.
            if is_grid_prelim and not is_summary_prelim and summary_page_readings:
                continue

        pix = page.get_pixmap(dpi=ocr_dpi)
        img_bytes = pix.tobytes(output="png")
        text = _run_ocr_on_page(img_bytes, psm=6)
        full_text += text + "\n"

        if page_idx == 0:
            continue  # header page: use for metadata only

        is_summary = _UT_REPORT_SUMMARY.search(text)
        is_grid_only = (_OCR_GRID_PAGE.search(text) or _UT_GRID_SECTION.search(text)) and not is_summary
        readings = _extract_numeric_readings(text)
        if is_summary:
            summary_page_readings.extend(readings)
        if is_grid_only and summary_page_readings:
            continue
        all_readings.extend(readings)
        # Dual-PSM second pass: opt-in only (off by default to avoid doubling OCR time)
        if dual_psm and len(readings) < 3:
            text2 = _run_ocr_on_page(img_bytes, psm=11)
            extra = _extract_numeric_readings(text2)
            all_readings.extend(extra)
            if _UT_REPORT_SUMMARY.search(text2):
                summary_page_readings.extend(extra)

    doc.close()
    # Prefer summary table readings when available (high sensitivity for image-based summaries)
    # If no summary found (image-only), use all readings - summary may be embedded in grid pages
    if summary_page_readings:
        all_readings = summary_page_readings

    date = _extract_date_from_text(full_text)
    circuit = _extract_circuit_from_text(full_text)
    cml_ids = _extract_cml_ids_from_text(full_text)

    return date or "", all_readings, cml_ids, circuit or ""


def _extract_with_easyocr(pdf_path: Path) -> Tuple[str, List[float], List[str], str]:
    """EasyOCR extraction — skips grid-scan pages before rendering to cut CPU time significantly."""
    try:
        import io
        import numpy as np
        from PIL import Image
    except ImportError:
        return "", [], [], ""

    reader = _get_easyocr_reader()
    if reader is None:
        return "", [], [], ""
    doc = pymupdf.open(pdf_path)
    full_text = ""
    all_readings = []
    summary_page_readings: List[float] = []
    ocr_dpi = 250 if os.getenv("INSPECTION_REPORT_OCR_HIGH_DPI") else 200

    for page_idx, page in enumerate(doc):
        # Quick native-text check before expensive rendering + neural OCR.
        # EasyOCR is ~3-5 s/page on CPU; skipping grid pages saves substantial time.
        if page_idx > 0:
            quick_text = page.get_text() or ""
            is_grid_prelim = bool(
                _OCR_GRID_PAGE.search(quick_text) or _UT_GRID_SECTION.search(quick_text)
            )
            is_summary_prelim = bool(_UT_REPORT_SUMMARY.search(quick_text))
            if is_grid_prelim and not is_summary_prelim and summary_page_readings:
                continue

        pix = page.get_pixmap(dpi=ocr_dpi)
        img_bytes = pix.tobytes(output="png")
        img = Image.open(io.BytesIO(img_bytes))
        if os.getenv("INSPECTION_REPORT_OCR_PREPROCESS", "1") != "0":
            img = _preprocess_for_ocr(img)
        img = np.array(img)
        result = reader.readtext(img)
        page_text = ""
        for (_, text, _) in result:
            page_text += text + "\n"
            full_text += text + "\n"
        readings = _extract_numeric_readings(page_text)
        if page_idx > 0:
            is_summary = _UT_REPORT_SUMMARY.search(page_text)
            is_grid_only = (_OCR_GRID_PAGE.search(page_text) or _UT_GRID_SECTION.search(page_text)) and not is_summary
            if is_summary:
                summary_page_readings.extend(readings)
            if not (is_grid_only and summary_page_readings):
                all_readings.extend(readings)
    doc.close()
    if summary_page_readings:
        all_readings = summary_page_readings

    date = _extract_date_from_text(full_text)
    circuit = _extract_circuit_from_text(full_text)
    cml_ids = _extract_cml_ids_from_text(full_text)
    return date or "", all_readings, cml_ids, circuit or ""


def _is_image_heavy_report(pdf_path: Path, full_text: str) -> bool:
    """Heuristic: scanned/image-heavy reports need structured OCR more than text parsing."""
    if len(full_text.strip()) < 400:
        return True
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return False

    try:
        image_pages = 0
        for page_idx, page in enumerate(doc):
            if page_idx == 0:
                continue
            page_text = page.get_text() or ""
            images = page.get_images(full=True)
            large_images = sum(1 for img in images if len(img) >= 4 and img[2] >= 900 and img[3] >= 400)
            if large_images >= 1 and len(page_text.strip()) < 400:
                image_pages += 1
        return image_pages >= 1
    finally:
        doc.close()


def _get_candidate_vision_pages(pdf_path: Path, max_pages: int = 5) -> List[int]:
    """
    Pick likely result-table pages for structured local OCR.
    Prefer pages with large embedded images and CML/result markers, while skipping grid pages.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return []

    scored_pages: List[Tuple[int, int]] = []
    page_count = len(doc)
    try:
        for page_idx, page in enumerate(doc):
            if page_idx == 0:
                continue
            text = page.get_text() or ""
            if _OCR_GRID_PAGE.search(text) or _UT_GRID_SECTION.search(text):
                continue

            score = 0
            upper_text = text.upper()
            if _UT_REPORT_SUMMARY.search(text):
                score += 6
            if "RESULTS" in upper_text:
                score += 3
            if "CML" in upper_text:
                score += 3
            if "CIRCUIT" in upper_text:
                score += 2

            images = page.get_images(full=True)
            large_images = sum(1 for img in images if len(img) >= 4 and img[2] >= 900 and img[3] >= 400)
            score += min(large_images, 3)

            if score > 0:
                scored_pages.append((score, page_idx))
    finally:
        doc.close()

    scored_pages.sort(key=lambda item: (-item[0], item[1]))
    page_indices = [page_idx for _, page_idx in scored_pages[:max_pages]]
    if page_indices:
        return page_indices
    return list(range(1, min(page_count, max_pages + 1)))


def _iter_candidate_image_segments(doc, candidate_pages: List[int]):
    """Yield likely embedded report-image segments from candidate pages."""
    try:
        import io

        from PIL import Image
    except ImportError:
        return

    for page_idx in reversed(candidate_pages):
        if page_idx >= len(doc):
            continue
        page = doc[page_idx]
        large_images = []
        for img in page.get_images(full=True):
            if len(img) < 4:
                continue
            xref = img[0]
            width, height = img[2], img[3]
            if width >= 900 and height >= 400:
                large_images.append((xref, width, height))

        for xref, _, _ in large_images[:3]:
            try:
                image_info = doc.extract_image(xref)
                image = Image.open(io.BytesIO(image_info["image"])).convert("RGB")
            except Exception:
                continue

            segments = []
            if image.width >= image.height:
                segments.append(("bottom", image.crop((0, image.height // 2, image.width, image.height))))
            segments.append(("full", image))

            for segment_name, segment in segments:
                scale = 2 if max(segment.size) < 1600 else 1
                resized = segment.resize((segment.width * scale, segment.height * scale)) if scale > 1 else segment
                yield page_idx, xref, segment_name, resized


def _iter_candidate_page_segments(doc, candidate_pages: List[int], dpi: int = 300):
    """Yield full-page rendered images for candidate pages (image-first OCR path)."""
    for page_idx in candidate_pages:
        if page_idx < 0 or page_idx >= len(doc):
            continue
        try:
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            yield page_idx, f"page-{page_idx + 1}", "full_page", pix
        except Exception:
            continue


def _normalize_easyocr_tokens(ocr_result) -> List[dict]:
    """Convert EasyOCR output into simple positioned tokens."""
    tokens = []
    for item in ocr_result or []:
        if not item or len(item) < 2:
            continue
        bbox, text = item[0], str(item[1] or "").strip()
        conf = float(item[2]) if len(item) > 2 else 0.0
        if not text:
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        tokens.append(
            {
                "text": text,
                "conf": conf,
                "left": min(xs),
                "right": max(xs),
                "top": min(ys),
                "bottom": max(ys),
                "cy": (min(ys) + max(ys)) / 2,
                "height": max(1.0, max(ys) - min(ys)),
            }
        )
    return tokens


def _normalize_paddleocr_tokens(ocr_result) -> List[dict]:
    """Convert PaddleOCR output into simple positioned tokens."""
    tokens = []
    lines = []
    if isinstance(ocr_result, list):
        if ocr_result and isinstance(ocr_result[0], list) and ocr_result and ocr_result[0]:
            # Common form: [ [ [bbox, (text, conf)], ... ] ]
            first = ocr_result[0]
            if first and isinstance(first[0], (list, tuple)):
                lines = first
        if not lines:
            # Alternate form: [ [bbox, (text, conf)], ... ]
            lines = ocr_result
    for item in lines or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        bbox, txt_conf = item[0], item[1]
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        text = ""
        conf = 0.0
        if isinstance(txt_conf, (list, tuple)) and len(txt_conf) >= 2:
            text = str(txt_conf[0] or "").strip()
            try:
                conf = float(txt_conf[1])
            except Exception:
                conf = 0.0
        else:
            text = str(txt_conf or "").strip()
        if not text:
            continue
        try:
            xs = [float(p[0]) for p in bbox]
            ys = [float(p[1]) for p in bbox]
        except Exception:
            continue
        tokens.append(
            {
                "text": text,
                "conf": conf,
                "left": min(xs),
                "right": max(xs),
                "top": min(ys),
                "bottom": max(ys),
                "cy": (min(ys) + max(ys)) / 2,
                "height": max(1.0, max(ys) - min(ys)),
            }
        )
    return tokens


def _easyocr_use_gpu() -> bool:
    """Use GPU on the backend host when INSPECTION_REPORT_OCR_GPU=1 (requires CUDA + torch with CUDA)."""
    flag = os.getenv("INSPECTION_REPORT_OCR_GPU", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        try:
            import torch

            return bool(torch.cuda.is_available())
        except ImportError:
            return False
    return False


def _get_easyocr_reader():
    """Reuse a singleton EasyOCR reader. Thread-safe: initialization is guarded by a lock."""
    global _EASYOCR_READER, _EASYOCR_INIT_FAILED
    # Fast path: already initialized (no lock needed — reads are safe under CPython GIL)
    if _EASYOCR_INIT_FAILED:
        return None
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER
    # Slow path: first-time init, serialize with a lock so two threads never race here
    with _EASYOCR_INIT_LOCK:
        # Re-check inside the lock in case another thread just finished initializing
        if _EASYOCR_INIT_FAILED:
            return None
        if _EASYOCR_READER is not None:
            return _EASYOCR_READER
        try:
            import easyocr
        except ImportError:
            _EASYOCR_INIT_FAILED = True
            return None
        try:
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=_easyocr_use_gpu(), verbose=False)
        except Exception as exc:
            msg = str(exc).lower()
            _logger.warning("EasyOCR init failed: %s", exc)
            if "not enough memory" in msg or "alloc" in msg and "fail" in msg:
                _logger.warning(
                    "EasyOCR needs hundreds of MB of free RAM. Close other apps, or use "
                    "Tesseract-only (install Tesseract, set INSPECTION_REPORT_OCR_ENGINE=tesseract), "
                    "or avoid INSPECTION_REPORT_PRELOAD_OCR=1 on this machine."
                )
            _EASYOCR_INIT_FAILED = True
            return None
    return _EASYOCR_READER


def _get_paddleocr_reader():
    """Reuse a singleton PaddleOCR reader. Thread-safe: initialization is guarded by a lock."""
    global _PADDLEOCR_READER, _PADDLEOCR_INIT_FAILED
    # Fast path
    if _PADDLEOCR_INIT_FAILED:
        return None
    if _PADDLEOCR_READER is not None:
        return _PADDLEOCR_READER
    # Slow path: serialize init
    with _PADDLEOCR_INIT_LOCK:
        if _PADDLEOCR_INIT_FAILED:
            return None
        if _PADDLEOCR_READER is not None:
            return _PADDLEOCR_READER
        try:
            from paddleocr import PaddleOCR
        except Exception:
            # Catches ImportError but also DLL/binary errors (FileNotFoundError on Windows
            # when paddle's native libs are missing or incompatible). Mark as failed so we
            # never retry — the failed import is slow and prints noisy warnings.
            _PADDLEOCR_INIT_FAILED = True
            return None
        try:
            _PADDLEOCR_READER = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
            )
        except Exception as exc:
            _logger.warning("PaddleOCR init failed: %s", exc)
            _PADDLEOCR_INIT_FAILED = True
            return None
    return _PADDLEOCR_READER


def _run_structured_ocr_on_image(img_np):
    """
    Return normalized OCR tokens from preferred structured OCR engine.
    Engine order:
    - INSPECTION_REPORT_STRUCTURED_OCR_ENGINE=paddle: PaddleOCR only
    - INSPECTION_REPORT_STRUCTURED_OCR_ENGINE=easyocr: EasyOCR only
    - default/auto: PaddleOCR first, then EasyOCR fallback
    """
    engine = os.getenv("INSPECTION_REPORT_STRUCTURED_OCR_ENGINE", "auto").strip().lower()
    token_sets: List[List[dict]] = []

    # Serialize CPU-bound OCR calls so parallel threads don't thrash each other.
    # pdfplumber threads never reach this point and remain truly parallel.
    with _OCR_SEMAPHORE:
        if engine in ("paddle", "auto"):
            reader = _get_paddleocr_reader()
            if reader is not None:
                try:
                    paddle_result = reader.ocr(img_np, cls=True)
                    paddle_tokens = _normalize_paddleocr_tokens(paddle_result)
                    if paddle_tokens:
                        token_sets.append(paddle_tokens)
                        if engine == "paddle":
                            return paddle_tokens
                except Exception:
                    pass

        if engine in ("easyocr", "auto"):
            reader = _get_easyocr_reader()
            if reader is not None:
                try:
                    easy_result = reader.readtext(img_np, detail=1)
                    easy_tokens = _normalize_easyocr_tokens(easy_result)
                    if easy_tokens:
                        token_sets.append(easy_tokens)
                        if engine == "easyocr":
                            return easy_tokens
                except Exception:
                    pass

    # In auto mode, prefer richer token output (usually better row reconstruction).
    if token_sets:
        token_sets.sort(key=len, reverse=True)
        return token_sets[0]
    return []


def _extract_structured_rows_from_easyocr_tokens(
    tokens: List[dict],
    source_filename: str,
    fallback_circuit: str,
    fallback_date: str,
    fallback_cml_ids: Optional[List[str]] = None,
) -> List[ExtractedReading]:
    """
    Recover summary-table rows from positioned OCR tokens.
    This is a lightweight local alternative to a document parser like MinerU.
    """
    if not tokens:
        return []

    joined_text = " ".join(t["text"] for t in sorted(tokens, key=lambda t: (t["top"], t["left"])))
    upper_text = joined_text.upper()
    if "CIRCUIT" not in upper_text or "CML" not in upper_text or "SECTION" not in upper_text:
        return []

    circuit_id = fallback_circuit or "Unknown"
    # Only attempt OCR-based circuit extraction when fallback is absent or unknown.
    # Report numbers embedded in page text (e.g. "UT-ROBJOS-26-063") contain patterns
    # like "26-063" that match the circuit regex but are NOT the actual circuit ID.
    # When pdfplumber already resolved the circuit (e.g. "52-001G"), trust that over OCR.
    if not fallback_circuit or fallback_circuit in ("Unknown", ""):
        circuit_match = re.search(r"\b\d{2,3}-\d{3}[A-Z]?(?:\s+\d+-\d+)?\b", joined_text)
        if circuit_match:
            circuit_id = _extract_circuit_base(circuit_match.group(0))

    cml_base = None
    for expected in fallback_cml_ids or []:
        if expected and expected in joined_text:
            cml_base = expected
            break
    if not cml_base:
        cml_match = re.search(r"\b\d+\.\d+\b", joined_text)
        if cml_match:
            cml_base = cml_match.group(0)
    if not cml_base:
        return []

    avg_height = sum(t["height"] for t in tokens) / max(1, len(tokens))
    # OCR often places the leftmost section cell and the numeric reading cells on slightly
    # different baselines; use a wider band so one logical table row stays together.
    row_tolerance = max(55.0, avg_height * 1.5)
    header_tokens = [t for t in tokens if re.fullmatch(r"(?:CIRCUIT|CML|SECTION|DIAM\.?|NORTH|SOUTH|EAST|WEST|TOP|BOTTOM|CENTER|HIGH|COMMENTS|A|B|C|D|E)", t["text"], re.I)]
    header_row = None
    for token in header_tokens:
        same_row = [t for t in header_tokens if abs(t["cy"] - token["cy"]) <= row_tolerance]
        labels = {t["text"].upper().rstrip(".") for t in same_row}
        if {"CIRCUIT", "CML", "SECTION"}.issubset(labels):
            header_row = same_row
            break
    if not header_row:
        return []

    x_by_label = {}
    for token in header_row:
        label = token["text"].upper().rstrip(".")
        if label not in x_by_label:
            x_by_label[label] = token["left"]

    section_x = x_by_label.get("SECTION")
    cml_x = x_by_label.get("CML")
    reading_start_x = min(
        [x_by_label[label] for label in ("A", "NORTH", "TOP") if label in x_by_label] or [x_by_label.get("DIAM", 0) + 80]
    )

    sorted_tokens = sorted(tokens, key=lambda t: (t["cy"], t["left"]))
    row_centers: List[float] = []
    header_cutoff = max(t["cy"] for t in header_row) + max(12.0, avg_height * 0.4)
    for token in sorted_tokens:
        if token["cy"] <= header_cutoff:
            continue
        if any(abs(token["cy"] - center) <= row_tolerance for center in row_centers):
            continue
        row_centers.append(token["cy"])

    results: List[ExtractedReading] = []
    active_cml_base = cml_base
    pending_row: Optional[dict] = None
    for center in row_centers:
        row_tokens = [t for t in sorted_tokens if abs(t["cy"] - center) <= row_tolerance]
        row_tokens.sort(key=lambda t: t["left"])
        row_text = " ".join(t["text"] for t in row_tokens)
        if re.search(r"N/?A|FLANGE", row_text, re.I):
            pending_row = None
            continue

        row_cml_base = active_cml_base
        row_has_explicit_cml = False
        if cml_x is not None:
            cml_candidates = []
            for token in row_tokens:
                if re.fullmatch(r"\d+\.\d+", token["text"]):
                    cml_candidates.append((abs(token["left"] - cml_x), token["left"], token["text"]))
            if cml_candidates:
                cml_candidates.sort(key=lambda item: (item[0], item[1]))
                candidate = cml_candidates[0][2]
                if not fallback_cml_ids or candidate in fallback_cml_ids:
                    row_cml_base = candidate
                    active_cml_base = candidate
                    row_has_explicit_cml = True
        if not row_cml_base:
            continue

        if section_x is None:
            continue
        section_candidates = []
        for token in row_tokens:
            if re.fullmatch(r"\d{1,2}", token["text"]):
                section_text = token["text"]
                if section_text == "11":
                    section_text = "1"
                try:
                    section_num = int(section_text)
                except ValueError:
                    continue
                if 1 <= section_num <= 40:
                    section_candidates.append((token["left"], section_text))
        unique_sections = []
        seen_sections = set()
        for left, section_text in sorted(section_candidates, key=lambda item: item[0]):
            if section_text not in seen_sections:
                unique_sections.append(section_text)
                seen_sections.add(section_text)

        # Minimum OCR confidence for numeric reading tokens.
        # 0.6 rejects clear noise while allowing marginally blurry scans.
        # Set INSPECTION_REPORT_OCR_MIN_CONF=0 to disable confidence gating.
        _min_conf = float(os.getenv("INSPECTION_REPORT_OCR_MIN_CONF", "0.6"))

        readings_in_row = []
        for token in row_tokens:
            if token["left"] + 10 < reading_start_x:
                continue
            if re.fullmatch(r"0\.\d{2,4}", token["text"]):
                if _min_conf > 0 and token.get("conf", 1.0) < _min_conf:
                    continue  # discard low-confidence decimal token (likely OCR noise)
                try:
                    value = float(token["text"])
                except ValueError:
                    continue
                if 0.05 <= value <= 3.0:
                    readings_in_row.append(value)
        if not readings_in_row:
            pending_row = None
            continue

        if not unique_sections:
            pending_row = {
                "cml_base": row_cml_base,
                "readings": readings_in_row,
                "inherits_next_cml": not row_has_explicit_cml,
            }
            continue

        if pending_row and len(unique_sections) >= 2:
            pending_section = unique_sections[0]
            pending_cml_base = row_cml_base if pending_row.get("inherits_next_cml") else pending_row["cml_base"]
            results.append(
                ExtractedReading(
                    circuit_id=circuit_id,
                    cml_id=f"{pending_cml_base}-{pending_section}",
                    measurement_date=fallback_date or "",
                    min_reading=min(pending_row["readings"]),
                    all_readings=pending_row["readings"],
                    source_file=source_filename,
                    extraction_method="ocr_structured",
                )
            )
            section = unique_sections[-1]
            pending_row = None
        else:
            section = unique_sections[-1]

        min_value = min(readings_in_row)
        results.append(
            ExtractedReading(
                circuit_id=circuit_id,
                cml_id=f"{row_cml_base}-{section}",
                measurement_date=fallback_date or "",
                min_reading=min_value,
                all_readings=readings_in_row,
                source_file=source_filename,
                extraction_method="ocr_structured",
            )
        )
        pending_row = None

    return _validate_and_dedupe_before_export(results) if results else []


def _extract_structured_with_local_ocr(
    pdf_path: Path,
    source_filename: str = "",
    fallback_circuit: str = "",
    fallback_date: str = "",
    fallback_cml_ids: Optional[List[str]] = None,
) -> List[ExtractedReading]:
    """Local structured OCR for image-heavy reports using embedded summary images."""
    # ── Cache check ────────────────────────────────────────────────────────────
    try:
        _cache_key = (str(pdf_path), pdf_path.stat().st_mtime_ns)
        if _cache_key in _STRUCT_OCR_CACHE:
            _logger.debug("OCR cache hit for %s", pdf_path.name)
            return _STRUCT_OCR_CACHE[_cache_key]
    except Exception:
        _cache_key = None

    try:
        import io
        import numpy as np
        from PIL import Image
    except ImportError:
        return []

    candidate_pages = _get_candidate_vision_pages(pdf_path, max_pages=6)
    if not candidate_pages:
        return []

    # Require at least one OCR backend.
    if _get_paddleocr_reader() is None and _get_easyocr_reader() is None:
        return []

    doc = pymupdf.open(pdf_path)
    results: List[ExtractedReading] = []
    try:
        import io

        # Pass 1: embedded report images (high precision on image-based summary tables).
        for page_idx, xref, segment_name, segment in _iter_candidate_image_segments(doc, candidate_pages):
            try:
                tokens = _run_structured_ocr_on_image(np.array(segment))
            except Exception:
                continue
            page_results = _extract_structured_rows_from_easyocr_tokens(
                tokens,
                source_filename=source_filename or pdf_path.name,
                fallback_circuit=fallback_circuit,
                fallback_date=fallback_date,
                fallback_cml_ids=fallback_cml_ids,
            )
            if page_results:
                results.extend(page_results)
                expected_bases = {cml_id for cml_id in (fallback_cml_ids or []) if cml_id}
                found_bases = {r.cml_id.split("-", 1)[0] for r in results if "-" in r.cml_id}
                min_expected_rows = max(5, len(expected_bases) * 2 + 1) if expected_bases else 5
                if expected_bases and expected_bases.issubset(found_bases) and len(results) >= min_expected_rows:
                    return _validate_and_dedupe_before_export(results)

        # Pass 2: full page rendered as image (helps when table is vector PDF text and not embedded image).
        # Skip if Pass 1 already returned structured rows — pdfplumber can fill gaps.
        if not results:
            for page_idx, xref, segment_name, pix in _iter_candidate_page_segments(doc, candidate_pages):
                try:
                    segment = Image.open(io.BytesIO(pix.tobytes(output="png"))).convert("RGB")
                    tokens = _run_structured_ocr_on_image(np.array(segment))
                except Exception:
                    continue
                page_results = _extract_structured_rows_from_easyocr_tokens(
                    tokens,
                    source_filename=source_filename or pdf_path.name,
                    fallback_circuit=fallback_circuit,
                    fallback_date=fallback_date,
                    fallback_cml_ids=fallback_cml_ids,
                )
                if page_results:
                    results.extend(page_results)
                    break  # First successful page is sufficient; pdfplumber supplements gaps
    finally:
        doc.close()

    finalized = _validate_and_dedupe_before_export(results) if results else []
    # Guard against weak OCR matches: require at least a few row-level readings.
    out = [] if (finalized and len(finalized) < 3) else finalized
    if _cache_key:
        _STRUCT_OCR_CACHE[_cache_key] = out
    return out


def _supplement_with_pdfplumber(
    pdf_path: Path,
    circuit_base: str,
    cml_ids: List[str],
    date_str: str,
    primary_results: List[ExtractedReading],
) -> List[ExtractedReading]:
    """Fill in zones from pdfplumber that the structured OCR pass missed.

    OCR can miss zone 1 or other rows when they are close to the header or lack
    explicit CML tokens.  pdfplumber-based parsers often recover these rows since
    they work from PDF text rather than rendered images.  We only ADD rows, never
    replace: if OCR already found a zone, the OCR reading is kept.
    """
    primary_keys = {(r.circuit_id, r.cml_id) for r in primary_results}
    plumber: List[ExtractedReading] = []
    try:
        if len(cml_ids) == 1 and _get_summary_page_indices(pdf_path):
            plumber = _parse_ut_report_summary_table(pdf_path, circuit_base, cml_ids, date_str)
        if not plumber:
            plumber = _parse_acuren_results_table(pdf_path, circuit_base, cml_ids, date_str)
        if not plumber and len(cml_ids) == 1:
            plumber = _parse_single_cml_permissive(pdf_path, circuit_base, cml_ids[0], date_str)
        if not plumber:
            plumber = _parse_generic_zone_table(pdf_path, circuit_base, cml_ids, date_str)
    except Exception:
        pass

    if not plumber:
        return primary_results

    supplemented = list(primary_results)
    for r in plumber:
        if (r.circuit_id, r.cml_id) not in primary_keys:
            supplemented.append(r)

    return _validate_and_dedupe_before_export(supplemented)


def parse_inspection_report_pdf(pdf_path: Path, source_filename: str = "") -> List[ExtractedReading]:
    """
    Parse a single UT inspection report PDF.

    Extracts: circuit ID, CML IDs, measurement date, and minimum thickness reading per CML.

    Args:
        pdf_path: Path to the PDF file
        source_filename: Original filename for display

    Returns:
        List of ExtractedReading (one per CML)
    """
    source_filename = source_filename or str(pdf_path)
    date = ""
    circuit = ""
    cml_ids: List[str] = []

    # First pass: pdfplumber — three independent operations run in parallel
    full_text = ""
    readings_from_tables = []
    readings_from_text = []

    def _extract_full_text_local(path: Path) -> str:
        text = ""
        try:
            with pdfplumber.open(path) as _pdf:
                for _page in _pdf.pages:
                    _t = _page.extract_text()
                    if _t:
                        text += _t + "\n"
        except Exception:
            pass
        return text

    with ThreadPoolExecutor(max_workers=3) as _pp_pool:
        _f_text   = _pp_pool.submit(_extract_full_text_local, pdf_path)
        _f_tables = _pp_pool.submit(_extract_readings_from_tables, pdf_path)
        _f_txtrd  = _pp_pool.submit(_extract_readings_from_text, pdf_path)
        try:
            full_text = _f_text.result()
        except Exception:
            full_text = ""
        try:
            readings_from_tables = _f_tables.result()
        except Exception:
            readings_from_tables = []
        try:
            readings_from_text = _f_txtrd.result()
        except Exception:
            readings_from_text = []

    # Combine readings (prefer table extraction, fallback to text)
    all_readings = readings_from_tables if readings_from_tables else readings_from_text

    # Seed metadata from text/filename early so image-based fallbacks have context.
    date = _extract_date_from_text(full_text) or date
    circuit = _extract_circuit_from_text(full_text) or circuit
    cml_ids = _extract_cml_ids_from_text(full_text) or cml_ids
    if not date:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", source_filename)
        if m:
            date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    if not circuit:
        m = re.search(r"([\d]+-[\w]+\s+[\d]+-[\d]+)", source_filename)
        if m:
            circuit = m.group(1).strip()
    if not cml_ids:
        cml_ids = _extract_cml_ids_from_filename(source_filename)

    # Image-first strategy: try structured OCR from page images before PDF table parsing.
    # Default OFF — pdfplumber is tried first (fast, works for text-based PDFs).
    # Set INSPECTION_REPORT_IMAGE_FIRST=1 to enable for scanned/image-heavy reports.
    if os.getenv("INSPECTION_REPORT_IMAGE_FIRST", "0") == "1":
        image_first_results = _extract_structured_with_local_ocr(
            pdf_path,
            source_filename=source_filename,
            fallback_circuit=_extract_circuit_base(circuit or "Unknown"),
            fallback_date=date or "",
            fallback_cml_ids=cml_ids,
        )
        if image_first_results:
            if cml_ids:
                expected = set(cml_ids)
                found = {r.cml_id.split("-", 1)[0] for r in image_first_results if "-" in r.cml_id}
                if found & expected:
                    # Supplement OCR results with pdfplumber for any zones OCR missed
                    # (e.g. zone 1 rows that appear very close to the header in the image).
                    merged = _supplement_with_pdfplumber(
                        pdf_path, _extract_circuit_base(circuit or "Unknown"), cml_ids, date or "", image_first_results
                    )
                    return _finalize_results(pdf_path, source_filename, merged)
            elif len(image_first_results) >= 3:
                merged = _supplement_with_pdfplumber(
                    pdf_path, _extract_circuit_base(circuit or "Unknown"), cml_ids, date or "", image_first_results
                )
                return _finalize_results(pdf_path, source_filename, merged)

    # Try OCR when: no readings, very little text, or suspicious 0.0-only readings (image-based table)
    _suspicious_readings = all_readings and all(r == 0.0 for r in all_readings)
    _try_ocr = not all_readings or len(full_text) < 100 or _suspicious_readings
    _image_heavy_report = _is_image_heavy_report(pdf_path, full_text)
    if _try_ocr:
        if _image_heavy_report:
            structured_local_results = _extract_structured_with_local_ocr(
                pdf_path,
                source_filename=source_filename,
                fallback_circuit=_extract_circuit_base(circuit or "Unknown"),
                fallback_date=date or "",
                fallback_cml_ids=cml_ids,
            )
            if structured_local_results:
                return _finalize_results(
                    pdf_path, source_filename, [replace(r, source_file=source_filename) for r in structured_local_results]
                )

        # OCR fallback order: EasyOCR first (usually more accurate on tables, no external install),
        # then Tesseract. Each engine is called at most once to avoid doubling the OCR time.
        ocr_date, ocr_readings, ocr_cml_ids, ocr_circuit = "", [], [], ""
        if os.getenv("INSPECTION_REPORT_OCR_ENGINE") != "tesseract":
            try:
                e_date, e_readings, e_cmls, e_circuit = _extract_with_easyocr(pdf_path)
                if e_readings:
                    ocr_date, ocr_readings, ocr_cml_ids, ocr_circuit = e_date, e_readings, e_cmls, e_circuit
            except Exception:
                pass
        # Try Tesseract only when EasyOCR found nothing or insufficient readings
        if len(ocr_readings) < 4:
            try:
                t_date, t_readings, t_cmls, t_circuit = _extract_with_ocr(pdf_path)
                if len(t_readings) > len(ocr_readings):
                    ocr_date, ocr_readings, ocr_cml_ids, ocr_circuit = t_date, t_readings, t_cmls, t_circuit
            except Exception as e:
                _logger.debug(
                    "Tesseract OCR fallback failed (install Tesseract for image-based reports): %s", e
                )
        if ocr_readings:
            all_readings = ocr_readings
        if ocr_date:
            date = ocr_date
        if ocr_cml_ids:
            cml_ids = ocr_cml_ids
        if ocr_circuit:
            circuit = ocr_circuit

    # Use pdfplumber/full_text only when OCR didn't provide values
    date = date or _extract_date_from_text(full_text)
    circuit = circuit or _extract_circuit_from_text(full_text)
    cml_ids = cml_ids or _extract_cml_ids_from_text(full_text)

    # Fallback: try filename for date (e.g. ..._02.23.2026.pdf)
    if not date:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", source_filename)
        if m:
            date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"

    # Fallback: try filename for circuit (e.g. 52-021K 1-2 CML ...)
    if not circuit:
        m = re.search(r"([\d]+-[\w]+\s+[\d]+-[\d]+)", source_filename)
        if m:
            circuit = m.group(1).strip()

    if not circuit:
        circuit = "Unknown"

    # Fallback: CML from filename (e.g. "1.29, 1.37" or "CML 1.52,1.29&4.09")
    if not cml_ids:
        cml_ids = _extract_cml_ids_from_filename(source_filename)
    if not cml_ids and all_readings:
        cml_ids = ["1"]  # single CML

    circuit_base = _extract_circuit_base(circuit)
    date_str = date or ""

    # When 3+ CMLs, use generic zone table (multi-section format). Else try Acuren first.
    if len(cml_ids) >= 3:
        generic_results = _parse_generic_zone_table(pdf_path, circuit_base, cml_ids, date_str)
        if generic_results:
            return _finalize_results(pdf_path, source_filename, generic_results)

    # Single CML with UT REPORT - TEE/ELBOW summary page: use dedicated summary table parser
    if len(cml_ids) == 1 and _get_summary_page_indices(pdf_path):
        ut_summary_results = _parse_ut_report_summary_table(pdf_path, circuit_base, cml_ids, date_str)
        if ut_summary_results:
            ut_summary_results = _dedupe_by_cml_keep_min(ut_summary_results)
            ut_summary_results = _validate_and_dedupe_before_export(ut_summary_results)
            return _finalize_results(pdf_path, source_filename, ut_summary_results)

    acuren_results = _parse_acuren_results_table(pdf_path, circuit_base, cml_ids, date_str)
    if acuren_results:
        # For single CML: also try permissive parser (catches tables without diameter column)
        if len(cml_ids) == 1:
            permissive = _parse_single_cml_permissive(pdf_path, circuit_base, cml_ids[0], date_str)
            if len(permissive) > len(acuren_results):
                acuren_results = permissive
        acuren_results = _dedupe_by_cml_keep_min(acuren_results)
        acuren_results = _validate_and_dedupe_before_export(acuren_results)
        return _finalize_results(pdf_path, source_filename, acuren_results)
    if len(cml_ids) < 3:
        generic_results = _parse_generic_zone_table(pdf_path, circuit_base, cml_ids, date_str)
        if generic_results:
            # For single CML: try permissive if generic found few
            if len(cml_ids) == 1 and len(generic_results) < 5:
                permissive = _parse_single_cml_permissive(pdf_path, circuit_base, cml_ids[0], date_str)
                if len(permissive) > len(generic_results):
                    generic_results = permissive
            generic_results = _dedupe_by_cml_keep_min(generic_results)
            generic_results = _validate_and_dedupe_before_export(generic_results)
            return _finalize_results(pdf_path, source_filename, generic_results)

    # Image-based reports often lose table structure with OCR — retry structured local OCR.
    if _image_heavy_report:
        structured_local_results = _extract_structured_with_local_ocr(
            pdf_path,
            source_filename=source_filename,
            fallback_circuit=circuit_base,
            fallback_date=date_str,
            fallback_cml_ids=cml_ids,
        )
        if structured_local_results:
            return _finalize_results(
                pdf_path, source_filename, [replace(r, source_file=source_filename) for r in structured_local_results]
            )

    results = []

    if not cml_ids:
        return results

    # OCR-derived readings: build zone-level results when table parsers failed
    # (e.g. image-based results table like 52-010B - "Readings, Grids & Photos on attached pages")
    _valid_readings = [r for r in all_readings if 0.05 <= r <= 3.0]
    if _valid_readings and len(cml_ids) >= 1:
        n = len(cml_ids)
        total = len(_valid_readings)
        # Prefer 3 zones per CML for 2-CML reports; cap to avoid calibration noise
        _ocr_cml_ids = list(cml_ids)
        if n == 2 and total >= 6:
            if total >= 12:
                # OCR may read table with 2 values per cell; take every other
                _valid_readings = _valid_readings[0::2][:6]
            else:
                _valid_readings = _valid_readings[:6]
            total = len(_valid_readings)
            # Table layout often has CML columns reversed vs filename; try [1.37, 1.29]
            # Only swap for symmetric 3+3; for 3+2 (after outlier drop) use filename order
            _ocr_cml_ids = [cml_ids[1], cml_ids[0]]
        # Asymmetric zones: 5 readings for 2 CMLs = 3+2 (e.g. 6x6 grid + 3x3 branch)
        # When 6 readings but one is outlier (<0.25 when others >0.3), use 5 with 3+2
        _zone_splits = None
        _use_swapped_order = False
        if n == 2 and total == 5:
            _zone_splits = [3, 2]
        elif n == 2 and total == 6:
            above_03 = [r for r in _valid_readings if r >= 0.3]
            below_025 = [r for r in _valid_readings if r < 0.25]
            if len(above_03) >= 4 and len(below_025) == 1:
                _valid_readings = [r for r in _valid_readings if r >= 0.25]
                total = len(_valid_readings)
                if total == 5:
                    _zone_splits = [3, 2]
                    _ocr_cml_ids = list(cml_ids)  # Use filename order for 3+2
            if _zone_splits is None and total % n == 0:
                zones_per_cml = total // n
                if 2 <= zones_per_cml <= 9:
                    _zone_splits = [zones_per_cml] * n
                    _use_swapped_order = True  # 3+3 uses swapped
        elif total % n == 0:
            zones_per_cml = total // n
            if 2 <= zones_per_cml <= 9:
                _zone_splits = [zones_per_cml] * n
        if _zone_splits and sum(_zone_splits) == total:
            ocr_results = []
            idx = 0
            cml_list = _ocr_cml_ids if (n == 2 and _use_swapped_order) else cml_ids
            for i, cml_base in enumerate(cml_list):
                for z in range(_zone_splits[i]):
                    cml_id = f"{cml_base}-{z + 1}"
                    ocr_results.append(
                        ExtractedReading(
                            circuit_id=circuit_base,
                            cml_id=cml_id,
                            measurement_date=date_str,
                            min_reading=_valid_readings[idx],
                            all_readings=[_valid_readings[idx]],
                            source_file=source_filename,
                            extraction_method="ocr",
                        )
                    )
                    idx += 1
            return _finalize_results(pdf_path, source_filename, _validate_and_dedupe_before_export(ocr_results))

    # Fallback: aggregate readings by CML (min per CML)
    if len(cml_ids) == 1:
        min_reading = min(all_readings) if all_readings else 0.0
        cml_id = cml_ids[0]
        # Single-zone CML: use X.XX-1 format for consistency (e.g. 11.05 -> 11.05-1)
        if "-" not in cml_id:
            cml_id = f"{cml_id}-1"
        results.append(
            ExtractedReading(
                circuit_id=circuit_base,
                cml_id=cml_id,
                measurement_date=date or "",
                min_reading=min_reading,
                all_readings=all_readings,
                source_file=source_filename,
            )
        )
    else:
        # Multiple CMLs: try to split readings by table sections
        n = len(cml_ids)
        chunk_size = max(1, len(all_readings) // n) if all_readings else 0
        for i, cml_id in enumerate(cml_ids):
            if all_readings:
                start = i * chunk_size
                end = (i + 1) * chunk_size if i < n - 1 else len(all_readings)
                subset = all_readings[start:end] if chunk_size > 0 else all_readings
                min_reading = min(subset) if subset else min(all_readings)
            else:
                min_reading = 0.0
                subset = []
            results.append(
                ExtractedReading(
                    circuit_id=circuit_base,
                    cml_id=cml_id,
                    measurement_date=date or "",
                    min_reading=min_reading,
                    all_readings=subset or all_readings,
                    source_file=source_filename,
                )
            )

    return _finalize_results(pdf_path, source_filename, results)


def parse_inspection_report_pdfs(
    pdf_paths: List[Path],
    source_filenames: Optional[List[str]] = None,
) -> List[ExtractedReading]:
    """Parse multiple PDFs in parallel and return combined results in original order.

    Text-based PDFs (pdfplumber path) run truly in parallel.
    OCR-heavy PDFs are serialized through _OCR_SEMAPHORE to avoid CPU thrashing,
    but their pdfplumber pre-pass and post-processing still overlap with other threads.
    """
    if not pdf_paths:
        return []
    if len(pdf_paths) == 1:
        fn = (source_filenames[0] if source_filenames else "") or str(pdf_paths[0])
        return parse_inspection_report_pdf(pdf_paths[0], fn)

    # Cap workers: no benefit beyond number of PDFs; also avoid spawning too many threads
    # on machines where EasyOCR already saturates all cores.
    max_workers = min(len(pdf_paths), (os.cpu_count() or 4))

    def _parse_one(idx: int) -> List[ExtractedReading]:
        path = pdf_paths[idx]
        fn = (source_filenames[idx] if source_filenames and idx < len(source_filenames) else "") or str(path)
        try:
            return parse_inspection_report_pdf(path, fn)
        except Exception as exc:
            _logger.error("Error parsing %s: %s", path.name, exc)
            return []

    results: List[Optional[List[ExtractedReading]]] = [None] * len(pdf_paths)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {pool.submit(_parse_one, i): i for i in range(len(pdf_paths))}
        for future in as_completed(future_to_idx):
            results[future_to_idx[future]] = future.result()

    return [r for sublist in results if sublist for r in sublist]
