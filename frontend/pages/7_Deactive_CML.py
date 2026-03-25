import sys
from pathlib import Path

import httpx
import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    BACKEND_URL,
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell


def _show_debug_error(title: str, status_code: int, detail: str, endpoint: str):
    """Show detailed error info for debugging."""
    st.error(f"❌ **{title}** (HTTP {status_code})")
    st.markdown(f"**Endpoint:** `{endpoint}`")
    st.markdown(f"**Status:** {status_code}")
    if status_code == 404:
        st.warning("404 Not Found — Is the backend running? Did you restart it after adding new endpoints?")
    st.markdown("**Detail:**")
    st.code(str(detail), language="text")

# Page configuration
set_page_config("De-active CML", "🔴")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

main = get_layout_main()

with main:
    # Header
    display_header(
        "🔴 De-active CML",
        "Generate a dataloader to deactivate all CMLs in your uploaded sheet",
    )

    # Check backend status
    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    # Privacy notice
    st.info("🔒 **Privacy Notice:** Files are processed in memory only and are not stored on the server.")

    # Flow-chart style layout
    st.markdown("### 📋 Process Flow")

    # Step 1: Upload
    with st.container():
        st.markdown("**Step 1 — Upload Source File**")
        source_file = st.file_uploader(
            "Source Excel File",
            type=["xlsx", "xls"],
            help="Excel file with sheet 'Source_Data' containing Equipment ID, CML Group ID, sub-CML ID",
            key="deactive_source",
            on_change=lambda: st.session_state.pop("deactive_result", None),
        )

    # Optional template
    with st.expander("⚙️ Optional: Custom Template", expanded=False):
        st.caption("If not provided, the default TM_Loader_Template.xlsx from the system will be used.")
        template_file = st.file_uploader(
            "Template Excel File (TM_Loader.xlsx)",
            type=["xlsx", "xls"],
            help="Optional. Leave empty to use default template.",
            key="deactive_template",
            on_change=lambda: st.session_state.pop("deactive_result", None),
        )

    # Visual flow connector
    if source_file:
        st.markdown("⬇️")
    else:
        st.markdown("⬇️ *Upload a file to continue*")

    # Step 2: Process
    st.markdown("**Step 2 — Process**")
    process_btn = st.button(
        "🚀 Generate De-active Dataloader",
        type="primary",
        disabled=not source_file,
        key="deactive_process",
    )

    if process_btn and source_file:
        with st.spinner("⏳ Processing..."):
            try:
                files = {
                    "source_file": (
                        source_file.name,
                        source_file.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                }
                if template_file:
                    files["template_file"] = (
                        template_file.name,
                        template_file.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        f"{BACKEND_URL}/api/tml/deactivate-cml",
                        files=files,
                    )

                if response.status_code == 200:
                    result = response.json()
                    download_token = result.get("download_token")
                    output_filename = result.get("output_filename", "output_deactive.xlsx")

                    # Fetch file content
                    dl_response = httpx.get(
                        f"{BACKEND_URL}/api/tml/download/{download_token}",
                        timeout=60.0,
                    )
                    if dl_response.status_code == 200:
                        st.session_state.deactive_result = {
                            "output_data": dl_response.content,
                            "output_filename": output_filename,
                            "records_count": result.get("records_count", 0),
                        }
                    else:
                        _show_debug_error(
                            "Download failed",
                            dl_response.status_code,
                            dl_response.text,
                            f"GET {BACKEND_URL}/api/tml/download/{{token}}",
                        )
                else:
                    try:
                        err_body = response.json()
                        detail = err_body.get("detail", str(err_body))
                        if isinstance(detail, list):
                            detail = "\n".join(str(d) for d in detail)
                    except Exception:
                        detail = response.text or "No response body"
                    _show_debug_error(
                        "Process failed",
                        response.status_code,
                        str(detail),
                        f"POST {BACKEND_URL}/api/tml/deactivate-cml",
                    )

            except httpx.TimeoutException:
                st.error("❌ Request timed out. Try a smaller file or check backend.")
            except httpx.ConnectError as e:
                st.error(f"❌ Could not connect to backend at `{BACKEND_URL}`. Is it running?")
                st.code(str(e), language="text")
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {str(e)}")
                import traceback
                with st.expander("🔍 Full traceback"):
                    st.code(traceback.format_exc(), language="text")

    # Step 3: Download
    st.markdown("**Step 3 — Download**")
    if "deactive_result" in st.session_state:
        res = st.session_state.deactive_result
        st.success(f"✅ Deactivated **{res['records_count']}** CML(s)")
        st.download_button(
            label=f"📥 Download {res['output_filename']}",
            data=res["output_data"],
            file_name=res["output_filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="deactive_download",
        )
    else:
        st.caption("Output will appear here after processing.")

    # Help section
    st.divider()
    with st.expander("ℹ️ Help"):
        st.markdown("""
        **Required columns** (flexible naming supported):
        - Equipment ID (aliases: Equipment #, Equip ID)
        - CML Group ID (aliases: CML Group, TML Group ID)
        - sub-CML ID (aliases: Sub CML ID, TML_ID, TML ID, CML ID, CML_ID)

        **Sheet:** Auto-detects — tries "Source_Data" first, then any sheet with required columns.

        **Output:** `{your_filename}_deactive.xlsx` with Status Indicator = "Inactive" for all CMLs.
        """)

    st.caption("De-active CML | Chen's Engineer Toolbox")

render_floating_chat_shell()
