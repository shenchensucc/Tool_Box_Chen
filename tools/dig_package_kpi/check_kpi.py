"""
Dig Package KPI checker — static code checks, optional pytest, manual marks.

Usage (from repo root):
  uv run python tools/dig_package_kpi/check_kpi.py
  uv run python tools/dig_package_kpi/check_kpi.py --with-tests
  uv run python tools/dig_package_kpi/check_kpi.py mark A-1 pass
  uv run python tools/dig_package_kpi/check_kpi.py sync-doc

Agent loop (KPI + layout verify → dev/dig_package_inspection/generated/):
  uv run python tools/dig_package_kpi/agent_loop.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path(__file__).resolve().parent / "kpi_registry.yaml"
STATE_PATH = Path(__file__).resolve().parent / "kpi_state.json"
KPI_DOC = REPO_ROOT / "docs" / "DIG_PACKAGE_KPI_CHECKLIST.md"
MARKERS = (
    "<!-- KPI_PROGRESS_AUTO_START -->",
    "<!-- KPI_PROGRESS_AUTO_END -->",
)


@dataclass
class KPIRow:
    id: str
    section_key: str
    section_title: str
    name: str
    checks: List[Dict[str, Any]] = field(default_factory=list)
    pytest: Optional[str] = None
    manual_only: bool = False
    gate: Optional[Dict[str, Any]] = None


def _load_yaml() -> dict:
    if yaml is None:
        raise ImportError(
            "PyYAML is required for the KPI registry. Install: pip install pyyaml (or uv sync --extra dev)"
        )
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def clear_kpi_caches() -> None:
    """Clear file text and pytest caches (call after code changes or 'Refresh')."""
    _file_cache.clear()
    _pytest_cache.clear()


def flatten_registry(raw: dict) -> List[KPIRow]:
    rows: List[KPIRow] = []
    sections = raw.get("sections", {})
    for section_key, block in sections.items():
        title = block.get("title", section_key)
        if section_key == "C":
            for item in block.get("items") or []:
                rows.append(
                    KPIRow(
                        id=item["id"],
                        section_key=section_key,
                        section_title=title,
                        name=item.get("name", item["id"]),
                        checks=[],
                        gate=item.get("gate"),
                    )
                )
            continue
        for item in block.get("items") or []:
            rows.append(
                KPIRow(
                    id=item["id"],
                    section_key=section_key,
                    section_title=title,
                    name=item.get("name", item["id"]),
                    checks=item.get("checks") or [],
                    pytest=item.get("pytest"),
                )
            )
    return rows


_file_cache: Dict[str, str] = {}


def _read_file(rel: str) -> str:
    if rel not in _file_cache:
        path = REPO_ROOT / rel
        if not path.is_file():
            _file_cache[rel] = ""
        else:
            _file_cache[rel] = path.read_text(encoding="utf-8", errors="replace")
    return _file_cache[rel]


def eval_checks(checks: List[Dict[str, Any]]) -> Tuple[bool, str]:
    if not checks:
        return False, "no checks"
    for ch in checks:
        t = ch.get("type")
        if t == "code_all":
            rel = ch["file"]
            text = _read_file(rel)
            missing = [s for s in ch["substrings"] if s not in text]
            if missing:
                return False, f"missing in {rel}: {missing[:3]!r}"
        elif t == "code_any":
            rel = ch["file"]
            text = _read_file(rel)
            if not any(s in text for s in ch["substrings"]):
                return False, f"none of {ch['substrings'][:3]} in {rel}"
        else:
            return False, f"unknown check type {t}"
    return True, "ok"


def eval_gate(gate: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """not_until_def: PASS when `def function_name` exists in file."""
    if not gate:
        return False, "no gate"
    if gate.get("type") != "not_until_def":
        return False, "unknown gate"
    rel = gate["file"]
    fn = gate["function"]
    text = _read_file(rel)
    if re.search(rf"^def\s+{re.escape(fn)}\s*\(", text, re.MULTILINE):
        return True, f"`def {fn}` present"
    return False, f"`def {fn}` not found (not implemented)"


def load_state() -> dict:
    if not STATE_PATH.is_file():
        return {"version": 1, "manual": {}, "notes": {}}
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


_pytest_cache: Dict[str, bool] = {}


def run_pytest_node(nodeid: str) -> bool:
    if nodeid in _pytest_cache:
        return _pytest_cache[nodeid]
    mod = "tests/test_dig_package.py"
    full = f"{mod}::{nodeid}"
    r = subprocess.run(
        [sys.executable, "-m", "pytest", full, "-q", "--tb=no"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    ok = r.returncode == 0
    _pytest_cache[nodeid] = ok
    return ok


def compute_row_status(
    row: KPIRow,
    with_tests: bool,
) -> Tuple[str, str, Optional[bool]]:
    """
    Returns (auto_label, detail, test_ok)
    auto_label: pass | fail | pending | n/a
    """
    if row.manual_only:
        return "n/a", "manual-only (template/product confirmation)", None

    if row.gate:
        ok, detail = eval_gate(row.gate)
        t_ok: Optional[bool] = None
        if with_tests and row.pytest:
            t_ok = run_pytest_node(row.pytest)
        elif with_tests:
            t_ok = None
        return ("pass" if ok else "fail", detail, t_ok)

    ok, detail = eval_checks(row.checks)
    t_ok = None
    if with_tests and row.pytest:
        t_ok = run_pytest_node(row.pytest)
        if t_ok and not ok:
            detail = detail + "; pytest OK"
        if not t_ok:
            detail = detail + "; pytest FAILED"

    if ok:
        return "pass", detail, t_ok
    if with_tests and row.pytest and t_ok:
        return "pass", detail, t_ok
    return "fail", detail, t_ok


def effective_status(auto: str, manual: Optional[str]) -> Tuple[str, bool]:
    """
    Returns (label, counts_for_pass_denominator).
    manual: pass|fail|skip|None
    """
    if manual == "skip":
        return "SKIP", False
    if manual == "pass":
        return "PASS✓", True
    if manual == "fail":
        return "FAIL✗", False
    if auto == "pass":
        return "PASS (auto)", True
    if auto == "n/a":
        return "PENDING (manual)", False
    if auto == "fail":
        return "FAIL (auto)", False
    return "PENDING", False


def aggregate(rows: List[dict]) -> Tuple[int, int, int, float]:
    """passed, skipped, total, percent (0-100)."""
    total = len(rows)
    skipped = sum(1 for r in rows if r["effective"].startswith("SKIP"))
    passed = sum(1 for r in rows if r["counts_pass"])
    denom = total - skipped
    pct = (100.0 * passed / denom) if denom else 0.0
    return passed, skipped, total, pct


def build_report(with_tests: bool) -> Tuple[List[dict], Dict[str, Any]]:
    raw = _load_yaml()
    flat = flatten_registry(raw)
    state = load_state()
    manual_map = state.get("manual") or {}

    out: List[dict] = []
    for row in flat:
        auto, detail, test_ok = compute_row_status(row, with_tests=with_tests)
        m = manual_map.get(row.id)
        eff_label, counts = effective_status(auto, m)
        if test_ok is True:
            pytest_cell = "PASS"
        elif test_ok is False:
            pytest_cell = "FAIL"
        else:
            pytest_cell = "—"
        out.append(
            {
                "id": row.id,
                "section_key": row.section_key,
                "section": row.section_title,
                "name": row.name,
                "auto": auto,
                "detail": detail,
                "pytest": pytest_cell,
                "manual": m if m else "",
                "effective": eff_label,
                "counts_pass": counts,
            }
        )

    passed, skipped, total, pct = aggregate(out)
    summary = {
        "passed": passed,
        "skipped": skipped,
        "total": total,
        "percent": round(pct, 1),
        "with_tests": with_tests,
    }
    return out, summary


def cmd_report(args: argparse.Namespace) -> None:
    rows, summary = build_report(with_tests=args.with_tests)
    print(f"\n=== Dig Package KPI Progress: {summary['percent']}% "
          f"({summary['passed']}/{summary['total'] - summary['skipped']} counted, "
          f"{summary['skipped']} skipped) ===\n")
    if args.with_tests:
        print("(pytest nodeids run per KPI where configured)\n")
    cur_section = None
    for r in rows:
        if r["section"] != cur_section:
            cur_section = r["section"]
            print(f"\n--- {cur_section} ---")
        line = f"  {r['id']:<6} {r['effective']:<16} auto={r['auto']:<6} {r['name'][:55]}"
        print(line)
        if args.verbose and r["detail"]:
            print(f"         {r['detail'][:120]}")
    print(f"\nOverall: {summary['percent']}% complete (manual + auto pass)\n")


def cmd_mark(args: argparse.Namespace) -> None:
    state = load_state()
    state.setdefault("manual", {})
    k = args.kpi_id
    v = args.status
    if v == "clear":
        state["manual"].pop(k, None)
    else:
        state["manual"][k] = v
    save_state(state)
    print(f"Updated {k} -> {v!r} in {STATE_PATH}")


def render_doc_table(rows: List[dict], summary: Dict[str, Any]) -> str:
    """Markdown block for DIG_PACKAGE_KPI_CHECKLIST.md"""
    lines = [
        "",
        f"> **Auto-generated** by `tools/dig_package_kpi/check_kpi.py sync-doc`. "
        f"**Overall progress: {summary['percent']}%** "
        f"({summary['passed']} PASS, {summary['total'] - summary['passed'] - summary['skipped']} open, "
        f"{summary['skipped']} SKIP).",
        "",
        "| Section | KPIs | PASS | SKIP | FAIL / PENDING | % |",
        "|---------|-----:|-----:|-----:|----------------|--:|",
    ]
    by_sec: Dict[str, List[dict]] = {}
    for r in rows:
        by_sec.setdefault(r["section"], []).append(r)

    for sec, sec_rows in by_sec.items():
        n = len(sec_rows)
        p = sum(1 for x in sec_rows if x["counts_pass"])
        sk = sum(1 for x in sec_rows if x["effective"].startswith("SKIP"))
        bad = n - p - sk
        spct = round(100.0 * p / n, 0) if n else 0
        lines.append(
            f"| {sec} | {n} | {p} | {sk} | {bad} | {spct:.0f}% |"
        )
    lines.append(
        f"| **TOTAL** | **{summary['total']}** | **{summary['passed']}** | **{summary['skipped']}** | "
        f"**{summary['total'] - summary['passed'] - summary['skipped']}** | **{summary['percent']}%** |"
    )
    lines.append("")
    return "\n".join(lines)


def sync_doc_progress_table(with_tests: bool) -> Dict[str, Any]:
    """
    Rewrite the auto-progress block in DIG_PACKAGE_KPI_CHECKLIST.md.
    Raises FileNotFoundError / ValueError on failure (safe for Streamlit).
    """
    rows, summary = build_report(with_tests=with_tests)
    block = render_doc_table(rows, summary)
    if not KPI_DOC.is_file():
        raise FileNotFoundError(str(KPI_DOC))
    text = KPI_DOC.read_text(encoding="utf-8")
    if MARKERS[0] not in text or MARKERS[1] not in text:
        raise ValueError(
            f"Markers not found in {KPI_DOC}; expected {MARKERS[0]} ... {MARKERS[1]}"
        )
    pre, rest = text.split(MARKERS[0], 1)
    _, post = rest.split(MARKERS[1], 1)
    new_text = pre + MARKERS[0] + block + "\n" + MARKERS[1] + post
    KPI_DOC.write_text(new_text, encoding="utf-8")
    return summary


def cmd_sync_doc(args: argparse.Namespace) -> None:
    try:
        summary = sync_doc_progress_table(with_tests=args.with_tests)
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(f"Updated progress table in {KPI_DOC} ({summary['percent']}%)")


def main() -> None:
    p = argparse.ArgumentParser(description="Dig Package KPI checker")
    p.add_argument("--with-tests", action="store_true", help="Run pytest nodeids (slower)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=False)

    sub.add_parser("report", help="Print KPI status (default if no subcommand)")

    mk = sub.add_parser("mark", help="Set manual status for a KPI id")
    mk.add_argument("kpi_id", help="e.g. A-1, C-3, U-1")
    mk.add_argument("status", choices=["pass", "fail", "skip", "clear"])

    sub.add_parser("sync-doc", help="Inject progress table into DIG_PACKAGE_KPI_CHECKLIST.md")

    args = p.parse_args()
    if args.cmd is None:
        args.cmd = "report"
    if args.cmd == "report":
        cmd_report(args)
    elif args.cmd == "mark":
        cmd_mark(args)
    elif args.cmd == "sync-doc":
        cmd_sync_doc(args)


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
