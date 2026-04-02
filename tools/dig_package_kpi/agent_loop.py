#!/usr/bin/env python3
"""
Agent feedback loop for Dig Package development.

Runs KPI static checks, optional pytest, optional layout verify against a template,
and writes machine-readable + markdown reports under:
  dev/dig_package_inspection/generated/

Usage (repo root):
  python tools/dig_package_kpi/agent_loop.py
  python tools/dig_package_kpi/agent_loop.py --with-tests --template "path/to/template.xlsx"
  python tools/dig_package_kpi/agent_loop.py --sync-doc   # refresh KPI checklist table

Safe to delete: dev/dig_package_inspection/generated/agent_iteration*
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
_PKG = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(_PKG))

OUT_DIR = REPO / "dev" / "dig_package_inspection" / "generated"

_BUNDLED = (
    REPO
    / "backend"
    / "static"
    / "templates"
    / "dig_package"
    / "2026 Dig Package Template.xlsx"
)
_LEGACY = Path(
    r"C:\Users\cshen\Documents\Reference dig package\3-Dig Package Template\2026 Dig Package Template.xlsx"
)


def _resolve_template(cli: Optional[Path]) -> Tuple[Optional[Path], List[str]]:
    tried: List[str] = []
    for c in (
        cli,
        Path(os.environ.get("DIG_PACKAGE_TEMPLATE_PATH", "").strip()) if os.environ.get("DIG_PACKAGE_TEMPLATE_PATH") else None,
        _BUNDLED,
        _LEGACY,
    ):
        if c is None:
            continue
        p = Path(c)
        tried.append(str(p.resolve()))
        if p.is_file():
            return p, tried
    return None, tried


def _layout_verify(template: Optional[Path]) -> Dict[str, Any]:
    if template is None or not template.is_file():
        return {
            "skipped": True,
            "reason": "no_template",
            "results": [],
        }
    try:
        from openpyxl import load_workbook

        from backend.pipeline.dig_package_layout import load_layout_manifest, verify_layout_against_workbook

        wb = load_workbook(str(template), data_only=False)
        manifest = load_layout_manifest()
        results = verify_layout_against_workbook(wb, manifest)
        ok_n = sum(1 for r in results if r.get("ok"))
        return {
            "skipped": False,
            "template": str(template.resolve()),
            "total": len(results),
            "ok_count": ok_n,
            "fail_count": len(results) - ok_n,
            "results": results,
        }
    except Exception as e:
        return {"skipped": True, "reason": "error", "error": str(e), "results": []}


def _suggest_kpi_action(row: Dict[str, Any]) -> str:
    rid = row.get("id", "")
    if str(rid).startswith("C-"):
        return (
            "Joint Summary not implemented: add `populate_joint_summary()` in "
            "`backend/pipeline/dig_package.py` and wire it from `generate_dig_packages`."
        )
    detail = (row.get("detail") or "")[:200]
    return f"Fix static check or pytest for {rid}: {detail}"


def _suggest_layout_action(fail: Dict[str, Any]) -> str:
    fid = fail.get("field_id", "")
    err = fail.get("error", "")
    return (
        f"Update `backend/static/templates/dig_package/dig_package_layout.json` anchor for `{fid}` "
        f"to match label text in the real template. Error: {err}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-tests", action="store_true", help="Run pytest nodes (slow)")
    parser.add_argument("--template", type=Path, default=None, help="Dig Package .xlsx for layout verify")
    parser.add_argument(
        "--sync-doc",
        action="store_true",
        help="Update docs/DIG_PACKAGE_KPI_CHECKLIST.md progress table",
    )
    args = parser.parse_args()

    import check_kpi as ck

    generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows, summary = ck.build_report(with_tests=args.with_tests)

    template_path, tried_paths = _resolve_template(args.template)
    layout = _layout_verify(template_path)

    failed_kpi = [r for r in rows if not r.get("counts_pass")]
    layout_fails: List[Dict[str, Any]] = []
    if not layout.get("skipped") and layout.get("results"):
        layout_fails = [x for x in layout["results"] if not x.get("ok")]

    actions: List[Dict[str, str]] = []
    for r in failed_kpi:
        actions.append({"source": "kpi", "id": str(r.get("id")), "action": _suggest_kpi_action(r)})
    for lf in layout_fails:
        actions.append(
            {
                "source": "layout",
                "id": str(lf.get("field_id")),
                "action": _suggest_layout_action(lf),
            }
        )

    blocked_on_user = False
    blockers: List[str] = []
    if any(str(r.get("id", "")).startswith("C-") for r in failed_kpi):
        blockers.append(
            "Joint Summary (C-1..C-7) requires implementing `populate_joint_summary` — confirm scope with team."
        )
        blocked_on_user = True
    if layout_fails:
        blockers.append(
            "Layout anchors do not match your local `2026 Dig Package Template.xlsx` — confirm label wording in Excel."
        )
        blocked_on_user = True

    report: Dict[str, Any] = {
        "generated_at_utc": generated_utc,
        "kpi": {
            "summary": summary,
            "failed_ids": [r["id"] for r in failed_kpi],
            "rows": rows,
        },
        "layout_verify": layout,
        "template_paths_tried": tried_paths,
        "suggested_actions": actions,
        "blocked_on_user_input": blocked_on_user,
        "blockers": blockers,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "agent_iteration_report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md_lines = [
        "# Agent iteration report",
        "",
        f"- **UTC:** {generated_utc}",
        f"- **KPI progress:** {summary['percent']}% ({summary['passed']}/{summary['total'] - summary['skipped']} counted)",
        f"- **Layout verify:** "
        + (
            "skipped (no template)"
            if layout.get("skipped")
            else f"{layout.get('ok_count', 0)}/{layout.get('total', 0)} anchors OK"
        ),
        "",
        "## Suggested actions (auto)",
        "",
    ]
    if not actions:
        md_lines.append("_No failing checks — continue with feature work or run `--with-tests`._")
    else:
        for a in actions[:40]:
            md_lines.append(f"- **[{a['source']}] {a['id']}:** {a['action']}")
        if len(actions) > 40:
            md_lines.append(f"- _…and {len(actions) - 40} more (see agent_iteration_report.json)_")
    md_lines.extend(["", "## Blockers needing human input", ""])
    if blockers:
        for b in blockers:
            md_lines.append(f"- {b}")
    else:
        md_lines.append("_None flagged — or run with a real template path for layout coverage._")
    md_lines.append("")
    (OUT_DIR / "AGENT_ITERATION.md").write_text("\n".join(md_lines), encoding="utf-8")

    if args.sync_doc:
        try:
            s2 = ck.sync_doc_progress_table(with_tests=args.with_tests)
            print(f"sync-doc: updated checklist ({s2['percent']}%)")
        except (FileNotFoundError, ValueError) as e:
            print(f"sync-doc skipped: {e}", file=sys.stderr)

    print(f"Wrote {json_path}")
    print(f"Wrote {OUT_DIR / 'AGENT_ITERATION.md'}")
    print(f"KPI: {summary['percent']}%  failed rows: {len(failed_kpi)}  layout anchor fails: {len(layout_fails)}")
    return 0 if not failed_kpi and not layout_fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
