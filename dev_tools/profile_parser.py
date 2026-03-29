"""
Profile inspection report parser — shows where time is spent per stage.
Run from project root:  python dev_tools/profile_parser.py
"""
import sys, time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber
import pymupdf as fitz
import backend.tml.inspection_report_parser as _mod

# ── Instrument key functions ───────────────────────────────────────────────────
_timings: dict = {}

def _timed(name, fn):
    def wrapper(*a, **kw):
        t = time.perf_counter()
        r = fn(*a, **kw)
        _timings.setdefault(name, []).append(time.perf_counter() - t)
        return r
    return wrapper

# Patch heavy functions
_mod._extract_readings_from_tables   = _timed("pdfplumber_tables",   _mod._extract_readings_from_tables)
_mod._extract_readings_from_text     = _timed("pdfplumber_text",     _mod._extract_readings_from_text)
_mod._is_image_heavy_report          = _timed("is_image_heavy",      _mod._is_image_heavy_report)
_mod._extract_with_ocr               = _timed("tesseract_ocr",       _mod._extract_with_ocr)
_mod._extract_with_easyocr           = _timed("easyocr",             _mod._extract_with_easyocr)
_mod._extract_structured_with_local_ocr = _timed("structured_ocr",  _mod._extract_structured_with_local_ocr)
_mod._parse_acuren_results_table     = _timed("parse_acuren",        _mod._parse_acuren_results_table)
_mod._parse_generic_zone_table       = _timed("parse_generic",       _mod._parse_generic_zone_table)
_mod._parse_ut_report_summary_table  = _timed("parse_ut_summary",    _mod._parse_ut_report_summary_table)
_mod._parse_single_cml_permissive    = _timed("parse_permissive",    _mod._parse_single_cml_permissive)
_mod._get_summary_page_indices       = _timed("get_summary_pages",   _mod._get_summary_page_indices)
_mod._finalize_results               = _timed("finalize",            _mod._finalize_results)

from backend.tml.inspection_report_parser import parse_inspection_report_pdf, parse_inspection_report_pdfs

def run_pdf(pdf_path: Path):
    _timings.clear()
    t0 = time.perf_counter()
    results = parse_inspection_report_pdf(pdf_path)
    total = time.perf_counter() - t0

    print(f"\n{'='*64}")
    print(f"PDF: {pdf_path.name}")
    print(f"Total: {total:.2f}s   |   {len(results)} result(s)")

    # Show timings sorted by total time
    rows = [(name, sum(ts), len(ts)) for name, ts in _timings.items()]
    rows.sort(key=lambda x: x[1], reverse=True)
    print(f"\n{'Stage':<32} {'Total':>8} {'Calls':>6}")
    print("-" * 50)
    for name, tot, calls in rows:
        print(f"  {name:<30} {tot:>7.3f}s {calls:>5}x")

    if results:
        print("\nExtracted readings:")
        for r in results:
            print(f"  {r.circuit_id:12} {r.cml_id:10} reading={r.min_reading:.3f}  date={r.measurement_date}  method={r.extraction_method}")
    else:
        print("\n  !! NO RESULTS EXTRACTED !!")

# ── Run on ground truth PDFs ───────────────────────────────────────────────────
gt_dir    = Path("dev_tools/ground_truth_data")
fix_dir   = Path("tests/fixtures")

pdfs = sorted(list(gt_dir.glob("*.pdf")) + list(fix_dir.glob("*.pdf")))

if not pdfs:
    print("No PDFs found. Check dev_tools/ground_truth_data/ and tests/fixtures/")
    sys.exit(1)

print(f"Found {len(pdfs)} PDF(s) to profile\n")
for p in pdfs:
    run_pdf(p)

print("\n" + "="*64)
print("Done.")
