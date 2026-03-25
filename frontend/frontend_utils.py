import os
from typing import Any, Dict, Optional

import httpx
import streamlit as st

# Backend URL configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def apply_custom_styling():
    """Apply custom CSS styling to the Streamlit app with dark/light mode support"""
    st.markdown(
        """
        <style>
        /* Main container styling */
        .main {
            padding: 2rem;
        }

        /* Header styling - adaptive to theme */
        h1, h2, h3 {
            font-weight: 600;
        }

        /* Button styling - uses theme colors */
        .stButton button {
            border-radius: 8px;
            padding: 0.5rem 1.5rem;
            border: none;
            transition: all 0.3s ease;
            font-weight: 500;
        }

        .stButton button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        /* Primary button styling */
        .stButton button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .stButton button[kind="primary"]:hover {
            background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
        }

        /* File uploader styling - adaptive */
        [data-testid="stFileUploader"] {
            border: 2px dashed;
            border-color: var(--primary-color, #667eea);
            border-radius: 8px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }

        [data-testid="stFileUploader"]:hover {
            border-color: var(--primary-color, #764ba2);
            background-color: rgba(102, 126, 234, 0.05);
        }

        /* Info/Alert box styling */
        .stAlert {
            border-radius: 8px;
            border-left: 4px solid;
        }

        /* DataFrame styling - adaptive borders */
        .dataframe {
            border-radius: 8px;
            overflow: hidden;
        }

        /* Metric styling */
        [data-testid="stMetric"] {
            background-color: rgba(102, 126, 234, 0.05);
            padding: 1rem;
            border-radius: 8px;
            border: 1px solid rgba(102, 126, 234, 0.1);
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            border-radius: 8px;
            font-weight: 500;
        }

        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 0.5rem 1rem;
            font-weight: 500;
        }

        /* Sidebar improvements */
        [data-testid="stSidebar"] {
            padding-top: 2rem;
        }

        /* Hide default Streamlit navigation (we use custom navigation) */
        [data-testid="stSidebarNav"] {
            display: none;
        }

        /* Card-like containers */
        .element-container div[data-testid="stMarkdownContainer"] div {
            border-radius: 8px;
        }

        /* Plotly chart containers */
        .js-plotly-plot {
            border-radius: 8px;
        }

        /* Download button */
        .stDownloadButton button {
            border-radius: 8px;
            font-weight: 500;
        }

        /* Success/Error/Warning styling */
        .stSuccess, .stError, .stWarning, .stInfo {
            border-radius: 8px;
        }

        /* Smooth transitions */
        * {
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        /* Chat panel: sticky/floating when scrolling */
        [data-testid="stHorizontalBlock"] > div:last-child {
            position: sticky !important;
            top: 1rem !important;
            align-self: start !important;
        }

        /* Chat header with integrated hide button */
        .chat-header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .chat-header-row h4 {
            margin: 0;
            flex: 1;
        }
        .chat-hide-btn {
            padding: 0.25rem 0.5rem !important;
            min-width: auto !important;
            font-size: 0.85rem !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def set_page_config(page_title: str, page_icon: str = "🔧", layout: str = "wide"):
    """Set Streamlit page configuration"""
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout=layout)


def display_header(title: str, description: Optional[str] = None):
    """Display a formatted page header"""
    st.title(title)
    if description:
        st.markdown(f"*{description}*")
    st.markdown("---")


def display_session_privacy_banner() -> None:
    """
    High-visibility reminder that uploads/results are not persisted server-side
    (session-only in the browser).
    """
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #fef08a 0%, #fde047 50%, #facc15 100%);
            border: 2px solid #ca8a04;
            border-radius: 10px;
            padding: 14px 18px;
            margin: 0 0 1rem 0;
            font-size: 1.05rem;
            line-height: 1.45;
            font-weight: 600;
            color: #713f12;
            box-shadow: 0 3px 10px rgba(180, 83, 9, 0.35);
        ">
            <span style="font-size: 1.2rem;">🔒</span>
            <strong>Reminder:</strong>
            This app does not save your uploads or results on the server —
            everything stays in your current browser session only.
        </div>
        """,
        unsafe_allow_html=True,
    )


