"""
Legacy standalone Streamlit entry for the KPI dashboard.

Prefer the main app: **frontend/pages/10_Dig_Package_KPI_Dev.py** (sidebar → Development).

  streamlit run tools/dig_package_kpi/dashboard.py

Run from repository root so imports resolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent
sys.path.insert(0, str(_PKG))

import check_kpi as ck  # noqa: E402

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dig Package KPI", layout="wide")
st.title("Dig Package KPI tracker")

with st.sidebar:
    st.markdown("### Options")
    with_tests = st.checkbox("Run pytest per KPI (slow)", value=False)
    if st.button("Refresh checks"):
        ck.clear_kpi_caches()

rows, summary = ck.build_report(with_tests=with_tests)

c1, c2, c3 = st.columns(3)
c1.metric("Progress", f"{summary['percent']}%")
c2.metric("PASS (effective)", summary["passed"])
c3.metric("Skipped (manual)", summary["skipped"])

st.progress(min(summary["percent"] / 100.0, 1.0))

st.caption(
    "Auto = static code checks; with pytest ON, a passing test can satisfy “runs OK” when code heuristics miss. "
    "Manual marks override auto for template/Excel verification."
)

df = pd.DataFrame(rows)
show = df[["id", "section", "name", "auto", "pytest", "manual", "effective"]].copy()
st.dataframe(show, use_container_width=True, hide_index=True, height=480)

st.markdown("### Manual mark")
col_a, col_b, col_c = st.columns([2, 1, 1])
ids = [r["id"] for r in rows]
with col_a:
    pick = st.selectbox("KPI id", ids, index=0)
with col_b:
    action = st.selectbox("Action", ["pass", "fail", "skip", "clear"])
with col_c:
    st.write("")
    st.write("")
    if st.button("Apply"):
        state = ck.load_state()
        state.setdefault("manual", {})
        if action == "clear":
            state["manual"].pop(pick, None)
        else:
            state["manual"][pick] = action
        ck.save_state(state)
        st.success(f"Saved {pick} → {action}")
        st.rerun()

st.markdown("### Update KPI doc")
if st.button("Write progress table into DIG_PACKAGE_KPI_CHECKLIST.md"):
    try:
        s2 = ck.sync_doc_progress_table(with_tests=with_tests)
        st.success(f"Synced ({s2['percent']}%). Re-open the markdown file to review.")
    except (FileNotFoundError, ValueError) as e:
        st.error(str(e))
