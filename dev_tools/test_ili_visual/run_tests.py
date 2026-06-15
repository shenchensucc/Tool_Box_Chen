"""
ILI Visual Tool — test runner.

Uploads each test file to the running backend and checks the response against
the expectations in test_cases.json.  All assertions are soft (logged, not
raised), so every case runs even when earlier ones fail.

Usage
-----
  # Start backend first:
  uvicorn backend.main:app --reload

  # Then in a second terminal:
  python dev_tools/test_ili_visual/run_tests.py

  # Run only specific cases by ID:
  python dev_tools/test_ili_visual/run_tests.py pipe_tally_209_240_manual dig_correlation_sheet

  # Save a markdown report:
  python dev_tools/test_ili_visual/run_tests.py --report report.md

Iteration workflow
------------------
1. Run this script  →  see FAIL lines
2. Look at the "Actual columns detected" block in the output
3. Add missing column name variants to COLUMN_KEYWORDS in ili_reader.py
4. Restart the backend  →  re-run  →  repeat until green
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    sys.exit("httpx is required.  Run:  pip install httpx")

# ── Paths ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
CASES_FILE = HERE / "test_cases.json"

# ── ANSI colours (disabled on Windows when not supported) ──────────────────
_USE_COLOUR = sys.stdout.isatty() and sys.platform != "win32"


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text


GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
BOLD   = lambda t: _c("1",  t)
DIM    = lambda t: _c("2",  t)


# ── Result accumulator ─────────────────────────────────────────────────────
class Result:
    def __init__(self, case_id: str, description: str):
        self.case_id     = case_id
        self.description = description
        self.checks:  list[tuple[bool, str]] = []   # (passed, message)
        self.info:    list[str]              = []    # informational lines
        self.skipped  = False
        self.error:   str | None            = None

    def ok(self, msg: str):
        self.checks.append((True, msg))

    def fail(self, msg: str):
        self.checks.append((False, msg))

    def note(self, msg: str):
        self.info.append(msg)

    @property
    def passed(self) -> bool:
        return not self.skipped and self.error is None and all(ok for ok, _ in self.checks)

    @property
    def n_pass(self) -> int:
        return sum(1 for ok, _ in self.checks if ok)

    @property
    def n_fail(self) -> int:
        return sum(1 for ok, _ in self.checks if not ok)


# ── Health check ───────────────────────────────────────────────────────────
def check_backend(base_url: str) -> bool:
    try:
        r = httpx.get(f"{base_url}/health", timeout=5.0)
        return r.status_code == 200 and r.json().get("ok", False)
    except Exception:
        return False


# ── Preview endpoint ───────────────────────────────────────────────────────
def call_preview(base_url: str, file_path: Path) -> dict[str, Any] | None:
    url = f"{base_url}/api/ili/preview"
    try:
        with file_path.open("rb") as fh:
            r = httpx.post(
                url,
                files={"file": (file_path.name, fh, _mime(file_path))},
                timeout=180.0,
            )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return {"_error": str(exc)}


# ── Process-feature-map endpoint ───────────────────────────────────────────
def call_process(
    base_url: str,
    file_path: Path,
    mode: str,
    sheet_name: str | None,
    vendor_format: str | None,
    data_format_override: str | None,
) -> dict[str, Any]:
    url = f"{base_url}/api/ili/process-feature-map"
    data: dict[str, str] = {}
    if mode == "vendor_auto" and vendor_format:
        data["vendor_format"] = vendor_format
    elif mode == "manual_sheet" and sheet_name:
        data["sheet_name"] = sheet_name
    else:
        return {"success": False, "error": f"Invalid mode/params: mode={mode!r}"}

    if data_format_override and data_format_override != "auto":
        data["data_format"] = data_format_override

    try:
        with file_path.open("rb") as fh:
            r = httpx.post(
                url,
                files={"file": (file_path.name, fh, _mime(file_path))},
                data=data,
                timeout=600.0,
            )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _mime(p: Path) -> str:
    return (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if p.suffix.lower() == ".xlsx"
        else "application/vnd.ms-excel"
    )


# ── Single test-case runner ────────────────────────────────────────────────
def run_case(base_url: str, tc: dict[str, Any]) -> Result:
    res = Result(tc["id"], tc.get("description", ""))

    if tc.get("skip"):
        res.skipped = True
        res.note("Skipped (skip=true in test_cases.json)")
        return res

    file_path = Path(tc["file_path"])
    if not file_path.exists():
        res.error = f"File not found: {file_path}"
        return res

    mode              = tc.get("mode", "manual_sheet")
    sheet_name        = tc.get("sheet_name")
    vendor_format     = tc.get("vendor_format")
    df_override       = tc.get("data_format_override", "auto")
    expected          = tc.get("expected", {})

    # ── Step 1: preview (informational only) ──────────────────────────────
    preview = call_preview(base_url, file_path)
    if "_error" not in preview:
        sheets = preview.get("sheet_names", [])
        res.note(f"Sheets in workbook: {sheets}")
        if sheet_name and sheet_name not in sheets:
            res.fail(f"Sheet '{sheet_name}' not found in workbook (available: {sheets})")
            return res
        if sheet_name:
            cols = preview.get("columns", {}).get(sheet_name, [])
            rows = preview.get("row_counts", {}).get(sheet_name, "?")
            res.note(f"Sheet '{sheet_name}': {rows} rows, columns: {cols}")
    else:
        res.note(f"Preview failed (non-fatal): {preview['_error']}")

    # ── Step 2: process feature map ───────────────────────────────────────
    resp = call_process(base_url, file_path, mode, sheet_name, vendor_format, df_override)

    # ── success ───────────────────────────────────────────────────────────
    expect_success = expected.get("success", True)
    got_success    = bool(resp.get("success"))
    if expect_success:
        if got_success:
            res.ok("success=true")
        else:
            err = resp.get("error", "(no error message)")
            res.fail(f"Expected success but got error: {err}")
            return res   # nothing else to check
    else:
        if not got_success:
            res.ok("Expected failure confirmed")
        else:
            res.fail("Expected failure but got success=true")

    if not got_success:
        return res

    # ── data_format ───────────────────────────────────────────────────────
    actual_fmt = resp.get("data_format", "anomaly")
    res.note(f"Detected data_format: {actual_fmt!r}")
    if "data_format" in expected:
        exp_fmt = expected["data_format"]
        if actual_fmt == exp_fmt:
            res.ok(f"data_format={actual_fmt!r}")
        else:
            res.fail(f"data_format: expected {exp_fmt!r}, got {actual_fmt!r}")

    # ── row count ─────────────────────────────────────────────────────────
    total_rows = resp.get("total_rows", 0)
    res.note(f"total_rows: {total_rows}")
    if "min_rows" in expected:
        if total_rows >= expected["min_rows"]:
            res.ok(f"total_rows={total_rows} >= {expected['min_rows']}")
        else:
            res.fail(f"total_rows={total_rows} < min_rows={expected['min_rows']}")

    # ── column mapping ────────────────────────────────────────────────────
    col_map = resp.get("column_mapping", {})
    res.note(f"Column mapping: {col_map}")

    for key in expected.get("column_keys_required", []):
        if col_map.get(key):
            res.ok(f"column '{key}' → '{col_map[key]}'")
        else:
            res.fail(f"Required column key '{key}' not detected (not in column_mapping)")

    for key in expected.get("column_keys_preferred", []):
        if col_map.get(key):
            res.ok(f"column '{key}' → '{col_map[key]}' (preferred)")
        else:
            res.note(f"  Preferred column key '{key}' not detected — consider adding keyword")

    # ── girth welds ───────────────────────────────────────────────────────
    scatter = resp.get("scatter_data") or {}
    girth_welds = scatter.get("girth_welds", [])
    seam_welds  = scatter.get("seam_welds", [])
    gwd_numbers = resp.get("gwd_numbers", [])

    res.note(f"girth_welds: {len(girth_welds)}, seam_welds: {len(seam_welds)}, gwd_numbers: {len(gwd_numbers)}")
    if gwd_numbers:
        res.note(f"  GWD range: {min(gwd_numbers)} – {max(gwd_numbers)}")
    if girth_welds:
        sample = girth_welds[:3]
        res.note(f"  Sample girth welds: {sample}")
    if seam_welds:
        sample = seam_welds[:2]
        res.note(f"  Sample seam welds: {sample}")

    exp_gw = expected.get("has_girth_welds")
    if exp_gw is True:
        if girth_welds:
            res.ok(f"has_girth_welds ({len(girth_welds)} found)")
        else:
            res.fail("Expected girth_welds but none found")
    elif exp_gw == "any":
        res.note("has_girth_welds: any (informational only)")

    exp_sw = expected.get("has_seam_welds")
    if exp_sw is True:
        if seam_welds:
            res.ok(f"has_seam_welds ({len(seam_welds)} found)")
        else:
            res.fail("Expected seam_welds but none found")
    elif exp_sw == "any":
        res.note("has_seam_welds: any (informational only)")

    # ── feature sample ────────────────────────────────────────────────────
    features = resp.get("features", [])
    if features:
        sample = features[0]
        # Strip private/internal keys for display
        clean = {k: v for k, v in sample.items() if not k.startswith("_")}
        res.note(f"First feature (sample): {json.dumps(clean, default=str)[:400]}")

    return res


# ── Report printer ─────────────────────────────────────────────────────────
def print_report(results: list[Result], report_path: Path | None = None) -> None:
    lines: list[str] = []

    def _line(s: str = "") -> None:
        lines.append(s)
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode("ascii", errors="replace").decode("ascii"))

    _line()
    _line(BOLD("=" * 72))
    _line(BOLD("  ILI Visual Tool — Test Report"))
    _line(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _line(BOLD("=" * 72))

    for res in results:
        icon = (
            DIM("⏭  SKIP")
            if res.skipped
            else (GREEN("✅ PASS") if res.passed else RED("❌ FAIL"))
            if res.error is None
            else RED("💥 ERROR")
        )
        _line()
        _line(f"{icon}  {BOLD(res.case_id)}  —  {res.description}")

        if res.error:
            _line(f"   {RED('ERROR:')} {res.error}")
        elif res.skipped:
            _line(f"   {DIM(res.info[0] if res.info else 'skipped')}")
        else:
            for ok, msg in res.checks:
                sym = GREEN("  ✓") if ok else RED("  ✗")
                _line(f"{sym} {msg}")
            if res.info:
                _line(DIM("  ── info ──"))
                for line in res.info:
                    _line(DIM(f"    {line}"))
            _line(f"   {res.n_pass} passed, {res.n_fail} failed")

    _line()
    _line(BOLD("─" * 72))
    total   = len(results)
    passed  = sum(1 for r in results if r.passed)
    failed  = sum(1 for r in results if not r.passed and not r.skipped and r.error is None)
    errors  = sum(1 for r in results if r.error)
    skipped = sum(1 for r in results if r.skipped)
    _line(
        f"  Total: {total}  "
        + GREEN(f"Passed: {passed}  ")
        + RED(f"Failed: {failed}  ")
        + YELLOW(f"Errors: {errors}  ")
        + DIM(f"Skipped: {skipped}")
    )
    _line(BOLD("=" * 72))
    _line()

    if report_path:
        # Write plain-text version (strip ANSI for markdown)
        import re
        plain = "\n".join(re.sub(r"\033\[[0-9;]*m", "", l) for l in lines)
        report_path.write_text(plain, encoding="utf-8")
        print(f"Report saved → {report_path}")


# ── Iteration guidance ─────────────────────────────────────────────────────
def print_fix_hints(results: list[Result]) -> None:
    failed = [r for r in results if not r.passed and not r.skipped and r.error is None]
    if not failed:
        return
    print(BOLD("\n── How to fix failures ──────────────────────────────────────────"))
    for res in failed:
        if any("not detected" in m for _, m in res.checks if not _ok):
            print(
                f"\n{res.case_id}: column detection failed.\n"
                "  → Find the actual column names in the 'info' block above.\n"
                "  → Add them to COLUMN_KEYWORDS in backend/pipeline/ili_reader.py\n"
                "  → Restart the backend and re-run this script."
            )
        if any("data_format" in m for ok, m in res.checks if not ok):
            print(
                f"\n{res.case_id}: wrong data_format detected.\n"
                "  → Check detect_data_format() in backend/pipeline/ili_reader.py\n"
                "  → Add column keywords that are unique to the correct format.\n"
                "  → Or set data_format_override explicitly in test_cases.json."
            )
    print()

# silence linter warning for unused variable in loop
_ok = True


# ── Entry point ────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Run ILI Visual Tool tests against a live backend.")
    parser.add_argument("case_ids", nargs="*", help="Run only these case IDs (default: all)")
    parser.add_argument("--report", metavar="FILE", help="Save a markdown/text report to FILE")
    parser.add_argument("--backend", default=None, help="Override backend URL")
    args = parser.parse_args()

    spec = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    base_url = args.backend or spec.get("backend_url", "http://127.0.0.1:8000")
    cases = spec["test_cases"]

    if args.case_ids:
        cases = [c for c in cases if c["id"] in args.case_ids]
        if not cases:
            sys.exit(f"No cases matched IDs: {args.case_ids}")

    # ── Backend health check ───────────────────────────────────────────────
    print(f"Checking backend at {base_url} …")
    if not check_backend(base_url):
        sys.exit(
            f"\n{RED('Backend not reachable')} at {base_url}\n\n"
            "Start the backend first:\n"
            "  uvicorn backend.main:app --reload\n"
            "\nThen re-run this script."
        )
    print(GREEN(f"Backend OK — running {len(cases)} test case(s)\n"))

    results: list[Result] = []
    for tc in cases:
        try:
            print(f"  Running: {tc['id']} \u2026", end=" ", flush=True)
        except UnicodeEncodeError:
            print(f"  Running: {tc['id']} ...", end=" ", flush=True)
        res = run_case(base_url, tc)
        tag = "SKIP" if res.skipped else ("PASS" if res.passed else ("ERROR" if res.error else "FAIL"))
        print(tag)
        results.append(res)

    report_path = Path(args.report) if args.report else None
    print_report(results, report_path)
    print_fix_hints(results)

    any_fail = any(not r.passed and not r.skipped for r in results)
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
