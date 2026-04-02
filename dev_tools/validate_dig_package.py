"""
Validate dig package parser against ground truth JSON files.

Run: python dev_tools/validate_dig_package.py

Looks for ground truth in: dev_tools/ground_truth_data/dig_package/

Ground truth JSON format:
- source_files: { mdl, ili[], template }
- expected: { dig_ids: [...], dig_count: N }
- Files must exist in same folder as the JSON or in a subfolder
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.pipeline.dig_package import extract_dig_ids, parse_mdl_file
from backend.pipeline.ili_parse import parse_ili_file

GROUND_TRUTH_DIR = ROOT / "dev_tools" / "ground_truth_data" / "dig_package"


def find_file(filename: str, base_dir: Path, case_folder: str | None = None) -> Path | None:
    """Find file in case_folder, base_dir, ground_truth_data/dig_package, or project root."""
    search_dirs = []
    if case_folder:
        search_dirs.append(GROUND_TRUTH_DIR / case_folder)
    search_dirs.extend([base_dir, GROUND_TRUTH_DIR, ROOT])
    for d in search_dirs:
        p = d / filename
        if p.exists():
            return p
    return None


def validate_one(gt_path: Path) -> tuple[bool | None, str]:
    """
    Validate parser output against ground truth.
    Returns (True, msg) if pass, (False, msg) if fail, (None, msg) if skip.
    """
    with open(gt_path, encoding="utf-8") as f:
        gt = json.load(f)

    source_files = gt.get("source_files", {})
    expected = gt.get("expected", {})
    expected_dig_ids = set(expected.get("dig_ids", []))
    ili_formats = gt.get("ili_formats", ["Rosen-MFLA"])

    if not expected_dig_ids:
        return None, "No expected dig_ids in ground truth"

    base_dir = gt_path.parent
    case_folder = gt.get("case_folder")
    mdl_name = source_files.get("mdl", "")
    if not mdl_name:
        return False, "No mdl in source_files"

    mdl_path = find_file(mdl_name, base_dir, case_folder)
    if not mdl_path:
        return None, f"MDL file not found: {mdl_name}"

    # Parse MDL
    try:
        mdl_content = mdl_path.read_bytes()
        mdl_df, mdl_col_map = parse_mdl_file(mdl_content)
        got_dig_ids = set(extract_dig_ids(mdl_df, mdl_col_map))
    except Exception as e:
        return False, f"Parse error: {e}"

    ili_files = source_files.get("ili", [])
    if ili_files and len(ili_formats) != len(ili_files):
        return False, f"ILI format count {len(ili_formats)} does not match ILI file count {len(ili_files)}"
    for ili_name, ili_format in zip(ili_files, ili_formats):
        ili_path = find_file(ili_name, base_dir, case_folder)
        if not ili_path:
            return None, f"ILI file not found: {ili_name}"
        try:
            parse_ili_file(ili_path.read_bytes(), ili_format)
        except Exception as e:
            return False, f"ILI parse error ({ili_name}, {ili_format}): {e}"

    # Compare
    missing = expected_dig_ids - got_dig_ids
    extra = got_dig_ids - expected_dig_ids

    if missing:
        return False, f"Missing dig IDs: {sorted(missing)}"
    if extra:
        return False, f"Extra dig IDs: {sorted(extra)}"
    return True, f"OK ({len(got_dig_ids)} dig IDs, {len(ili_files)} ILI files parsed)"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate dig package parser against ground truth")
    args = parser.parse_args()

    print("Validating dig package parser against ground truth...")
    passed, failed, skipped = 0, 0, 0

    gt_files = sorted(GROUND_TRUTH_DIR.glob("*_ground_truth.json"))
    if not gt_files:
        print("No ground truth files in dev_tools/ground_truth_data/dig_package/")
        return 0

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

    print(f"\nResult: {passed} passed, {failed} failed, {skipped} skipped")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
