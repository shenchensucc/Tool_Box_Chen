import asyncio
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    apply_custom_styling,
    call_preview_api,
    call_process_api,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    set_page_config,
    show_backend_unavailable_and_retry,
)

# Page configuration
set_page_config("ILI Visual Tool", "🛢️")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

# Header
display_header(
    "🛢️ ILI Visual Tool",
    "Upload and analyze In-Line Inspection (ILI) data from Excel files",
)

# Check backend status
if not check_backend_health():
    show_backend_unavailable_and_retry()
    st.stop()

# Initialize session state
if "preview_data" not in st.session_state:
    st.session_state.preview_data = None
if "process_data" not in st.session_state:
    st.session_state.process_data = None
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

# File upload section
st.markdown("### 📁 Step 1: Upload Excel File")
uploaded_file = st.file_uploader(
    "Choose an Excel file (.xlsx or .xls)",
    type=["xlsx", "xls"],
    help="Maximum file size: 100 MB",
)

if uploaded_file is not None:
    # Store file in session state
    if st.session_state.uploaded_file != uploaded_file.name:
        st.session_state.uploaded_file = uploaded_file.name
        st.session_state.preview_data = None
        st.session_state.process_data = None

    st.success(f"✅ File uploaded: **{uploaded_file.name}**")

    # Preview button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔍 Preview File", type="primary"):
            with st.spinner("Loading file preview..."):
                preview_data = asyncio.run(call_preview_api(uploaded_file))
                if preview_data:
                    st.session_state.preview_data = preview_data

    # Display preview data
    if st.session_state.preview_data:
        st.markdown("---")
        st.markdown("### 📋 Step 2: File Preview")

        preview = st.session_state.preview_data

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Sheets found:** {len(preview['sheet_names'])}")
        with col2:
            st.info(f"**Total rows:** {sum(preview['row_counts'].values())}")

        # Display sheet information
        for sheet_name in preview["sheet_names"]:
            with st.expander(f"📄 Sheet: **{sheet_name}** ({preview['row_counts'][sheet_name]} rows)"):
                columns = preview["columns"][sheet_name]
                st.write(f"**Columns ({len(columns)}):**")
                st.write(", ".join(columns))

        # Processing section
        st.markdown("---")
        st.markdown("### ⚙️ Step 3: Process and Visualize")

        # Select sheet
        selected_sheet = st.selectbox(
            "Select sheet to process",
            options=preview["sheet_names"],
            help="Choose which sheet contains your ILI data",
        )

        # Column mapping
        st.markdown("**Map your columns:**")
        col1, col2, col3 = st.columns(3)

        available_columns = [""] + preview["columns"][selected_sheet]

        with col1:
            distance_col = st.selectbox(
                "Distance Column",
                options=available_columns,
                help="Column containing distance/location data",
            )

        with col2:
            depth_col = st.selectbox(
                "Depth Column",
                options=available_columns,
                help="Column containing depth/anomaly depth data",
            )

        with col3:
            metal_loss_col = st.selectbox(
                "Metal Loss Column",
                options=available_columns,
                help="Column containing metal loss percentage",
            )

        # Process button
        if st.button("🚀 Process Data", type="primary"):
            if not any([distance_col, depth_col, metal_loss_col]):
                st.warning("⚠️ Please select at least one column to analyze")
            else:
                with st.spinner("Processing data..."):
                    process_data = asyncio.run(
                        call_process_api(
                            uploaded_file,
                            selected_sheet,
                            distance_col,
                            depth_col,
                            metal_loss_col,
                        )
                    )
                    if process_data:
                        st.session_state.process_data = process_data
                        st.success("✅ Data processed successfully!")

        # Display processed results
        if st.session_state.process_data:
            st.markdown("---")
            st.markdown("### 📊 Step 4: Results and Visualizations")

            process = st.session_state.process_data

            # Statistics table
            st.markdown("#### 📈 Statistical Summary")

            if process["stats"]:
                stats_df = pd.DataFrame(process["stats"]).T
                stats_df = stats_df.round(2)
                st.dataframe(stats_df, use_container_width=True)
            else:
                st.info("No numeric columns to analyze")

            # Histograms
            if process["histograms"]:
                st.markdown("#### 📊 Distribution Plots")

                cols = st.columns(min(len(process["histograms"]), 3))

                for idx, hist_data in enumerate(process["histograms"]):
                    with cols[idx % 3]:
                        fig = go.Figure()
                        fig.add_trace(
                            go.Histogram(
                                x=hist_data["values"],
                                nbinsx=len(hist_data["bin_edges"]) - 1,
                                name=hist_data["column_name"],
                                marker_color="#3498db",
                            )
                        )
                        fig.update_layout(
                            title=f"Distribution: {hist_data['column_name']}",
                            xaxis_title=hist_data["column_name"],
                            yaxis_title="Frequency",
                            height=300,
                            showlegend=False,
                        )
                        st.plotly_chart(fig, use_container_width=True)

            # Scatter plots
            if process["scatter_data"] and process["scatter_data"]["y_data"]:
                st.markdown("#### 🔍 Distance-based Analysis")

                x_values = process["scatter_data"]["x_values"]
                x_column = process["scatter_data"]["x_column"]
                y_data = process["scatter_data"]["y_data"]

                tabs = st.tabs([key.replace("_", " ").title() for key in y_data.keys()])

                for idx, (key, y_values) in enumerate(y_data.items()):
                    with tabs[idx]:
                        fig = go.Figure()
                        fig.add_trace(
                            go.Scatter(
                                x=x_values,
                                y=y_values,
                                mode="markers",
                                marker=dict(
                                    size=6,
                                    color=y_values,
                                    colorscale="Viridis",
                                    showscale=True,
                                    colorbar=dict(title=key.replace("_", " ").title()),
                                ),
                                name=key.replace("_", " ").title(),
                            )
                        )
                        fig.update_layout(
                            title=f"{key.replace('_', ' ').title()} vs {x_column}",
                            xaxis_title=x_column,
                            yaxis_title=key.replace("_", " ").title(),
                            height=400,
                            hovermode="closest",
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # Box plot
                        fig_box = go.Figure()
                        fig_box.add_trace(go.Box(y=y_values, name=key.replace("_", " ").title(), marker_color="#3498db"))
                        fig_box.update_layout(
                            title=f"{key.replace('_', ' ').title()} Distribution",
                            yaxis_title=key.replace("_", " ").title(),
                            height=300,
                            showlegend=False,
                        )
                        st.plotly_chart(fig_box, use_container_width=True)

            # Download section
            st.markdown("---")
            st.markdown("#### 💾 Export Results")

            col1, col2 = st.columns(2)

            with col1:
                if process["stats"]:
                    stats_csv = pd.DataFrame(process["stats"]).T.to_csv()
                    st.download_button(
                        label="📥 Download Statistics (CSV)",
                        data=stats_csv,
                        file_name=f"ili_stats_{process['filename']}.csv",
                        mime="text/csv",
                    )

            with col2:
                st.info(f"**Processed:** {process['total_rows']} rows from sheet '{process['sheet_name']}'")

else:
    # No file uploaded
    st.info(
        """
        👆 **Get started by uploading an Excel file**

        Your Excel file should contain ILI (In-Line Inspection) data with columns such as:
        - Distance or location information
        - Depth measurements
        - Metal loss percentages
        - Other inspection metrics

        The tool will help you:
        1. Preview the structure of your Excel file
        2. Select the relevant sheet and columns
        3. Generate statistical summaries
        4. Create interactive visualizations
        5. Export processed results
        """
    )

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #95a5a6;'>
        <p>ILI Visual Tool | Powered by FastAPI + Plotly</p>
    </div>
    """,
    unsafe_allow_html=True,
) 