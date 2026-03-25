import sys
from pathlib import Path

import streamlit as st

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
from ili_visual_shared import render_dig_package_visual_tool


set_page_config("Dig Package Visual Tool", "📦")
apply_custom_styling()

display_sidebar_navigation()

main = get_layout_main()

with main:
    display_header(
        "📦 Dig Package Visual Tool",
        "Visualize ILI data directly from dig package Excel files",
    )
    display_session_privacy_banner()

    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    render_dig_package_visual_tool()

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #95a5a6;'>
            <p>Dig Package Visual Tool | Powered by FastAPI + Plotly</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_floating_chat_shell()
