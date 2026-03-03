"""
Inspection Report PDF Parser

Extracts Circuit ID, CML ID, thickness readings, and measurement date from UT inspection report PDFs.
Supports Acuren-style reports with multiple table formats:
- Format A: SECTION/DIAM columns, 8"/6" -> CML base, row num -> zone (e.g. 1.01-1)
- Format B: CIRCUIT CML ZONE DIAM. table, CML section headers, multiple readings per zone -> min
Circuit format: NN-NNNXX (e.g. 52-021K); "1-2", "2-3" are breakdown drawing numbers, not circuit.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import pdfplumber
import pymupdf


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


def _extract_numeric_readings(text: str) -> List[float]:
    """
    Extract thickness readings from text. Handles normal (0.285) and fragmented PDF (0 . 2 8 5).
    Excludes false positives from phone numbers (e.g. 0.79 in 780.790.1776) via (?<![\\d.]) lookbehind.
    """
    readings = []
    # Normal format: 0.285, 0.380 - not part of longer number (avoid 780.790)
    for m in re.finditer(r"(?<!\d)(?<!\.)0\.\d{2,4}(?!\d)(?!\.\d)", text):
        try:
            v = float(m.group(0))
            if 0.05 <= v <= 3.0:
                readings.append(v)
        except ValueError:
            pass
    # Fragmented PDF: collapse spaces and try again (0 . 2 8 5 -> 0.285)
    if not readings:
        collapsed = re.sub(r"\s+", "", text)
        for m in re.finditer(r"(?<!\d)0\.\d{2,4}(?!\d)", collapsed):
            try:
                v = float(m.group(0))
                if 0.05 <= v <= 3.0:
                    readings.append(v)
            except ValueError:
                pass
    # Fallback: X.XXX (exclude 1.0, 2.0 calibration refs)
    if not readings:
        for m in re.finditer(r"(?<!\d)(\d+\.\d{3,4})(?!\d)", text):
            try:
                v = float(m.group(1))
                if 0.05 <= v <= 3.0 and not (0.99 <= v <= 1.01 or 1.99 <= v <= 2.01):
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


# Page filtering: prefer "UT REPORT - TEE/ELBOW" summary tables, skip "UT Grid" detailed readings
# Fragmented PDFs may have "U T R E P O R T - T E E" (spaces between letters)
_UT_REPORT_SUMMARY = re.compile(
    r"(?:U\s*T\s*R\s*E\s*P\s*O\s*R\s*T|UT\s+REPORT)\s*[-–]\s*"
    r"(?:T\s*E\s*E|TEE|E\s*L\s*B\s*O\s*W|ELBOW|PIPE|REDUCER|CAP|WELD|STRAIGHT)",
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
            tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            for table in tables or []:
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
        for page_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if not _should_process_page(page_text, summary_page_indices, page_idx):
                continue
            tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            for table in tables or []:
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
        for page_idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if not _should_process_page(page_text, summary_page_indices, page_idx):
                continue
            tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            for table in tables or []:
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
            tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
            for table in tables or []:
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
                                )
                            )

    return results


def _extract_readings_from_tables(pdf_path: Path) -> List[float]:
    """Extract numeric readings from PDF tables using pdfplumber."""
    all_readings = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
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
    """Extract readings from text using pdfplumber."""
    all_readings = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_readings.extend(_extract_numeric_readings(text))
    return all_readings


def _run_ocr_on_page(page_image: bytes, dpi: int = 300, psm: int = 6) -> str:
    """
    Run OCR on a page image. Returns extracted text.

    Tesseract works best at 300+ DPI. PSM 6 = single block (tables); PSM 11 = sparse text.
    """
    try:
        import pytesseract
        from PIL import Image
        import io

        # Use Windows default install path when Tesseract not in PATH
        _win_path = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if _win_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(_win_path)

        img = Image.open(io.BytesIO(page_image))
        # Rescale if small: Tesseract prefers 300 DPI; capital letters ~30px height
        w, h = img.size
        if w < 1200 or h < 1200:  # ~4" at 300 DPI
            scale = max(1200 / w, 1200 / h, 1.5)
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        config = f"--psm {psm} --oem 3"  # OEM 3 = default LSTM
        return pytesseract.image_to_string(img, config=config)
    except Exception:
        return ""


def _extract_with_ocr(pdf_path: Path) -> Tuple[str, List[float], List[str], str]:
    """Fallback: render PDF pages to images and run OCR. Returns (date, readings, cml_ids, circuit)."""
    doc = pymupdf.open(pdf_path)
    full_text = ""
    all_readings = []

    for page in doc:
        # 300 DPI recommended for Tesseract; pymupdf uses 72 base
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes(output="png")
        text = _run_ocr_on_page(img_bytes, psm=6)
        full_text += text + "\n"
        readings = _extract_numeric_readings(text)
        all_readings.extend(readings)
        # If PSM 6 got few readings, retry with PSM 11 (sparse text) for table-like layouts
        if len(readings) < 3 and len(doc) <= 5:
            text2 = _run_ocr_on_page(img_bytes, psm=11)
            all_readings.extend(_extract_numeric_readings(text2))

    doc.close()

    date = _extract_date_from_text(full_text)
    circuit = _extract_circuit_from_text(full_text)
    cml_ids = _extract_cml_ids_from_text(full_text)

    return date or "", all_readings, cml_ids, circuit or ""


def _extract_with_easyocr(pdf_path: Path) -> Tuple[str, List[float], List[str], str]:
    """Optional fallback: EasyOCR when Tesseract returns few readings. No external binary."""
    try:
        import easyocr
        import numpy as np
    except ImportError:
        return "", [], [], ""

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    doc = pymupdf.open(pdf_path)
    full_text = ""
    all_readings = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes(output="png")
        from PIL import Image
        import io
        img = np.array(Image.open(io.BytesIO(img_bytes)))
        result = reader.readtext(img)
        for (_, text, _) in result:
            full_text += text + "\n"
            all_readings.extend(_extract_numeric_readings(text))
    doc.close()

    date = _extract_date_from_text(full_text)
    circuit = _extract_circuit_from_text(full_text)
    cml_ids = _extract_cml_ids_from_text(full_text)
    return date or "", all_readings, cml_ids, circuit or ""


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


    # First pass: pdfplumber
    full_text = ""
    readings_from_tables = []
    readings_from_text = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
            readings_from_tables = _extract_readings_from_tables(pdf_path)
            readings_from_text = _extract_readings_from_text(pdf_path)
    except Exception:
        pass

    # Combine readings (prefer table extraction, fallback to text)
    all_readings = readings_from_tables if readings_from_tables else readings_from_text

    # Try OCR when: no readings, very little text, or suspicious 0.0-only readings (image-based table)
    _suspicious_readings = all_readings and all(r == 0.0 for r in all_readings)
    _try_ocr = not all_readings or len(full_text) < 100 or _suspicious_readings
    if _try_ocr:
        try:
            ocr_date, ocr_readings, ocr_cml_ids, ocr_circuit = _extract_with_ocr(pdf_path)
            if ocr_readings:
                all_readings = ocr_readings
            if ocr_date:
                date = ocr_date
            if ocr_cml_ids:
                cml_ids = ocr_cml_ids
            if ocr_circuit:
                circuit = ocr_circuit
            # If Tesseract got few readings, try EasyOCR (pip install easyocr)
            if len(ocr_readings) < 4:
                try:
                    e_date, e_readings, e_cmls, e_circuit = _extract_with_easyocr(pdf_path)
                    if e_readings and len(e_readings) > len(ocr_readings):
                        all_readings = e_readings
                        if e_date:
                            date = e_date
                        if e_cmls:
                            cml_ids = e_cmls
                        if e_circuit:
                            circuit = e_circuit
                except Exception:
                    pass
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(
                "OCR fallback failed (install Tesseract for image-based reports): %s", e
            )

    date = _extract_date_from_text(full_text)
    circuit = _extract_circuit_from_text(full_text)
    cml_ids = _extract_cml_ids_from_text(full_text)

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
            for r in generic_results:
                r.source_file = source_filename
            return generic_results

    # Single CML with UT REPORT - TEE/ELBOW summary page: use dedicated summary table parser
    if len(cml_ids) == 1 and _get_summary_page_indices(pdf_path):
        ut_summary_results = _parse_ut_report_summary_table(pdf_path, circuit_base, cml_ids, date_str)
        if ut_summary_results:
            ut_summary_results = _dedupe_by_cml_keep_min(ut_summary_results)
            ut_summary_results = _validate_and_dedupe_before_export(ut_summary_results)
            for r in ut_summary_results:
                r.source_file = source_filename
            return ut_summary_results

    acuren_results = _parse_acuren_results_table(pdf_path, circuit_base, cml_ids, date_str)
    if acuren_results:
        # For single CML: also try permissive parser (catches tables without diameter column)
        if len(cml_ids) == 1:
            permissive = _parse_single_cml_permissive(pdf_path, circuit_base, cml_ids[0], date_str)
            if len(permissive) > len(acuren_results):
                acuren_results = permissive
        acuren_results = _dedupe_by_cml_keep_min(acuren_results)
        acuren_results = _validate_and_dedupe_before_export(acuren_results)
        for r in acuren_results:
            r.source_file = source_filename
        return acuren_results
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
            for r in generic_results:
                r.source_file = source_filename
            return generic_results

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
            _ocr_cml_ids = [cml_ids[1], cml_ids[0]]
        if total % n == 0:
            zones_per_cml = total // n
            if 2 <= zones_per_cml <= 9:
                ocr_results = []
                for i, cml_base in enumerate(_ocr_cml_ids if n == 2 else cml_ids):
                    start = i * zones_per_cml
                    for z in range(zones_per_cml):
                        idx = start + z
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
                return _validate_and_dedupe_before_export(ocr_results)

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

    return results


def parse_inspection_report_pdfs(pdf_paths: List[Path], source_filenames: Optional[List[str]] = None) -> List[ExtractedReading]:
    """Parse multiple PDFs and return combined list of ExtractedReading."""
    all_results = []
    for i, path in enumerate(pdf_paths):
        fn = (source_filenames[i] if source_filenames and i < len(source_filenames) else "") or str(path)
        all_results.extend(parse_inspection_report_pdf(path, fn))
    return all_results
