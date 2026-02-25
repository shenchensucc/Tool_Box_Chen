"""
Inspection Report PDF Parser

Extracts Circuit ID, CML ID, thickness readings, and measurement date from UT inspection report PDFs.
Supports Acuren-style reports: table with SECTION/DIAM columns, 8"->CML 1.01, 6"->CML 1.05,
row number -> sub-CML suffix (e.g. 1.01-1, 1.05-2). Column A = reading per row.
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
    """Extract base circuit ID (e.g. '52-021K' from '52-021K 1-2')."""
    if not circuit_raw:
        return "Unknown"
    s = circuit_raw.strip()
    # "52-021K 1-2" -> "52-021K"
    m = re.match(r"^([\d]+-[\w]+)(?:\s+[\d]+-[\d]+)?", s)
    if m:
        return m.group(1).strip()
    return s


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
    """Extract thickness readings from text. Handles normal (0.285) and fragmented PDF (0 . 2 8 5) extraction."""
    readings = []
    # Normal format: 0.285, 0.380
    for m in re.finditer(r"\b(0\.\d{2,4})\b", text):
        try:
            v = float(m.group(1))
            if 0.05 <= v <= 3.0:
                readings.append(v)
        except ValueError:
            pass
    # Fragmented PDF: collapse spaces and try again (0 . 2 8 5 -> 0.285)
    if not readings:
        collapsed = re.sub(r"\s+", "", text)
        for m in re.finditer(r"0\.\d{2,4}", collapsed):
            try:
                v = float(m.group(0))
                if 0.05 <= v <= 3.0:
                    readings.append(v)
            except ValueError:
                pass
    # Fallback: X.XXX (exclude 1.0, 2.0 calibration refs)
    if not readings:
        for m in re.finditer(r"\b(\d+\.\d{3,4})\b", text):
            try:
                v = float(m.group(1))
                if 0.05 <= v <= 3.0 and not (0.99 <= v <= 1.01 or 1.99 <= v <= 2.01):
                    readings.append(v)
            except ValueError:
                pass
    return readings


def _parse_acuren_results_table(
    pdf_path: Path, circuit_base: str, cml_bases: List[str], date_str: str
) -> List[ExtractedReading]:
    """
    Parse Acuren-style results table: SECTION/DIAM columns, row num, 8"/6" -> CML base.
    Returns one ExtractedReading per row with a thickness reading (column A).
    """
    results = []
    diam_to_cml = {"8": cml_bases[0] if len(cml_bases) > 0 else "1.01", "6": cml_bases[1] if len(cml_bases) > 1 else "1.05"}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
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

                    # Diameter: 8" or 6" (must be diameter, not part of 0.28)
                    diam = None
                    if re.search(r"(?:^|[^\d.])8\s*[\"']", row_text) or "8\"" in collapsed or '8"' in row_text:
                        diam = "8"
                    elif re.search(r"(?:^|[^\d.])6\s*[\"']", row_text) or "6\"" in collapsed or '6"' in row_text:
                        diam = "6"

                    # Row number (1-4) - cell immediately before diameter (8" or 6") in SECTION column
                    row_num = None
                    cells = [str(c or "").strip() for c in row]
                    for i, c in enumerate(cells):
                        if c in ("1", "2", "3", "4"):
                            # Find next non-empty cell
                            for j in range(i + 1, len(cells)):
                                nc = cells[j]
                                if not nc:
                                    continue
                                if nc.startswith("8") and '"' in nc:
                                    row_num = c
                                    break
                                if nc.startswith("6") and '"' in nc:
                                    row_num = c
                                    break
                                break  # next cell is not diameter, stop
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

                    if row_num and diam and reading is not None:
                        cml_base = diam_to_cml.get(diam)
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


def _run_ocr_on_page(page_image: bytes) -> str:
    """Run OCR on a page image. Returns extracted text."""
    try:
        import pytesseract
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(page_image))
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def _extract_with_ocr(pdf_path: Path) -> Tuple[str, List[float], List[str], str]:
    """Fallback: render PDF pages to images and run OCR. Returns (date, readings, cml_ids, circuit)."""
    doc = pymupdf.open(pdf_path)
    full_text = ""
    all_readings = []

    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes(output="png")
        text = _run_ocr_on_page(img_bytes)
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

    # If pdfplumber got little, try OCR
    if not all_readings or len(full_text) < 100:
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
        except Exception:
            pass

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

    if not cml_ids and all_readings:
        cml_ids = ["1"]  # single CML

    circuit_base = _extract_circuit_base(circuit)
    date_str = date or ""

    # Try Acuren-style table parsing first (row-per-reading: 1.01-1, 1.05-2, etc.)
    acuren_results = _parse_acuren_results_table(pdf_path, circuit_base, cml_ids, date_str)
    if acuren_results:
        for r in acuren_results:
            r.source_file = source_filename
        return acuren_results

    results = []

    if not cml_ids:
        return results

    # Fallback: aggregate readings by CML (min per CML)
    if len(cml_ids) == 1:
        min_reading = min(all_readings) if all_readings else 0.0
        results.append(
            ExtractedReading(
                circuit_id=circuit,
                cml_id=cml_ids[0],
                measurement_date=date or "",
                min_reading=min_reading,
                all_readings=all_readings,
                source_file=source_filename,
            )
        )
    else:
        # Multiple CMLs: try to split readings by table sections
        # For now: assign min of all to each CML (conservative)
        # TODO: improve with spatial layout if needed
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
                    circuit_id=circuit,
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
