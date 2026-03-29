"""
Validate inspection report parser against ground truth JSON files.

Run: python dev_tools/validate_ground_truth.py

Looks for PDFs in:
- dev_tools/ground_truth_data/
- tests/fixtures/

Ground truth JSON must exist. PDF is located by source_file in the JSON.
To validate: place the PDF next to its ground_truth.json or in tests/fixtures/.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env for optional parser env overrides (e.g. OCR tuning)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.tml.inspection_report_parser import parse_inspection_report_pdf
from backend.tml.inspection_fixtures import FIXTURE_EXPECTED, FIXTURE_DIR

GROUND_TRUTH_DIR = ROOT / "dev_tools" / "ground_truth_data"
SEARCH_DIRS = [GROUND_TRUTH_DIR, FIXTURE_DIR]


def load_expected(gt_path: Path) -> dict:
    """Load expected (circuit, cml, reading) from ground truth: is_correct readings + additions."""
    with open(gt_path, encoding="utf-8") as f:
        gt = json.load(f)
    expected = {}
    for r in gt.get("readings", []):
        if r.get("is_correct"):
            key = (r["circuit_id"], r["cml_id"])
            expected[key] = r.get("expected_reading") or r["min_reading"]
    for a in gt.get("additions", []):
        key = (a["circuit_id"], a["cml_id"])
        expected[key] = a["min_reading"]
    return expected


def find_pdf(source_file: str) -> Path | None:
    """Find PDF by source_file in search dirs."""
    for d in SEARCH_DIRS:
        p = d / source_file
        if p.exists():
            return p
    return None


def validate_one(gt_path: Path) -> tuple[bool, str]:
    """Validate parser output against ground truth. Returns (ok, message)."""
    with open(gt_path, encoding="utf-8") as f:
        gt = json.load(f)
    source_file = gt.get("source_file", "")
    if not source_file:
        return False, "No source_file in ground truth"
    pdf_path = find_pdf(source_file)
    if not pdf_path:
        return None, f"PDF not found: {source_file}"  # None = skip
    expected = load_expected(gt_path)
    if not expected:
        return None, "No expected readings in ground truth"
    results = parse_inspection_report_pdf(pdf_path, source_file)
    got = {(r.circuit_id, r.cml_id): r.min_reading for r in results}
    errors = []
    for (circ, cml), exp_read in expected.items():
        if (circ, cml) not in got:
            errors.append(f"Missing {circ} {cml} (expected {exp_read})")
        elif abs(got[(circ, cml)] - exp_read) > 0.01:
            errors.append(f"{circ} {cml}: got {got[(circ, cml)]}, expected {exp_read}")
    if errors:
        return False, "; ".join(errors[:5]) + ("..." if len(errors) > 5 else "")
    return True, f"OK ({len(expected)} readings)"


def validate_fixture(pdf_name: str, pdf_path: Path) -> tuple[bool, str]:
    """Validate fixture using built-in expected."""
    expected_list = FIXTURE_EXPECTED.get(pdf_name)
    if not expected_list:
        return None, "No expected"
    results = parse_inspection_report_pdf(pdf_path, pdf_name)
    if len(results) != len(expected_list):
        return False, f"Got {len(results)} rows, expected {len(expected_list)}"
    for i, (circ, cml, read) in enumerate(expected_list):
        if i >= len(results):
            return False, f"Missing {circ} {cml}"
        r = results[i]
        if r.circuit_id != circ or r.cml_id != cml or abs(r.min_reading - read) > 0.01:
            return False, f"{circ} {cml}: got {r.min_reading}, expected {read}"
    return True, f"OK ({len(expected_list)} readings)"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate parser against ground truth")
    parser.add_argument("--fixtures-only", action="store_true", help="Run only legacy fixtures (52-021K, 57-008U from FIXTURE_EXPECTED)")
    args = parser.parse_args()

    print("Validating parser against ground truth...")
    passed, failed = 0, 0

    # Ground truth files (unified: includes consolidated fixtures)
    gt_files = sorted(GROUND_TRUTH_DIR.glob("*_ground_truth.json"))

    if args.fixtures_only:
        # Legacy mode: validate only the 2 fixtures from FIXTURE_EXPECTED
        for pdf_name in FIXTURE_EXPECTED:
            pdf_path = FIXTURE_DIR / pdf_name
            if pdf_path.exists():
                ok, msg = validate_fixture(pdf_name, pdf_path)
                if ok:
                    passed += 1
                    print(f"  PASS [fixture] {pdf_name[:50]}: {msg}")
                else:
                    failed += 1
                    print(f"  FAIL [fixture] {pdf_name[:50]}: {msg}")
        gt_files = []
    skipped = 0
    for gt_path in gt_files:
        name = gt_path.stem.replace("_ground_truth", "")
        result, msg = validate_one(gt_path)
        if result is None:
            skipped += 1
            print(f"  SKIP {name}: {msg}")
        elif result:
            passed += 1
            print(f"  PASS {name}: {msg}")
        else:
            failed += 1
            print(f"  FAIL {name}: {msg}")
    print(f"\nResult: {passed} passed, {failed} failed, {skipped} skipped (no PDF)")
    if not args.fixtures_only and not gt_files:
        print("No ground truth files in dev_tools/ground_truth_data/")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
