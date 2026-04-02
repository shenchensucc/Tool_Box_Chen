import streamlit as st

from frontend_utils import (
    apply_custom_styling,
    check_backend_health,
    display_sidebar_navigation,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell

# Page configuration
set_page_config("Chen's Engineer Toolbox", "🔧")
apply_custom_styling()

# Custom Sidebar Navigation with Expandable Sections
display_sidebar_navigation()

main = get_layout_main()

with main:
    # -----------------------------------------------------------------------
    # Hero
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div style="padding: 2.5rem 0 1rem 0;">
            <div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.5rem;">
                <span style="font-size:2.8rem; line-height:1;">🔧</span>
                <div>
                    <h1 style="margin:0; font-size:2.5rem; letter-spacing:-0.03em;">
                        Chen's Engineer Toolbox
                    </h1>
                    <p style="margin:0.25rem 0 0 0; font-size:1rem; color:#475569;">
                        Pipeline &amp; facility integrity tools — ILI analysis, dig packages, metal loss assessment
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # -----------------------------------------------------------------------
    # System status strip
    # -----------------------------------------------------------------------
    backend_status = check_backend_health()
    status_color = "#059669" if backend_status else "#DC2626"
    status_dot = "●" if backend_status else "○"
    status_label = "Backend API online" if backend_status else "Backend API offline"
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:0.5rem; padding:0.6rem 1rem;
                    background:#F1F5F9; border:1px solid #E2E8F0; border-radius:6px;
                    margin-bottom:1.5rem; font-size:0.875rem; font-weight:500;">
            <span style="color:{status_color}; font-size:1rem;">{status_dot}</span>
            <span style="color:#475569;">{status_label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not backend_status:
        show_backend_unavailable_and_retry()

    # -----------------------------------------------------------------------
    # Tool cards
    # -----------------------------------------------------------------------
    st.markdown(
        "<p style='font-size:0.7rem; font-weight:600; text-transform:uppercase; "
        "letter-spacing:0.1em; color:#94A3B8; margin-bottom:0.75rem;'>AVAILABLE TOOLS</p>",
        unsafe_allow_html=True,
    )

    tools = [
        {
            "icon": "📊", "title": "Dashboard",
            "desc": "Project overview and data summaries",
            "page": "1_Dashboard",
        },
        {
            "icon": "📦", "title": "Dig Package Generator",
            "desc": "Generate dig packages from MDL + ILI + template",
            "page": "5_Dig_Package_Generator",
        },
        {
            "icon": "🔍", "title": "Dig Package Visual Tool",
            "desc": "Visualize ILI data from dig package Excel files",
            "page": "3_Dig_Package_Visual_Tool",
        },
        {
            "icon": "📈", "title": "ILI Visual Tool",
            "desc": "Upload Excel or paste clipboard data for ILI visualization",
            "page": "3_ILI_Visual_Tool",
        },
        {
            "icon": "🧮", "title": "Metal Loss Assessment",
            "desc": "Single-feature metal loss fitness-for-service calculation",
            "page": "4_Metal_Loss_Assessment",
        },
        {
            "icon": "📋", "title": "Metal Loss Mass Assessment",
            "desc": "Batch metal loss assessment across multiple features",
            "page": "6_Metal_Loss_Mass_Assessment",
        },
        {
            "icon": "⚙️", "title": "TML Data Loader",
            "desc": "Batch-process up to 20 TML workflows simultaneously",
            "page": "2_TML_Data_Loader",
        },
        {
            "icon": "📄", "title": "Inspection Report Loader",
            "desc": "Parse and extract data from inspection report PDFs",
            "page": "8_Inspection_Report_Loader",
        },
        {
            "icon": "🔌", "title": "Deactivate CML",
            "desc": "Deactivate corrosion monitoring locations in bulk",
            "page": "7_Deactive_CML",
        },
    ]

    cols = st.columns(3)
    for i, tool in enumerate(tools):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="background:#FFFFFF; border:1px solid #E2E8F0;
                            border-left:3px solid #0F3460;
                            border-radius:6px; padding:1rem 1.1rem;
                            margin-bottom:0.75rem;
                            transition:box-shadow 0.15s;">
                    <div style="font-size:1.3rem; margin-bottom:0.4rem;">{tool['icon']}</div>
                    <div style="font-weight:600; font-size:0.95rem; color:#0F172A;
                                margin-bottom:0.25rem;">{tool['title']}</div>
                    <div style="font-size:0.82rem; color:#64748B; line-height:1.45;">{tool['desc']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("🛠️ Development (remove when shipping)", expanded=False):
        st.caption("Dig package template KPI checklist — static checks, optional pytest, manual marks.")
        st.page_link("pages/10_Dig_Package_KPI_Dev.py", label="🧪 Dig Package KPI (dev)")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Footer
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div style="display:flex; justify-content:space-between; align-items:center;
                    color:#94A3B8; font-size:0.8rem; padding:0.5rem 0 1rem 0;">
            <span>Chen's Engineer Toolbox v0.1.0</span>
            <span style="font-family:'JetBrains Mono',monospace;">
                Streamlit · FastAPI · Python 3.11
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_floating_chat_shell()