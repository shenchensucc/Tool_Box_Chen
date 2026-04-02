import os
import re
import textwrap
from typing import Any, Dict, Optional, Tuple

import httpx
import streamlit as st

# Backend URL configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Dig Package Generator — ILI layout labels (must match ``backend.pipeline.dig_package`` / API).
DIG_PACKAGE_ILI_FORMAT_OPTIONS: Tuple[str, ...] = (
    "TDW",
    "Rosen-MFLA",
    "Rosen-MFLC",
    "Rosen-EMAT",
    "BH-EMAT",
    "BH-MFLA",
)


def detect_dig_package_ili_format(filename: str) -> Tuple[str, str]:
    """
    Infer ILI vendor/layout from the uploaded filename (TDW, Rosen MFL-A/C/EMAT, BH EMAT/MFL).

    Returns:
        (format_name, short note for UI) — ``format_name`` is always one of
        :data:`DIG_PACKAGE_ILI_FORMAT_OPTIONS`.
    """
    opts = DIG_PACKAGE_ILI_FORMAT_OPTIONS
    name = (filename or "").strip()
    lower = name.lower()
    compact = re.sub(r"[^a-z0-9]", "", lower)

    def _mfl_a() -> bool:
        return bool(
            re.search(r"mfl\s*[-_/]?\s*a\b", lower)
            or re.search(r"\bmfla\b", lower)
            or "mfla" in compact
        )

    def _mfl_c() -> bool:
        return bool(
            re.search(r"mfl\s*[-_/]?\s*c\b", lower)
            or re.search(r"\bmflc\b", lower)
            or "mflc" in compact
            or "cmfl" in compact
        )

    has_emat_token = "emat" in compact
    has_rosen = "rosen" in compact

    # Baker Hughes — check before generic EMAT/MFL so vendor-specific names win.
    if (
        re.search(r"(^|[^a-z0-9])bh([^a-z0-9]|$)", lower)
        or "baker" in lower
        or "bakerhughes" in compact
    ):
        if has_emat_token:
            return (opts[4], "filename suggests Baker Hughes EMAT")
        if "mfl" in compact:
            return (opts[5], "filename suggests Baker Hughes MFL")

    # TDW vendor
    if re.search(r"\btdw\b", lower) or "tdw" in compact:
        return (opts[0], "filename contains TDW")

    mfl_a, mfl_c = _mfl_a(), _mfl_c()

    if mfl_a and mfl_c:
        if "cmfl" in compact:
            return (opts[2], "filename has both MFL-A and MFL-C cues; CMFL → Rosen-MFLC")
        return (opts[1], "filename has both MFL-A and MFL-C cues; defaulting to Rosen-MFLA — override if needed")

    if mfl_c:
        return (opts[2], "filename suggests MFL-C or CMFL (Rosen)")

    if mfl_a:
        return (opts[1], "filename suggests MFL-A (Rosen)")

    if has_emat_token:
        return (opts[3], "filename contains EMAT (Rosen-EMAT)")

    if has_rosen and "mfl" in compact:
        return (opts[1], "Rosen + MFL in filename; defaulting to Rosen-MFLA — override if this is MFL-C")

    if "mfl" in compact:
        return (opts[1], "filename contains MFL; defaulting to Rosen-MFLA — override for TDW/BH/MFL-C if needed")

    # Matches backend default in ``main.py`` when ``ili_formats`` is empty.
    return (opts[1], "no strong match — using Rosen-MFLA (API default); override if your file differs")


def fu_key(page: str, role: str) -> str:
    """Return a distinct ``key`` for ``st.file_uploader`` widgets.

    Use a unique key per control so Streamlit session state and widget identity
    do not collide across pages or between uploaders on the same page.

    Note: The OS/browser often remembers one recent folder per *site* for native
    ``<input type="file">`` dialogs. That is not controlled by Streamlit keys;
    Chromium can only associate separate folders per control when using the
    File System Access API (e.g. ``showOpenFilePicker({ id })``), which
    ``st.file_uploader`` does not use.
    """
    return f"fu_{page}_{role}"


