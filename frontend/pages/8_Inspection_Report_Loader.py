import base64
import sys
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    BACKEND_URL,
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    get_layout_with_chat,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_chat_expander

# Page configuration
set_page_config("Inspection Report Loader", "📄")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

cols, chat_visible = get_layout_with_chat()
left_col, right_col = cols

with left_col:
    display_header(
        "📄 Inspection Report Loader",
        "Upload UT inspection report PDFs to read summaries or generate APM dataloader",
    )

    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    st.info("🔒 **Privacy Notice:** Files are processed in memory only and are not stored on the server.")

    st.markdown("### 📋 Process Flow")

    # Step 1: PDFs (required for both actions)
    st.markdown("**Step 1 — Upload Inspection Report PDFs**")
    pdf_files = st.file_uploader(
        "UT Inspection Report PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="One or more UT thickness inspection report PDFs (e.g. Acuren format)",
        key="insp_pdfs",
        on_change=lambda: st.session_state.pop("insp_result", None),
    )

    # Step 2: Optional source Excel (for Generate Dataloader with full Equipment ID mapping)
    with st.expander("📎 Optional: Source Excel (Circuit → Equipment ID)", expanded=False):
        st.caption("If provided, Equipment IDs are mapped. If not, dataloader will use 'Need Add Equipment ID'—edit in Excel before APM upload.")
        source_file = st.file_uploader(
            "Source Excel File",
            type=["xlsx", "xls"],
            help="Sheet 'Source_Data' with Circuit ID and Equipment ID columns",
            key="insp_source",
            on_change=lambda: st.session_state.pop("insp_result", None),
        )

    st.markdown("**Step 2 — Choose Action**")
    col_read, col_gen = st.columns(2)

    with col_read:
        read_btn = st.button(
            "📖 Read Reports",
            type="primary",
            disabled=not pdf_files,
            key="insp_read",
            use_container_width=True,
            help="Parse PDFs and show summary (Circuit, CML, Min Reading, Date). No dataloader.",
        )

    with col_gen:
        gen_btn = st.button(
            "🚀 Generate Dataloader",
            type="primary",
            disabled=not pdf_files,
            key="insp_process",
            use_container_width=True,
            help="Generate APM dataloader Excel. Use placeholder if no source Excel.",
        )

    def _format_error(response: httpx.Response, context: str) -> str:
        """Build detailed error message for debugging."""
        parts = [
            f"**{context}**",
            f"- URL: `{response.url}`",
            f"- Status: {response.status_code} {response.reason_phrase}",
        ]
        try:
            body = response.json()
            if isinstance(body, dict) and "detail" in body:
                d = body["detail"]
                if isinstance(d, list):
                    parts.append("- Detail (validation errors):")
                    for item in d[:5]:
                        parts.append(f"  • {item}")
                else:
                    parts.append(f"- Detail: {d}")
            else:
                parts.append(f"- Response: {str(body)[:500]}")
        except Exception:
            text = response.text[:500] if response.text else "(empty)"
            parts.append(f"- Body: {text}")
        if response.status_code == 404:
            parts.append("\n💡 **Tip:** Restart the backend server if you added new endpoints.")
        return "\n".join(parts)

    if read_btn and pdf_files:
        with st.spinner("⏳ Reading reports..."):
            try:
                url = f"{BACKEND_URL}/api/tml/inspection-report/read"
                files = [("pdf_files", (pf.name, pf.getvalue(), "application/pdf")) for pf in pdf_files]
                with httpx.Client(timeout=180.0) as client:
                    response = client.post(url, files=files)
                if response.status_code == 200:
                    result = response.json()
                    st.session_state.insp_result = result
                else:
                    err_msg = _format_error(response, "Read Reports failed")
                    st.error(f"❌ Read Reports failed (HTTP {response.status_code})")
                    with st.expander("🔍 Error details (for debugging)", expanded=True):
                        st.markdown(err_msg)
            except httpx.TimeoutException:
                st.error("❌ Request timed out. Try fewer or smaller PDFs.")
            except httpx.ConnectError as e:
                st.error(f"❌ Could not connect to backend at `{BACKEND_URL}`. Is the server running?")
                with st.expander("🔍 Error details", expanded=True):
                    st.code(str(e))
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {str(e)}")
                with st.expander("🔍 Full traceback", expanded=True):
                    import traceback
                    st.code(traceback.format_exc())

    if gen_btn and pdf_files:
        with st.spinner("⏳ Parsing PDFs and generating dataloader..."):
            try:
                url = f"{BACKEND_URL}/api/tml/inspection-report"
                files = [("pdf_files", (pf.name, pf.getvalue(), "application/pdf")) for pf in pdf_files]
                if source_file:
                    files.append((
                        "source_file",
                        (source_file.name, source_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ))
                with httpx.Client(timeout=180.0) as client:
                    response = client.post(url, files=files)
                if response.status_code == 200:
                    result = response.json()
                    st.session_state.insp_result = result
                else:
                    err_msg = _format_error(response, "Generate Dataloader failed")
                    st.error(f"❌ Generate Dataloader failed (HTTP {response.status_code})")
                    with st.expander("🔍 Error details (for debugging)", expanded=True):
                        st.markdown(err_msg)
            except httpx.TimeoutException:
                st.error("❌ Request timed out. Try fewer or smaller PDFs.")
            except httpx.ConnectError as e:
                st.error(f"❌ Could not connect to backend at `{BACKEND_URL}`. Is the server running?")
                with st.expander("🔍 Error details", expanded=True):
                    st.code(str(e))
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {str(e)}")
                with st.expander("🔍 Full traceback", expanded=True):
                    import traceback
                    st.code(traceback.format_exc())

    # Step 3: Summary & Download
    st.markdown("**Step 3 — Summary & Download**")
    if "insp_result" in st.session_state:
        res = st.session_state.insp_result
        success = res.get("success", False)
        summary = res.get("summary", [])
        table_evidence = res.get("table_evidence", [])
        records_count = res.get("records_count", 0)
        has_download = bool(res.get("download_token"))

        if success and summary:
            if has_download:
                st.success(f"✅ {res.get('message', '')}")
            else:
                st.success(f"✅ Read **{len(summary)}** CML(s) from reports. Use Generate Dataloader to create Excel.")
            st.subheader("📊 Summary Table")
            df = pd.DataFrame(summary)
            st.dataframe(df, use_container_width=True, hide_index=True)

            if table_evidence:
                evidence_by_id = {
                    item.get("table_image_id"): item
                    for item in table_evidence
                    if item.get("table_image_id")
                }
                rows_by_image = {}
                for row in summary:
                    image_id = row.get("Table Image ID")
                    if image_id:
                        rows_by_image.setdefault(image_id, []).append(row)

                st.subheader("🧾 Source Table Validation")
                st.caption(
                    "Each card shows the source table screenshot used for OCR/table parsing, "
                    "with the extracted rows mapped to that image."
                )
                for image_id, related_rows in rows_by_image.items():
                    evidence = evidence_by_id.get(image_id)
                    if not evidence:
                        continue
                    src_file = evidence.get("source_file") or "Unknown file"
                    src_page = evidence.get("source_page") or "?"
                    method = evidence.get("extraction_method") or "unknown"

                    with st.expander(
                        f"📷 {src_file} | Page {src_page} | {len(related_rows)} row(s) | {method}",
                        expanded=False,
                    ):
                        image_b64 = evidence.get("image_base64")
                        if image_b64:
                            try:
                                zoom_key = f"insp_zoom_{image_id}"
                                zoom_enabled = st.checkbox("Zoom image", value=False, key=zoom_key)
                                st.image(
                                    base64.b64decode(image_b64),
                                    caption=f"Table Image ID: {image_id}",
                                    width=None if zoom_enabled else 360,
                                    use_container_width=zoom_enabled,
                                )
                            except Exception:
                                st.warning(f"Could not render evidence image for `{image_id}`.")

                        validate_cols = [
                            "Circuit",
                            "CML",
                            "Min Reading",
                            "Date",
                            "Source File",
                            "Source Page",
                            "Extraction Method",
                        ]
                        st.dataframe(
                            pd.DataFrame(related_rows)[[c for c in validate_cols if c in related_rows[0]]],
                            use_container_width=True,
                            hide_index=True,
                        )

        elif success and records_count == 0:
            st.warning("⚠️ No records extracted. Check PDF format.")
            if summary:
                st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

        else:
            st.warning(res.get("message", res.get("error", "Processing completed with issues.")))

        if res.get("download_token") and records_count > 0:
            dl_response = httpx.get(
                f"{BACKEND_URL}/api/tml/download/{res['download_token']}",
                timeout=60.0,
            )
            if dl_response.status_code == 200:
                st.download_button(
                    label=f"📥 Download {res.get('output_filename', 'Inspection_Report_Dataloader.xlsx')}",
                    data=dl_response.content,
                    file_name=res.get("output_filename", "Inspection_Report_Dataloader.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    key="insp_download",
                )
    else:
        st.caption("Output will appear here after processing.")

    st.divider()
    with st.expander("ℹ️ Help & OCR vs LLM"):
        st.markdown("""
        ### How It Works

        1. **Read Reports**: Upload PDFs only → see summary (Circuit, CML, Min Reading, Date). No Excel needed.
        2. **Generate Dataloader**: Upload PDFs, optionally Source Excel. Without source, Equipment ID = "Need Add Equipment ID"—edit in Excel before APM upload.
        3. **Source Excel** (optional): Sheet `Source_Data` with **Circuit ID** and **Equipment ID** columns
        4. For each CML, the **minimum** thickness reading is used. Date from report header.

        ### OCR vs LLM

        **Python (pdfplumber + pytesseract)** is used because:
        - **Deterministic**: Same PDF → same output
        - **Fast & offline**: No API cost or latency
        - **Good for structured reports**: Acuren-style reports have consistent layout
        - **OCR fallback**: When table extraction fails, pages are rendered to images and OCR extracts text

        **LLM APIs** (e.g. GPT-4 Vision) could interpret ambiguous layouts but add cost, latency, and variability.
        For standardized UT reports, Python extraction is recommended. LLM could be added later for one-off odd formats.
        """)

    st.caption("Inspection Report Loader | Chen's Engineer Toolbox")

with right_col:
    render_chat_expander(right_col, chat_visible)
