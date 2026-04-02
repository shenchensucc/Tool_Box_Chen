"""
Dig Package generation KPI checklist (development).

Remove this page and sidebar/Home links when the KPI pass/fail workflow is no longer needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_PAGE = Path(__file__).resolve()
_REPO_ROOT = _PAGE.parents[2]
_KPI_DIR = _REPO_ROOT / "tools" / "dig_package_kpi"
if str(_KPI_DIR) not in sys.path:
    sys.path.insert(0, str(_KPI_DIR))

sys.path.insert(0, str(_PAGE.parent.parent))

from chat_panel import render_floating_chat_shell
from frontend_utils import (
    apply_custom_styling,
    display_sidebar_navigation,
    get_layout_main,
    set_page_config,
)

try:
    import check_kpi as ck  # noqa: E402
except ImportError as e:
    ck = None  # type: ignore
    _import_err = e
else:
    _import_err = None

set_page_config("Dig Package KPI (Dev)", "🧪")
apply_custom_styling()
display_sidebar_navigation()

with_tests = False
if ck is not None:
    with st.sidebar:
        st.markdown("### KPI dev")
        with_tests = st.checkbox("Run pytest per KPI (slow)", value=False, key="kpi_with_tests")
        if st.button("Refresh scans", type="secondary"):
            ck.clear_kpi_caches()
            st.rerun()

main = get_layout_main()

with main:
    st.warning(
        "**Development-only page** — Tracks dig package template KPIs (~86 checks). "
        "Delete `pages/10_Dig_Package_KPI_Dev.py` and remove nav links when you no longer need it."
    )

    st.markdown("## 🧪 Dig Package KPI checklist")
    st.caption(
        "Static code checks against `backend/pipeline/dig_package.py` (and gates for Joint Summary). "
        "Optional pytest per row. Manual marks override automation for Excel/template verification."
    )

    if ck is None or _import_err is not None:
        st.error(f"Could not load KPI engine: {_import_err}")
        st.info("Install **PyYAML** (`pip install pyyaml` or `uv sync --extra dev`) and run from the repo root.")
        render_floating_chat_shell()
        st.stop()

    try:
        rows, summary = ck.build_report(with_tests=with_tests)
    except ImportError as e:
        st.error(str(e))
        render_floating_chat_shell()
        st.stop()
    except Exception as e:
        st.exception(e)
        render_floating_chat_shell()
        st.stop()

    # --- Top metrics ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Progress", f"{summary['percent']}%")
    c2.metric("PASS (effective)", summary["passed"])
    c3.metric("Skipped (manual)", summary["skipped"])
    c4.metric("Total KPIs", summary["total"])

    st.progress(min(float(summary["percent"]) / 100.0, 1.0))

    # --- Section rollup ---
    sec_rows = []
    by_sec: dict[str, list] = {}
    for r in rows:
        by_sec.setdefault(r["section"], []).append(r)
    for sec, lst in sorted(by_sec.items(), key=lambda x: x[0]):
        n = len(lst)
        p = sum(1 for x in lst if x["counts_pass"])
        sk = sum(1 for x in lst if str(x["effective"]).startswith("SKIP"))
        sec_rows.append(
            {
                "Section": sec,
                "KPIs": n,
                "PASS": p,
                "SKIP": sk,
                "Open": n - p - sk,
                "%": round(100.0 * p / n, 0) if n else 0.0,
            }
        )
    st.markdown("### By section")
    st.dataframe(pd.DataFrame(sec_rows), use_container_width=True, hide_index=True, height=min(420, 48 + 36 * len(sec_rows)))

    # --- Filters + full table ---
    st.markdown("### All KPI parameters")
    all_sections = sorted({r["section"] for r in rows})
    f1, f2 = st.columns(2)
    with f1:
        pick_sections = st.multiselect("Filter sections", options=all_sections, default=all_sections)
    with f2:
        eff_opts = sorted({r["effective"] for r in rows})
        pick_eff = st.multiselect("Filter effective status", options=eff_opts, default=eff_opts)

    filtered = [
        r
        for r in rows
        if r["section"] in pick_sections and r["effective"] in pick_eff
    ]
    show_detail = st.checkbox("Show detail column", value=False)

    df = pd.DataFrame(filtered)
    cols = ["id", "section", "name", "auto", "pytest", "manual", "effective"]
    if show_detail:
        cols.append("detail")
    df = df[[c for c in cols if c in df.columns]]

    h = min(720, 80 + min(len(filtered), 40) * 35)
    st.dataframe(df, use_container_width=True, hide_index=True, height=h)

    # --- Manual mark ---
    st.markdown("### Manual mark")
    st.caption(f"State file: `{ck.STATE_PATH.relative_to(_REPO_ROOT)}`")
    ids = [r["id"] for r in rows]
    m1, m2, m3 = st.columns([2, 1, 1])
    with m1:
        pick_id = st.selectbox("KPI id", ids, index=0)
    with m2:
        action = st.selectbox("Action", ["pass", "fail", "skip", "clear"])
    with m3:
        st.write("")
        st.write("")
        if st.button("Apply manual mark", type="primary"):
            state = ck.load_state()
            state.setdefault("manual", {})
            if action == "clear":
                state["manual"].pop(pick_id, None)
            else:
                state["manual"][pick_id] = action
            ck.save_state(state)
            ck.clear_kpi_caches()
            st.success(f"Saved `{pick_id}` → {action}")
            st.rerun()

    # --- Sync checklist doc ---
    st.markdown("### Update checklist markdown")
    if st.button("Write progress table into docs/DIG_PACKAGE_KPI_CHECKLIST.md"):
        try:
            s2 = ck.sync_doc_progress_table(with_tests=with_tests)
            st.success(f"Synced ({s2['percent']}%).")
        except (FileNotFoundError, ValueError) as e:
            st.error(str(e))

    st.markdown("---")
    st.caption(
        "CLI equivalent: `python tools/dig_package_kpi/check_kpi.py` · "
        "`python tools/dig_package_kpi/check_kpi.py sync-doc`"
    )

render_floating_chat_shell()