async def call_preview_api(file) -> Optional[Dict[str, Any]]:
    """Call the backend preview API"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file.name, file.getvalue(), file.type)}
            response = await client.post(f"{BACKEND_URL}/api/ili/preview", files=files)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        st.error(f"Error calling preview API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None


async def call_parse_paste_api(pasted_text: str) -> Optional[Dict[str, Any]]:
    """Call the backend parse-paste API for pasted ILI data"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            data = {"pasted_text": pasted_text}
            response = await client.post(f"{BACKEND_URL}/api/ili/parse-paste", data=data)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        st.error(f"Error calling parse API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None


async def call_process_api(
    file, sheet_name: str, distance_col: str = "", depth_col: str = "", metal_loss_col: str = ""
) -> Optional[Dict[str, Any]]:
    """Call the backend process API"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (file.name, file.getvalue(), file.type)}
            data = {
                "sheet_name": sheet_name,
                "distance_column": distance_col or "",
                "depth_column": depth_col or "",
                "metal_loss_column": metal_loss_col or "",
            }
            response = await client.post(
                f"{BACKEND_URL}/api/ili/process", files=files, data=data
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        st.error(f"Error calling process API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None


def _format_api_error(e: Exception, response: Optional[httpx.Response] = None) -> str:
    """Format API error with status code and response body for debugging."""
    parts = [str(e)]
    if response is not None:
        parts.append(f"Status: {response.status_code}")
        try:
            body = response.text
            if body and len(body) < 500:
                parts.append(f"Response: {body}")
            elif body:
                parts.append(f"Response (truncated): {body[:500]}...")
        except Exception:
            pass
    return " | ".join(parts)


async def call_process_feature_map_api(
    file,
    sheet_name: str,
    gwd_start: Optional[int] = None,
    gwd_end: Optional[int] = None,
    gwd_center: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Call the backend process-feature-map API for Excel → unwrapped pipe visualization"""
    url = f"{BACKEND_URL}/api/ili/process-feature-map"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (file.name, file.getvalue(), file.type)}
            data = {"sheet_name": sheet_name}
            if gwd_start is not None:
                data["gwd_start"] = str(gwd_start)
            if gwd_end is not None:
                data["gwd_end"] = str(gwd_end)
            if gwd_center is not None:
                data["gwd_center"] = str(gwd_center)
            response = await client.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        msg = _format_api_error(e, e.response)
        st.error(f"API error: {msg}")
        if e.response.status_code == 404:
            st.warning(
                f"**404 Not Found** — `{url}` may not be available. "
                "Please **restart the backend server** (e.g. `uvicorn backend.main:app --reload`) to load the latest code."
            )
        return None
    except httpx.HTTPError as e:
        st.error(f"Request failed: {_format_api_error(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return None


async def call_process_dig_package_api(file) -> Optional[Dict[str, Any]]:
    """Call the backend process-dig-package API for dig package Excel → unwrapped pipe visualization"""
    url = f"{BACKEND_URL}/api/ili/process-dig-package"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (file.name, file.getvalue(), file.type)}
            response = await client.post(url, files=files)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        msg = _format_api_error(e, e.response)
        st.error(f"API error: {msg}")
        if e.response.status_code == 404:
            st.warning(
                f"**404 Not Found** — `{url}` may not be available. "
                "Please **restart the backend server** (e.g. `uvicorn backend.main:app --reload`) to load the latest code."
            )
        return None
    except httpx.HTTPError as e:
        st.error(f"Request failed: {_format_api_error(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return None


async def call_excel_to_pdf_api(file_bytes: bytes, filename: str) -> Optional[bytes]:
    """
    Ask the backend to convert an Excel file to PDF (uses Excel COM on Windows).
    Returns raw PDF bytes on success, None if conversion is unavailable or fails.
    """
    url = f"{BACKEND_URL}/api/ili/excel-to-pdf"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            files = {
                "file": (
                    filename,
                    file_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            response = await client.post(url, files=files)
            if response.status_code == 200:
                return response.content  # raw PDF bytes
            # 501 = win32com not available; 500 = other error — caller falls back silently
            return None
    except Exception:
        return None


@st.cache_resource(ttl=10)  # Cache for 10 seconds (allows quick retry when backend starts)
def check_backend_health() -> bool:
    """Check if backend is running (cached for 10 seconds)"""
    try:
        response = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
        return response.status_code == 200 and response.json().get("ok", False)
    except Exception:
        return False


def show_backend_unavailable_and_retry() -> None:
    """
    Show backend unavailable message with retry button.
    On retry click, clears health check cache and reruns the app.
    """
    st.error(
        """
        ⚠️ **Backend API is not available**

        Please start the backend server from the project root:
        ```bash
        python -m uvicorn backend.main:app --reload
        ```
        Or with uv: `uv run uvicorn backend.main:app --reload`
        """
    )
    if st.button("🔄 Retry connection", type="primary"):
        check_backend_health.clear()
        st.rerun()


def get_layout_main():
    """
    Full-width main container. Chat uses a floating FAB + dialog — see ``chat_panel.render_floating_chat_shell``.
    """
    return st.container()


def get_layout_with_chat():
    """
    Same as :func:`get_layout_main` (single full-width container).
    Call ``chat_panel.render_floating_chat_shell()`` at the end of each page for Chat with Chen.
    """
    return get_layout_main()


def display_sidebar_navigation():
    """Display custom sidebar navigation with expandable sections"""
    with st.sidebar:
        st.page_link("Home.py", label="🏠 Home")
        st.page_link("pages/1_Dashboard.py", label="📊 Dashboard")
        st.page_link("pages/9_Skills_Overview.py", label="🧠 Skills Overview")

        st.markdown("---")

        with st.expander("🏭 Facility", expanded=False):
            st.page_link("pages/2_TML_Data_Loader.py", label="⚙️ TML Data Loader")
            st.page_link("pages/7_Deactive_CML.py", label="🔴 De-active CML")
            st.page_link("pages/8_Inspection_Report_Loader.py", label="📄 Inspection Report Loader")

        with st.expander("🛢️ Pipeline", expanded=False):
            st.page_link("pages/3_Dig_Package_Visual_Tool.py", label="📦 Dig Package Visual Tool")
            st.page_link("pages/3_ILI_Visual_Tool.py", label="📊 ILI Visual Tool")
            st.page_link("pages/4_Metal_Loss_Assessment.py", label="🔬 Metal Loss Assessment")
            st.page_link("pages/6_Metal_Loss_Mass_Assessment.py", label="📉 Metal Loss Mass Assessment")
            st.page_link("pages/5_Dig_Package_Generator.py", label="📦 Dig Package Generator") 