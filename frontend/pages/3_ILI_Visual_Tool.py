import asyncio

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
    call_parse_paste_api,
    call_preview_api,
    call_process_api,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    get_layout_with_chat,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_chat_expander

# Page configuration
set_page_config("ILI Visual Tool", "🛢️")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

(left_col, right_col), chat_visible = get_layout_with_chat()

with left_col:
    # Header
    display_header(
        "🛢️ ILI Visual Tool",
        "Visualize In-Line Inspection (ILI) data — upload Excel or paste from clipboard",
    )

    # Check backend status
    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    # Input mode: Upload vs Paste
    input_mode = st.radio(
        "**Input mode**",
        options=["Upload Excel File", "Paste from Clipboard"],
        horizontal=True,
        help="Upload an Excel file or paste tabular data (e.g. from Excel)",
    )

    # Initialize session state
    if "preview_data" not in st.session_state:
        st.session_state.preview_data = None
    if "process_data" not in st.session_state:
        st.session_state.process_data = None
    if "uploaded_file" not in st.session_state:
        st.session_state.uploaded_file = None
    if "feature_map_data" not in st.session_state:
        st.session_state.feature_map_data = None

    if input_mode == "Paste from Clipboard":
        # ========== PASTE MODE: Excel-like table, paste directly ==========
        st.markdown("### 📋 Paste ILI Data")
        st.caption(
            "Copy a table from Excel (including header row) and paste directly into the table below. "
            "Click Generate to visualize."
        )

        if "pasted_df" not in st.session_state:
            st.session_state.pasted_df = pd.DataFrame([[""] * 15])

        col_config = {str(i): st.column_config.TextColumn(label=" ", width="small") for i in range(20)}
        edited_df = st.data_editor(
            st.session_state.pasted_df,
            use_container_width=True,
            num_rows="dynamic",
            key="ili_paste_editor",
            hide_index=True,
            column_config=col_config,
        )
        st.session_state.pasted_df = edited_df

        def _prepare_data_for_api(df: pd.DataFrame) -> str:
            """If first row looks like ILI headers, use it as column names."""
            if df.empty or len(df) < 1:
                return ""
            first_row = df.iloc[0].astype(str).str.strip()
            header_keywords = ["ili", "chainage", "distance", "depth", "feature", "length", "width", "orientation", "odometer"]
            first_row_lower = " ".join(first_row.str.lower())
            if len(df) >= 2 and any(kw in first_row_lower for kw in header_keywords):
                new_cols = [str(v).strip() or f"_col{i}" for i, v in enumerate(first_row)]
                out = df.iloc[1:].copy()
                n = len(out.columns)
                out.columns = [new_cols[i] if i < len(new_cols) else f"_col{i}" for i in range(n)]
                return out.to_csv(index=False).strip()
            return df.to_csv(index=False).strip()

        if st.button("🗺️ Generate Feature Map", type="primary"):
            to_send = _prepare_data_for_api(edited_df) if not edited_df.empty else ""
            if not to_send or edited_df.empty:
                st.warning("Please paste data into the table above (copy from Excel and paste).")
            else:
                with st.spinner("Parsing and mapping columns..."):
                    result = asyncio.run(call_parse_paste_api(to_send))
                    if result and result.get("success"):
                        st.session_state.feature_map_data = result
                        st.success(f"✅ Parsed {result.get('total_rows', 0)} features!")
                    elif result and not result.get("success"):
                        st.error(result.get("error", "Parse failed"))

        if st.session_state.feature_map_data and st.session_state.feature_map_data.get("success"):
            fm = st.session_state.feature_map_data
            features = fm.get("features", [])
            mapping = fm.get("column_mapping", {})
            scatter_data = fm.get("scatter_data") or {}

            st.markdown("---")
            st.markdown("### 🗺️ Feature Map")
            st.caption("Unwrapped pipe view: X = chainage (m), Y = orientation (o'clock). Feature boxes proportional to length (mm) × width (mm). Depth: green 0-20% WT, yellow 20-40%, orange 40-60%, red >60%.")

            # Reference-style: X=chainage, Y=orientation, depth as color
            def _depth_color(d):
                if d is None or (isinstance(d, float) and pd.isna(d)):
                    return "lightgrey"
                if d < 20:
                    return "green"
                if d < 40:
                    return "yellow"
                if d < 60:
                    return "orange"
                return "red"

            x_values = scatter_data.get("x_values", [f["x"] for f in features])
            orient_hours = scatter_data.get("orientation_hours")
            use_orientation = orient_hours and len(orient_hours) == len(features)
            y_values = orient_hours if use_orientation else [f["y"] for f in features]
            y_label = "Feature Orientation (hh:mm)" if use_orientation else "Depth (%WT)"
            x_column = scatter_data.get("x_column", "ILI Chainage (m)")

            fig = go.Figure()
            x_span = (max(x_values) - min(x_values)) if x_values else 1
            x_span = x_span or 1
            y_span = (max(y_values) - min(y_values)) if y_values else 1
            y_span = y_span or 1
            pipe_od_mm = 273.05
            pipe_circ_mm = 3.14159 * pipe_od_mm
            scale_factor = 0.5
            min_len, min_wid = 1.0, 0.3

            # Exclude Girth Weld and Seam Weld from feature boxes (they are drawn as lines)
            plot_features = [f for f in features if "girth" not in (f.get("feature_type") or "").lower() and "seam" not in (f.get("feature_type") or "").lower() and "gwd" not in (f.get("feature_type") or "").lower()]

            for f in plot_features:
                cx = f["x"]
                cy = f.get("orientation_hours", 6.0) if use_orientation else f["y"]
                ln_mm = max(f.get("length", 0) or 0.001, 0.001)
                wd_mm = max(f.get("width", 0) or 0.001, 0.001)
                ln_m = max((ln_mm / 1000) * scale_factor, min_len)
                wd_hr = max((wd_mm / pipe_circ_mm) * 24 * scale_factor, min_wid)
                x0, x1 = cx - ln_m / 2, cx + ln_m / 2
                y0, y1 = cy - wd_hr / 2, cy + wd_hr / 2
                color = _depth_color(f.get("depth"))
                fig.add_shape(
                    type="rect",
                    x0=x0, x1=x1, y0=y0, y1=y1,
                    line=dict(color="black", width=2.5),
                    fillcolor=color,
                )

            for gw in scatter_data.get("girth_welds", []):
                fig.add_vline(x=gw.get("chainage"), line_color="red", line_width=2.5)

            x_min_plot = min(x_values) if x_values else 0
            x_max_plot = max(x_values) if x_values else 1
            y_min_plot = min(y_values) if y_values else 0
            y_max_plot = max(y_values) if y_values else 12
            for sw in scatter_data.get("seam_welds", []):
                oh = sw.get("orientation_hours", 6.0)
                ch_start = sw.get("chainage_start") if sw.get("chainage_start") is not None else x_min_plot
                ch_end = sw.get("chainage_end") if sw.get("chainage_end") is not None else x_max_plot
                fig.add_trace(go.Scatter(x=[ch_start, ch_end], y=[oh, oh], mode="lines", line=dict(color="blue", width=2.5), showlegend=False, hoverinfo="skip"))

            hover_texts = [f.get("hover_text", "") for f in plot_features]
            plot_x = [f["x"] for f in plot_features]
            plot_y = [f.get("orientation_hours", 6.0) if use_orientation else f["y"] for f in plot_features]

            fig.add_trace(
                go.Scatter(
                    x=plot_x,
                    y=plot_y,
                    mode="markers",
                    marker=dict(size=4, color="rgba(0,0,0,0)"),
                    text=hover_texts,
                    hoverinfo="text",
                )
            )

            annotations = [
                dict(x=1.02, y=0.98, xref="paper", yref="paper", text="Depth: 0-20% green, 20-40% yellow, 40-60% orange, >60% red", showarrow=False, font=dict(size=9), xanchor="left"),
                dict(x=1.02, y=0.88, xref="paper", yref="paper", text="Box size: length (mm) × width (mm)", showarrow=False, font=dict(size=8), xanchor="left"),
            ]
            for gw in scatter_data.get("girth_welds", []):
                lbl = gw.get("label", "")
                if lbl:
                    y_pos = y_min_plot + 0.7 * (y_max_plot - y_min_plot) if y_values else 6
                    annotations.append(
                        dict(x=gw["chainage"], y=y_pos, text=lbl, showarrow=False, font=dict(size=9, color="darkred"), textangle=-90, xanchor="right", yanchor="middle"),
                    )
            for sw in scatter_data.get("seam_welds", []):
                lbl = sw.get("orientation_label", "")
                if lbl:
                    ch_s, ch_e = sw.get("chainage_start"), sw.get("chainage_end")
                    mid_x = ((ch_s or 0) + (ch_e or 0)) / 2 if (ch_s is not None or ch_e is not None) else (x_min_plot + x_max_plot) / 2
                    annotations.append(
                        dict(x=mid_x, y=sw.get("orientation_hours", 6) + 0.3, text=lbl, showarrow=False, font=dict(size=8, color="blue"), xanchor="center", yanchor="bottom"),
                    )

            x_axis_title = "ILI Chainage (m)" if "chainage" in (x_column or "").lower() or "distance" in (x_column or "").lower() else f"{x_column} (m)"
            fig.update_layout(
                title="ILI Feature Map (Unwrapped Pipe View)",
                xaxis_title=x_axis_title,
                yaxis_title="Feature Orientation (hh:mm)",
                height=450,
                hovermode="closest",
                template="plotly_white",
                plot_bgcolor="white",
                xaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.2)", showline=True, linewidth=2, linecolor="black", mirror=True),
                yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.2)", showline=True, linewidth=2, linecolor="black", mirror=True),
                annotations=annotations,
            )
            if use_orientation:
                fig.update_yaxes(
                    tickvals=list(range(0, 13)),
                    ticktext=[f"{h:02d}:00" for h in range(0, 13)],
                    range=[0, 12],
                )
            st.plotly_chart(fig, use_container_width=True)

            st.info(f"**{len(features)} features** visualized")

            with st.expander("📊 Column mapping used"):
                st.json(mapping)

        else:
            st.info(
                """
                👆 **Paste your ILI data into the table above**

                Copy a table from Excel (with headers) and paste directly into the table. 
                Column format is preserved. Click **Generate Feature Map** to visualize.
                """
            )

    else:
        # ========== UPLOAD MODE: Existing Excel flow ==========
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

                # Display processed results (visual only, no assessment)
                if st.session_state.process_data:
                    st.markdown("---")
                    st.markdown("### 🗺️ Feature Map")

                    process = st.session_state.process_data

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

                    st.info(f"**{process['total_rows']} features** from sheet '{process['sheet_name']}'")

        else:
            # No file uploaded
            st.info(
                """
                👆 **Upload an Excel file** with ILI (In-Line Inspection) data

                The tool visualizes pipeline features by chainage and depth.
                No assessment or statistics — visualization only.
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
with right_col:
    render_chat_expander(right_col, chat_visible)