def apply_custom_styling():
    """Apply custom CSS styling — Industrial-Precision design system (see DESIGN.md)."""
    # Use st.html (not st.markdown) so <style> is injected as real CSS. Streamlit's markdown
    # path can strip <style> and leave the rules as visible text; then stSidebarNav never hides.
    _custom_theme_css = textwrap.dedent("""
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
        /* ------------------------------------------------------------------ */
        /* Design tokens (DESIGN.md)                                           */
        /* ------------------------------------------------------------------ */
        :root {
            --color-primary:        #0F3460;
            --color-primary-hover:  #1A4A7A;
            --color-accent:         #F59E0B;
            --color-accent-hover:   #D97706;
            --color-bg:             #F8FAFC;
            --color-surface:        #FFFFFF;
            --color-surface-raised: #F1F5F9;
            --color-border:         #E2E8F0;
            --color-border-strong:  #CBD5E1;
            --color-text-primary:   #0F172A;
            --color-text-secondary: #475569;
            --color-text-muted:     #94A3B8;
            --color-success:        #059669;
            --color-warning:        #D97706;
            --color-error:          #DC2626;
            --color-info:           #0369A1;
            --color-sidebar-bg:     #1E293B;
            --color-sidebar-text:   #F1F5F9;
            --font-ui:     'DM Sans', system-ui, sans-serif;
            --font-mono:   'JetBrains Mono', 'Consolas', monospace;
            --radius-sm:   4px;
            --radius-md:   6px;
            --radius-lg:   8px;
            --transition:  0.15s ease-out;
        }

        /* ------------------------------------------------------------------ */
        /* Base typography                                                      */
        /* ------------------------------------------------------------------ */
        html, body, [class*="css"], .stMarkdown, .stText,
        .stTextInput, .stSelectbox, .stMultiSelect,
        button, label, p, span, div {
            font-family: var(--font-ui) !important;
        }

        /* Monospace for numbers in tables, code blocks, and metric values */
        code, pre, .stCode,
        [data-testid="stMetricValue"],
        .mono, td, th {
            font-family: var(--font-mono) !important;
        }

        h1 { font-size: 2.2rem !important; font-weight: 700 !important; color: var(--color-text-primary); letter-spacing: -0.02em; }
        h2 { font-size: 1.5rem  !important; font-weight: 600 !important; color: var(--color-text-primary); }
        h3 { font-size: 1.15rem !important; font-weight: 600 !important; color: var(--color-text-primary); }
        h4 { font-size: 1rem    !important; font-weight: 600 !important; color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }

        p, li { color: var(--color-text-secondary); line-height: 1.65; }

        /* ------------------------------------------------------------------ */
        /* Main layout                                                          */
        /* ------------------------------------------------------------------ */
        .main { padding: 1.5rem 2rem; background-color: var(--color-bg); }

        /* Replace thick hr separators with precise 1px rules */
        hr {
            border: none !important;
            border-top: 1px solid var(--color-border) !important;
            margin: 1.25rem 0 !important;
        }

        /* ------------------------------------------------------------------ */
        /* Sidebar — petroleum dark                                             */
        /* ------------------------------------------------------------------ */
        [data-testid="stSidebar"] {
            background-color: var(--color-sidebar-bg) !important;
            padding-top: 1.5rem;
        }
        [data-testid="stSidebar"] * {
            color: var(--color-sidebar-text) !important;
        }
        [data-testid="stSidebar"] .stMarkdown h3,
        [data-testid="stSidebar"] .stMarkdown h4 {
            color: var(--color-text-muted) !important;
            font-size: 0.7rem !important;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 4px;
            margin-bottom: 6px;
        }
        [data-testid="stSidebarNav"] { display: none; }

        /* ------------------------------------------------------------------ */
        /* Buttons                                                              */
        /* ------------------------------------------------------------------ */
        .stButton button,
        .stDownloadButton button,
        .stFormSubmitButton button {
            font-family: var(--font-ui) !important;
            font-weight: 500 !important;
            border-radius: var(--radius-md) !important;
            border: 1.5px solid transparent !important;
            padding: 0.45rem 1.25rem !important;
            transition: background-color var(--transition), box-shadow var(--transition), transform var(--transition) !important;
            letter-spacing: 0.01em;
        }

        /* Primary buttons — amber accent, not purple gradient */
        .stButton button[kind="primary"],
        .stDownloadButton button,
        .stFormSubmitButton button[kind="primary"] {
            background: var(--color-accent) !important;
            color: #0F172A !important;
            border-color: var(--color-accent) !important;
            font-weight: 600 !important;
        }
        .stButton button[kind="primary"]:hover,
        .stDownloadButton button:hover {
            background: var(--color-accent-hover) !important;
            border-color: var(--color-accent-hover) !important;
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.35) !important;
            transform: translateY(-1px);
        }

        /* Secondary buttons — petroleum blue outline */
        .stButton button[kind="secondary"] {
            background: transparent !important;
            color: var(--color-primary) !important;
            border-color: var(--color-primary) !important;
        }
        .stButton button[kind="secondary"]:hover {
            background: rgba(15, 52, 96, 0.06) !important;
            box-shadow: 0 2px 6px rgba(15, 52, 96, 0.12) !important;
            transform: translateY(-1px);
        }

        /* ------------------------------------------------------------------ */
        /* File uploader                                                        */
        /* ------------------------------------------------------------------ */
        [data-testid="stFileUploader"] {
            border: 1.5px dashed var(--color-border-strong) !important;
            border-radius: var(--radius-lg) !important;
            padding: 1.25rem !important;
            background: var(--color-surface) !important;
            transition: border-color var(--transition), background var(--transition) !important;
        }
        [data-testid="stFileUploader"]:hover {
            border-color: var(--color-primary) !important;
            background: rgba(15, 52, 96, 0.03) !important;
        }

        /* ------------------------------------------------------------------ */
        /* Metrics / stat cards                                                 */
        /* ------------------------------------------------------------------ */
        [data-testid="stMetric"] {
            background: var(--color-surface) !important;
            border: 1px solid var(--color-border) !important;
            border-radius: var(--radius-lg) !important;
            padding: 1rem 1.25rem !important;
            border-left: 3px solid var(--color-primary) !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.75rem !important;
            font-weight: 500 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
            color: var(--color-text-muted) !important;
        }
        [data-testid="stMetricValue"] {
            font-family: var(--font-mono) !important;
            font-size: 1.75rem !important;
            font-weight: 500 !important;
            color: var(--color-text-primary) !important;
        }
        [data-testid="stMetricDelta"] {
            font-family: var(--font-mono) !important;
            font-size: 0.8rem !important;
        }

        /* ------------------------------------------------------------------ */
        /* Alert / info boxes                                                   */
        /* ------------------------------------------------------------------ */
        .stAlert {
            border-radius: var(--radius-md) !important;
            border-left-width: 3px !important;
            font-size: 0.9rem !important;
        }
        [data-testid="stInfo"] {
            background: rgba(3, 105, 161, 0.07) !important;
            border-left-color: var(--color-info) !important;
            color: var(--color-info) !important;
        }
        [data-testid="stSuccess"] {
            background: rgba(5, 150, 105, 0.07) !important;
            border-left-color: var(--color-success) !important;
        }
        [data-testid="stWarning"] {
            background: rgba(217, 119, 6, 0.08) !important;
            border-left-color: var(--color-warning) !important;
        }
        [data-testid="stError"] {
            background: rgba(220, 38, 38, 0.07) !important;
            border-left-color: var(--color-error) !important;
        }

        /* ------------------------------------------------------------------ */
        /* DataFrames / tables                                                  */
        /* ------------------------------------------------------------------ */
        .dataframe, [data-testid="stDataFrame"] {
            border-radius: var(--radius-lg) !important;
            overflow: hidden !important;
            border: 1px solid var(--color-border) !important;
        }
        [data-testid="stDataFrame"] th {
            font-family: var(--font-ui) !important;
            font-size: 0.75rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            color: var(--color-text-secondary) !important;
            background: var(--color-surface-raised) !important;
        }
        [data-testid="stDataFrame"] td {
            font-family: var(--font-mono) !important;
            font-size: 0.85rem !important;
        }

        /* ------------------------------------------------------------------ */
        /* Tabs                                                                 */
        /* ------------------------------------------------------------------ */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px !important;
            border-bottom: 1px solid var(--color-border) !important;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: var(--radius-md) var(--radius-md) 0 0 !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
            font-size: 0.9rem !important;
            color: var(--color-text-secondary) !important;
        }
        .stTabs [aria-selected="true"] {
            color: var(--color-primary) !important;
            border-bottom: 2px solid var(--color-primary) !important;
            font-weight: 600 !important;
        }

        /* ------------------------------------------------------------------ */
        /* Expanders                                                            */
        /* ------------------------------------------------------------------ */
        .streamlit-expanderHeader {
            border-radius: var(--radius-md) !important;
            font-weight: 500 !important;
            font-size: 0.9rem !important;
            border: 1px solid var(--color-border) !important;
            padding: 0.6rem 1rem !important;
            background: var(--color-surface) !important;
        }
        .streamlit-expanderContent {
            border: 1px solid var(--color-border) !important;
            border-top: none !important;
            border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
            padding: 1rem !important;
            background: var(--color-surface) !important;
        }

        /* ------------------------------------------------------------------ */
        /* Progress bar                                                         */
        /* ------------------------------------------------------------------ */
        [data-testid="stProgressBar"] > div {
            background: var(--color-surface-raised) !important;
            border-radius: 999px !important;
            height: 6px !important;
        }
        [data-testid="stProgressBar"] > div > div {
            background: var(--color-accent) !important;
            border-radius: 999px !important;
            transition: width 0.4s ease-out !important;
        }

        /* ------------------------------------------------------------------ */
        /* Select / input fields                                                */
        /* ------------------------------------------------------------------ */
        .stTextInput input, .stNumberInput input, .stTextArea textarea {
            border: 1px solid var(--color-border) !important;
            border-radius: var(--radius-md) !important;
            font-family: var(--font-ui) !important;
            font-size: 0.9rem !important;
            background: var(--color-surface) !important;
            color: var(--color-text-primary) !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
            border-color: var(--color-primary) !important;
            box-shadow: 0 0 0 3px rgba(15, 52, 96, 0.1) !important;
        }
        [data-testid="stSelectbox"] > div > div {
            border: 1px solid var(--color-border) !important;
            border-radius: var(--radius-md) !important;
            background: var(--color-surface) !important;
        }

        /* ------------------------------------------------------------------ */
        /* Plotly charts                                                        */
        /* ------------------------------------------------------------------ */
        .js-plotly-plot {
            border-radius: var(--radius-lg) !important;
            border: 1px solid var(--color-border) !important;
        }

        /* ------------------------------------------------------------------ */
        /* Chat panel (sticky)                                                  */
        /* ------------------------------------------------------------------ */
        [data-testid="stHorizontalBlock"] > div:last-child {
            position: sticky !important;
            top: 1rem !important;
            align-self: start !important;
        }
        .chat-header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .chat-header-row h4 { margin: 0; flex: 1; }
        .chat-hide-btn {
            padding: 0.25rem 0.5rem !important;
            min-width: auto !important;
            font-size: 0.85rem !important;
        }

        /* ------------------------------------------------------------------ */
        /* Utility classes                                                      */
        /* ------------------------------------------------------------------ */
        .mono { font-family: var(--font-mono) !important; }
        .label-caps {
            font-size: 0.7rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            color: var(--color-text-muted) !important;
        }

        </style>
        """).strip()
    inject = getattr(st, "html", None)
    if inject is not None:
        inject(_custom_theme_css)
    else:
        st.markdown(_custom_theme_css, unsafe_allow_html=True)


