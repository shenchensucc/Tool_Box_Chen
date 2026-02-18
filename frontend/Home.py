import streamlit as st

from frontend_utils import (
    apply_custom_styling,
    check_backend_health,
    display_sidebar_navigation,
    get_layout_with_chat,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_chat_expander

# Page configuration
set_page_config("Chen's Engineer Toolbox", "🔧")
apply_custom_styling()

# Custom Sidebar Navigation with Expandable Sections
display_sidebar_navigation()

# Layout: main content (left) + resizer + Chat with Chen (right, hideable, sticky)
cols, chat_visible = get_layout_with_chat()

left_col, right_col = cols

with left_col:
    # Main content
    st.markdown(
    """
    <div style='text-align: center; padding: 2rem 0;'>
        <h1 style='font-size: 3.5rem; color: #2c3e50; margin-bottom: 0;'>
            🔧 Chen's Engineer Toolbox
        </h1>
        <p style='font-size: 1.3rem; color: #7f8c8d; margin-top: 0.5rem;'>
            Python-based tools for facility and pipeline engineering
        </p>
    </div>
    """,
    unsafe_allow_html=True,
    )

    st.markdown("---")

    # Welcome section
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            """
            ### Welcome to the Engineering Toolbox

            This application provides a comprehensive suite of tools for:

            - 📊 **Dashboard**: Overview of your projects and data
            - 🏭 **Facility Tools**: Facility management and analysis
            - 🛢️ **Pipeline Tools**: Pipeline inspection and visualization
            - ⚙️ **TML Data Loader**: Batch process thickness monitoring location data

            ### Getting Started

            1. Use the sidebar to navigate to different sections
            2. Upload your data files (Excel, CSV)
            3. Analyze and visualize your engineering data

            ### Features

            - **ILI Visual Tool**: Upload and analyze in-line inspection data
            - **TML Data Loader**: Process up to 20 TML workflows simultaneously
            - **Interactive Charts**: Powered by Plotly for rich visualizations
            - **Data Export**: Download processed results
            - **Fast API Backend**: Efficient data processing

            ---

            **Ready to begin?** Select a tool from the sidebar! 👈
            """
        )

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        st.markdown("### System Status")
        backend_status = check_backend_health()

        if backend_status:
            st.success("✅ Backend API is running")
        else:
            show_backend_unavailable_and_retry()

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #95a5a6; padding: 2rem 0;'>
            <p>Chen's Engineer Toolbox v0.1.0</p>
            <p>Built with Streamlit + FastAPI + Python 3.11</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right_col:
    render_chat_expander(right_col, chat_visible) 