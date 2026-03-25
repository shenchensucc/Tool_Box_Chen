import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chat_panel import render_floating_chat_shell
from frontend_utils import (
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_session_privacy_banner,
    display_sidebar_navigation,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from ili_visual_shared import render_ili_visual_tool

# Page configuration
set_page_config("ILI Visual Tool", "🛢️")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

main = get_layout_main()

with main:
    display_header(
        "🛢️ ILI Visual Tool",
        "Visualize In-Line Inspection (ILI) data from uploaded Excel files or clipboard input",
    )
    display_session_privacy_banner()

    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    render_ili_visual_tool()

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #95a5a6;'>
            <p>ILI Visual Tool | Powered by FastAPI + Plotly</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_floating_chat_shell()