def set_page_config(page_title: str, page_icon: str = "🔧", layout: str = "wide"):
    """Set Streamlit page configuration"""
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout=layout)


def display_header(title: str, description: Optional[str] = None):
    """Display a formatted page header using the Industrial-Precision design system."""
    desc_html = (
        f'<p style="margin:0.3rem 0 0 0; font-size:0.95rem; color:var(--color-text-secondary, #475569);">'
        f"{description}</p>"
    ) if description else ""
    st.markdown(
        f"""
        <div style="padding:1.5rem 0 0.75rem 0; border-bottom:1px solid var(--color-border, #E2E8F0);
                    margin-bottom:1.5rem;">
            <h1 style="margin:0; letter-spacing:-0.02em;">{title}</h1>
            {desc_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_session_privacy_banner() -> None:
    """
    High-visibility reminder that uploads/results are not persisted server-side
    (session-only in the browser).  Colour matches the dig-package primary blue
    (rgb(0, 100, 220)) used throughout the ILI visualisation tools.
    """
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
            border: 2px solid #0064dc;
            border-left: 5px solid #0064dc;
            border-radius: 10px;
            padding: 14px 18px;
            margin: 0 0 1rem 0;
            font-size: 1.05rem;
            line-height: 1.45;
            font-weight: 600;
            color: #1e3a6e;
            box-shadow: 0 3px 10px rgba(0, 100, 220, 0.25);
        ">
            <span style="font-size: 1.2rem;">🔒</span>
            <strong>Privacy Notice:</strong>
            This app does not keep any user information on the server —
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
    sheet_name: Optional[str] = None,
    *,
    vendor_format: Optional[str] = None,
    gwd_start: Optional[int] = None,
    gwd_end: Optional[int] = None,
    gwd_center: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Call the backend process-feature-map API for Excel → unwrapped pipe visualization.

    **Manual mode:** pass ``sheet_name`` (sheet from preview). Omit ``vendor_format``.

    **Auto mode (same ILI parsing as Dig Package):** pass ``vendor_format`` (e.g. ``Rosen-MFLA``).
    """
    url = f"{BACKEND_URL}/api/ili/process-feature-map"
    if vendor_format:
        data: Dict[str, Any] = {"vendor_format": vendor_format}
    elif sheet_name:
        data = {"sheet_name": sheet_name}
    else:
        st.error("Internal error: provide sheet_name or vendor_format for process-feature-map.")
        return None
    if gwd_start is not None:
        data["gwd_start"] = str(gwd_start)
    if gwd_end is not None:
        data["gwd_end"] = str(gwd_end)
    if gwd_center is not None:
        data["gwd_center"] = str(gwd_center)
    timeout = 300.0 if vendor_format else 60.0
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            files = {"file": (file.name, file.getvalue(), file.type)}
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

        with st.expander("🛠️ Development", expanded=False):
            st.page_link("pages/10_Dig_Package_KPI_Dev.py", label="🧪 Dig Package KPI (dev)") 