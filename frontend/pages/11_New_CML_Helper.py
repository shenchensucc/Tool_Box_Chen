"""
New CML Dataloader Helper — AI-assisted column mapping + TML batch generation.

Uses the same backend LLM stack as Chat (/api/chat credentials).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    BACKEND_URL,
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_session_privacy_banner,
    display_sidebar_navigation,
    fu_key,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell

LLM_OPTIONS = [
    ("grok-4-fast", "Grok-4-Fast (default)"),
    ("supermind-agent-v1", "Supermind Agent"),
    ("deepseek", "DeepSeek"),
    ("gpt-5", "GPT-5"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro"),
    ("gemini-3-flash-preview", "Gemini 3 Flash"),
    ("kimi-k2.5", "Kimi K2.5"),
]

WORKFLOW_LABELS = {
    1: "Sub-CML Status (deactivated)",
    2: "AER Flag",
    3: "Code Year T-Min Formula",
    4: "Design Code",
    5: "Material Specification",
    6: "Material Grade",
    7: "Design Temperature",
    8: "Piping Formula",
    9: "Outside Diameter",
    10: "NPS",
    11: "Schedule",
    12: "Design Pressure",
    13: "Temperature Coefficient",
    14: "Tnom",
    15: "Tmin",
    16: "Override Allowable Stress",
    17: "Allowable Stress",
    18: "Design Factor",
    19: "Joint Factor",
    20: "Location Factor",
}


set_page_config("New CML Helper", "✨")
apply_custom_styling()
display_sidebar_navigation()

main = get_layout_main()


def _mime_for(name: str) -> str:
    n = name.lower()
    if n.endswith(".csv"):
        return "text/csv"
    if n.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/vnd.ms-excel"


with main:
    display_header(
        "✨ New CML Dataloader Helper",
        "Upload spreadsheets, review an AI mapping plan, answer gaps, then generate TML outputs",
    )

    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    display_session_privacy_banner()

    if "new_cml_plan" not in st.session_state:
        st.session_state.new_cml_plan = None
    if "new_cml_uploads" not in st.session_state:
        st.session_state.new_cml_uploads = None
    if "new_cml_validation_errors" not in st.session_state:
        st.session_state.new_cml_validation_errors = []
    if "new_cml_gen_result" not in st.session_state:
        st.session_state.new_cml_gen_result = None

    st.markdown(
        """
        **Flow:** upload one or more `.csv` / `.xlsx` files → **Analyze** (profiles + AI plan) →
        adjust workflows / answer questions → **Apply answers** → upload TM_Loader template → **Generate**.
        Rows must end up with `AER_Status_CML` containing **Yes** (map a column or set a constant).
        """
    )

    uploaded = st.file_uploader(
        "Source files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key=fu_key("new_cml", "sources"),
        help="Same files must stay available until you click Generate (stored in session after Analyze).",
    )

    notes = st.text_area("Notes for the assistant", key=fu_key("new_cml", "notes"), height=90)

    model_id = st.selectbox(
        "Model",
        options=[x[0] for x in LLM_OPTIONS],
        format_func=lambda i: dict(LLM_OPTIONS)[i],
        key=fu_key("new_cml", "model"),
    )

    analyze = st.button("🔍 Analyze uploads", type="primary")

    if analyze:
        if not uploaded:
            st.warning("Upload at least one file.")
        else:
            with st.spinner("Analyzing files…"):
                try:
                    file_parts = []
                    uploads_snap = []
                    for uf in uploaded:
                        raw = uf.getvalue()
                        uploads_snap.append((uf.name, raw))
                        file_parts.append(("files", (uf.name, raw, _mime_for(uf.name))))
                    payload = {"notes": notes, "model": model_id}
                    with httpx.Client(timeout=180.0) as client:
                        r = client.post(
                            f"{BACKEND_URL}/api/tml/new-cml-helper/analyze",
                            files=file_parts,
                            data=payload,
                        )
                    if r.status_code != 200:
                        st.error(r.json().get("detail", r.text))
                    else:
                        data = r.json()
                        st.session_state.new_cml_plan = data.get("plan")
                        st.session_state.new_cml_uploads = uploads_snap
                        st.session_state.new_cml_validation_errors = []
                        st.session_state.new_cml_gen_result = None
                        if data.get("llm_error"):
                            st.warning(f"LLM issue: {data['llm_error']}")
                        st.success("Analyze complete.")
                        st.rerun()
                except httpx.TimeoutException:
                    st.error("Request timed out.")
                except Exception as e:
                    st.error(str(e))

    plan = st.session_state.new_cml_plan

    if plan:
        st.subheader("Plan")

        if plan.get("warnings"):
            for w in plan["warnings"]:
                st.caption(f"⚠️ {w}")

        st.markdown(plan.get("summary") or "_No summary._")

        wf_raw = plan.get("recommended_workflows") or []
        wf_default: list[int] = []
        for x in wf_raw:
            try:
                xi = int(x)
                if 1 <= xi <= 20:
                    wf_default.append(xi)
            except (TypeError, ValueError):
                continue
        wf_pick = st.multiselect(
            "Workflows to run",
            options=list(range(1, 21)),
            default=sorted(set(wf_default)),
            format_func=lambda i: f"{i:02d} — {WORKFLOW_LABELS[i]}",
            key=fu_key("new_cml", "wf_pick"),
        )
        plan["recommended_workflows"] = sorted(set(wf_pick))

        with st.expander("Column mapping & constants"):
            st.json(
                {
                    "primary_file_name": plan.get("primary_file_name"),
                    "primary_sheet_name": plan.get("primary_sheet_name"),
                    "column_mapping": plan.get("column_mapping"),
                    "constants_suggested": plan.get("constants_suggested"),
                    "missing_canonical_columns": plan.get("missing_canonical_columns"),
                }
            )

        answers: dict[str, str] = {}
        qs = plan.get("questions") or []
        if qs:
            st.subheader("Open questions")
            for q in qs:
                qid = q.get("id", "")
                prompt = q.get("prompt", "")
                fk = q.get("field_key") or ""
                hint = f" ({fk})" if fk else ""
                answers[qid] = st.text_input(f"{prompt}{hint}", key=fu_key("new_cml", f"q_{qid}"))

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ Apply answers"):
                body = {"plan": plan, "answers": {k: v for k, v in answers.items() if str(v).strip()}}
                try:
                    with httpx.Client(timeout=60.0) as client:
                        r = client.post(
                            f"{BACKEND_URL}/api/tml/new-cml-helper/refine",
                            json=body,
                        )
                    if r.status_code != 200:
                        st.error(r.json().get("detail", r.text))
                    else:
                        out = r.json()
                        st.session_state.new_cml_plan = out["plan"]
                        st.session_state.new_cml_validation_errors = out.get("validation_errors") or []
                        st.session_state.new_cml_gen_result = None
                        st.success("Plan updated.")
                        st.rerun()
                except Exception as e:
                    st.error(str(e))

        with col_b:
            if st.button("↺ Reset session plan"):
                st.session_state.new_cml_plan = None
                st.session_state.new_cml_uploads = None
                st.session_state.new_cml_validation_errors = []
                st.session_state.new_cml_gen_result = None
                st.rerun()

        errs = st.session_state.new_cml_validation_errors
        if errs:
            st.error("Validation: " + "; ".join(errs))
        else:
            st.success("Plan validates for spine columns + workflows.")

        st.divider()
        st.subheader("Generate")

        tpl = st.file_uploader(
            "TM_Loader template (.xlsx)",
            type=["xlsx", "xls"],
            key=fu_key("new_cml", "template"),
        )

        gen_click = st.button(
            "🚀 Generate TML outputs",
            disabled=bool(errs) or not tpl or not st.session_state.new_cml_uploads,
        )

        if gen_click:
            ups = st.session_state.new_cml_uploads
            cur_plan = st.session_state.new_cml_plan
            wf_csv = ",".join(map(str, sorted(set(cur_plan.get("recommended_workflows") or []))))
            try:
                file_parts = [
                    ("source_files", (name, raw, _mime_for(name))) for name, raw in ups
                ]
                file_parts.append(
                    (
                        "template_file",
                        (tpl.name, tpl.getvalue(), _mime_for(tpl.name)),
                    )
                )
                form = {"plan_json": json.dumps(cur_plan), "workflows": wf_csv}
                with st.spinner("Running TML batch…"):
                    with httpx.Client(timeout=300.0) as client:
                        r = client.post(
                            f"{BACKEND_URL}/api/tml/new-cml-helper/generate",
                            files=file_parts,
                            data=form,
                        )
                if r.status_code != 200:
                    st.error(r.json().get("detail", r.text))
                else:
                    result = r.json()
                    zip_token = result.get("zip_token")
                    combined_token = result.get("combined_token")
                    zip_data = combined_data = None
                    try:
                        zr = httpx.get(f"{BACKEND_URL}/api/tml/download/{zip_token}", timeout=120.0)
                        if zr.status_code == 200:
                            zip_data = zr.content
                    except Exception:
                        pass
                    try:
                        cr = httpx.get(f"{BACKEND_URL}/api/tml/download/{combined_token}", timeout=120.0)
                        if cr.status_code == 200:
                            combined_data = cr.content
                    except Exception:
                        pass
                    st.session_state.new_cml_gen_result = {
                        "result": result,
                        "zip_data": zip_data,
                        "combined_data": combined_data,
                        "template_name": tpl.name,
                    }
                    st.success("Done.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

        gen = st.session_state.new_cml_gen_result
        if gen:
            st.markdown(f"Template used: `{gen['template_name']}`")
            c1, c2 = st.columns(2)
            with c1:
                if gen.get("zip_data"):
                    st.download_button(
                        "⬇️ ZIP",
                        data=gen["zip_data"],
                        file_name="TML_Output.zip",
                        mime="application/zip",
                        key=fu_key("new_cml", "dl_zip"),
                    )
            with c2:
                if gen.get("combined_data"):
                    st.download_button(
                        "⬇️ Combined workbook",
                        data=gen["combined_data"],
                        file_name="TML_Combined_Output.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=fu_key("new_cml", "dl_combined"),
                    )

render_floating_chat_shell()
