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


def check_backend_health() -> bool:
    """Check if backend is running"""
    try:
        response = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
        return response.status_code == 200 and response.json().get("ok", False)
    except Exception:
        return False 