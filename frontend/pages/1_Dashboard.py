import streamlit as st

from frontend_utils import (
    apply_custom_styling,
    display_header,
    display_sidebar_navigation,
    set_page_config,
)

# Page configuration
set_page_config("Dashboard - Chen's Toolbox", "📊")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

# Header
display_header("📊 Dashboard", "Overview of your engineering projects and data")

# Main content
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Total Projects", value="0", delta="0")
    st.markdown(
        """
        <div style='padding: 1rem; background-color: #f8f9fa; border-radius: 5px;'>
            <h4>Recent Activity</h4>
            <p style='color: #7f8c8d;'>No recent activity</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.metric(label="Files Analyzed", value="0", delta="0")
    st.markdown(
        """
        <div style='padding: 1rem; background-color: #f8f9fa; border-radius: 5px;'>
            <h4>Quick Actions</h4>
            <ul style='color: #7f8c8d;'>
                <li>Upload new data</li>
                <li>View reports</li>
                <li>Export results</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.metric(label="Active Tools", value="2", delta="+1")
    st.markdown(
        """
        <div style='padding: 1rem; background-color: #f8f9fa; border-radius: 5px;'>
            <h4>Available Tools</h4>
            <ul style='color: #7f8c8d;'>
                <li>ILI Visual Tool ✅</li>
                <li>TML Data Loader ✅</li>
                <li>More coming soon...</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# Info section
st.info(
    """
    **Dashboard Overview**

    This dashboard provides a centralized view of your engineering projects and activities.
    As you use the various tools in the toolbox, this page will automatically update with:

    - Project statistics and metrics
    - Recent file analyses
    - Quick access to frequently used tools
    - System status and notifications

    Get started by selecting a tool from the sidebar!
    """
)

# Placeholder for future charts
st.markdown("### Activity Overview")
st.info("📈 Activity charts and visualizations will appear here as you use the tools.") 