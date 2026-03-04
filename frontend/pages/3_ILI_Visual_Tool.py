import asyncio

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# NPS (Nominal Pipe Size) to OD (mm) - ASME/ISO standard
NPS_TO_OD_MM = {
    4: 114.3,
    5: 141.3,
    6: 168.3,
    8: 219.1,
    10: 273.0,
    12: 323.8,
    14: 355.6,
    16: 406.4,
    18: 457.0,
    20: 508.0,
    24: 610.0,
    28: 711.0,
    32: 813.0,
}

from frontend_utils import (
    apply_custom_styling,
    call_parse_paste_api,
    call_preview_api,
    call_process_dig_package_api,
    call_process_feature_map_api,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    get_layout_with_chat,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_chat_expander


# RGB values for depth colors (for rgba with alpha)
_DEPTH_RGB = {
    "lightgrey": (211, 211, 211),
    "green": (34, 139, 34),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "red": (220, 20, 60),
}


def _depth_color(d, alpha: float = 1.0):
    """Map depth % to color for feature boxes. alpha=1.0 full, 0.2 for 20% visible."""
    if d is None or (isinstance(d, float) and pd.isna(d)):
        name = "lightgrey"
    elif d < 20:
        name = "green"
    elif d < 40:
        name = "yellow"
    elif d < 60:
        name = "orange"
    else:
        name = "red"
    r, g, b = _DEPTH_RGB.get(name, _DEPTH_RGB["lightgrey"])
    return f"rgba({r},{g},{b},{alpha})"


def _get_x_axis_title(x_column: str) -> str:
    """Return appropriate x-axis label. Uses Distance from TGW when chainage not available."""
    xc = (x_column or "").lower()
    if "distance" in xc and "tgw" in xc:
        return "Distance from TGW (m)"
    if "chainage" in xc or "odometer" in xc or "distance" in xc:
        return "ILI Chainage (m)"
    return f"{x_column} (m)" if x_column else "Distance (m)"


def _build_feature_map_figure(
    features: list,
    scatter_data: dict,
    pipe_circ_mm: float,
    source_filter: set,
    filter_by_source: bool,
    x_column: str,
    title: str,
    height: int = 450,
    use_opacity_overlay: bool = False,
) -> tuple:
    """
    Build a Plotly figure for the feature map. Returns (fig, filtered_count).
    When use_opacity_overlay=True, deselected sources are shown at 20% opacity instead of hidden.
    """
    def _is_selected(f_or_gw):
        src = f_or_gw.get("source", "") or ""
        if not filter_by_source:
            return True
        if not source_filter:
            return True
        if src in source_filter:
            return True
        # Seam welds use Joint Summary source (e.g. "2022 Rosen"); features use full source (e.g. "2022 Rosen MFL-A")
        # Match when one contains the other (Rosen MFL-A selected -> show 2022 Rosen seam line)
        for s in source_filter:
            if src in s or s in src:
                return True
        return False

    def _alpha(f_or_gw):
        return 0.2 if use_opacity_overlay and not _is_selected(f_or_gw) else 1.0

    # Overlay mode: show all; filter mode: show only selected
    if use_opacity_overlay:
        plot_features = [f for f in features if "girth" not in (f.get("feature_type") or "").lower() and "seam" not in (f.get("feature_type") or "").lower() and "gwd" not in (f.get("feature_type") or "").lower()]
        girth_list = scatter_data.get("girth_welds", [])
        seam_list = scatter_data.get("seam_welds", [])
        selected_count = sum(1 for f in features if _is_selected(f))
    else:
        filtered_features = [f for f in features if _is_selected(f)]
        plot_features = [f for f in filtered_features if "girth" not in (f.get("feature_type") or "").lower() and "seam" not in (f.get("feature_type") or "").lower() and "gwd" not in (f.get("feature_type") or "").lower()]
        girth_list = [gw for gw in scatter_data.get("girth_welds", []) if _is_selected(gw)]
        seam_list = [sw for sw in scatter_data.get("seam_welds", []) if _is_selected(sw)]
        selected_count = len(filtered_features)

    x_values = scatter_data.get("x_values", [f["x"] for f in features])
    orient_hours = scatter_data.get("orientation_hours")
    use_orientation = orient_hours and len(orient_hours) == len(features)
    y_values = orient_hours if use_orientation else [f["y"] for f in features]

    fig = go.Figure()
    # Draw deselected first (lower layer), then selected (on top) for clearer overlap
    for layer_alpha, layer_features in [(0.2, [f for f in plot_features if not _is_selected(f)]), (1.0, [f for f in plot_features if _is_selected(f)])]:
        for f in layer_features:
            cx = f["x"]
            cy = f.get("orientation_hours", 6.0) if use_orientation else f["y"]
            ln_mm = max(f.get("length", 0) or 0.001, 0.001)
            wd_mm = max(f.get("width", 0) or 0.001, 0.001)
            ln_m = ln_mm / 1000
            wd_hr = (wd_mm / pipe_circ_mm) * 12
            x0, x1 = cx - ln_m / 2, cx + ln_m / 2
            y0, y1 = cy - wd_hr / 2, cy + wd_hr / 2
            alpha = layer_alpha if use_opacity_overlay else 1.0
            color = _depth_color(f.get("depth"), alpha=alpha)
            line_alpha = alpha
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1, line=dict(color=f"rgba(0,0,0,{line_alpha})", width=2.5), fillcolor=color)

    for gw in girth_list:
        a = _alpha(gw)
        fig.add_vline(x=gw.get("chainage"), line_color=f"rgba(220,20,60,{a})", line_width=2.5)

    x_min_plot = min(x_values) if x_values else 0
    x_max_plot = max(x_values) if x_values else 1
    y_min_plot = min(y_values) if y_values else 0
    y_max_plot = max(y_values) if y_values else 12
    for sw in seam_list:
        oh = sw.get("orientation_hours", 6.0)
        ch_start = sw.get("chainage_start") if sw.get("chainage_start") is not None else x_min_plot
        ch_end = sw.get("chainage_end") if sw.get("chainage_end") is not None else x_max_plot
        a = _alpha(sw)
        fig.add_trace(go.Scatter(x=[ch_start, ch_end], y=[oh, oh], mode="lines", line=dict(color=f"rgba(0,0,255,{a})", width=2.5), showlegend=False, hoverinfo="skip"))

    hover_texts = [f.get("hover_text", "") for f in plot_features]
    plot_x = [f["x"] for f in plot_features]
    plot_y = [f.get("orientation_hours", 6.0) if use_orientation else f["y"] for f in plot_features]
    fig.add_trace(go.Scatter(x=plot_x, y=plot_y, mode="markers", marker=dict(size=4, color="rgba(0,0,0,0)"), text=hover_texts, hoverinfo="text"))

    annotations = [
        dict(x=1.02, y=0.98, xref="paper", yref="paper", text="Depth: 0-20% green, 20-40% yellow, 40-60% orange, >60% red", showarrow=False, font=dict(size=9), xanchor="left"),
        dict(x=1.02, y=0.88, xref="paper", yref="paper", text="Box size: length (mm) × width (mm)", showarrow=False, font=dict(size=8), xanchor="left"),
    ]
    for gw in girth_list:
        lbl = gw.get("label", "")
        if lbl:
            y_pos = y_min_plot + 0.7 * (y_max_plot - y_min_plot) if y_values else 6
            annotations.append(dict(x=gw["chainage"], y=y_pos, text=lbl, showarrow=False, font=dict(size=9, color="darkred"), textangle=-90, xanchor="right", yanchor="middle"))
    for sw in seam_list:
        lbl = sw.get("orientation_label", "")
        if lbl:
            ch_s, ch_e = sw.get("chainage_start"), sw.get("chainage_end")
            mid_x = ((ch_s or 0) + (ch_e or 0)) / 2 if (ch_s is not None or ch_e is not None) else (x_min_plot + x_max_plot) / 2
            annotations.append(dict(x=mid_x, y=sw.get("orientation_hours", 6) + 0.3, text=lbl, showarrow=False, font=dict(size=8, color="blue"), xanchor="center", yanchor="bottom"))

    x_axis_title = _get_x_axis_title(x_column)
    fig.update_layout(
        title=title,
        xaxis_title=x_axis_title,
        yaxis_title="Feature Orientation (hh:mm)",
        height=height,
        hovermode="closest",
        dragmode="pan",
        template="plotly_white",
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.2)", showline=True, linewidth=2, linecolor="black", mirror=True, tickformat=".3f", ticksuffix=" m"),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.2)", showline=True, linewidth=2, linecolor="black", mirror=True, tickvals=list(range(0, 13)), ticktext=[f"{h:02d}:00" for h in range(0, 13)], range=[0, 12]),
        annotations=annotations,
    )
    count = len(features) if use_opacity_overlay else selected_count
    return fig, count


@st.fragment
def render_feature_map_fragment(fm: dict, total_before_filter: int = None):
    """
    Fragment wrapper: when source checkboxes change, only this reruns (not the full app).
    Avoids slow re-execution of file upload, preview, backend calls, etc.
    """
    render_feature_map(fm, total_before_filter)


def render_feature_map(fm: dict, total_before_filter: int = None):
    """
    Render the unwrapped pipe feature map from FeatureMapResponse data.
    Used by both paste and upload modes.
    """
    features = fm.get("features", [])
    mapping = fm.get("column_mapping", {})
    scatter_data = fm.get("scatter_data") or {}
    all_sources = fm.get("sources", [])
    feature_summary_raw = fm.get("feature_summary_raw")

    st.markdown("### 🗺️ Feature Map")
    caption_parts = [
        "Unwrapped pipe view: X = chainage (m) or Distance from TGW (m); Y = orientation (o'clock). "
        "Feature boxes proportional to length (mm) × width (mm). Depth: green 0-20% WT, yellow 20-40%, orange 40-60%, red >60%. "
        "Red vertical lines = girth welds. Blue horizontal lines = longseam per span (changes at each GWD)."
    ]
    if all_sources:
        caption_parts.append("Deselected sources shown at 20% opacity for overlap comparison.")
    st.caption(" ".join(caption_parts))

    # NPS selector
    nps_options = sorted(NPS_TO_OD_MM.keys())
    nps_default = 10 if 10 in nps_options else nps_options[0]
    nps = st.selectbox(
        "**Pipe NPS (Nominal Pipe Size)**",
        options=nps_options,
        index=nps_options.index(nps_default),
        format_func=lambda x: f"NPS {x}",
        help="Select pipe size for width scaling. OD is used to convert feature width (mm) to circumferential position.",
    )
    pipe_od_mm = NPS_TO_OD_MM.get(nps, 273.0)
    pipe_circ_mm = 3.14159 * pipe_od_mm

    # Source filter: checkboxes for quick compare (only when data has source column values)
    selected_sources = set()
    if all_sources:
        st.markdown("**Filter by ILI Source** — check/uncheck to compare:")
        cols = st.columns(min(len(all_sources), 6))
        for i, src in enumerate(all_sources):
            with cols[i % len(cols)]:
                if st.checkbox(src, value=True, key=f"ili_source_{src}"):
                    selected_sources.add(src)
    filter_by_source = bool(all_sources)

    x_column = scatter_data.get("x_column", "ILI Chainage (m)")

    # Main chart: combined selected sources
    main_title = "ILI Feature Map (Unwrapped Pipe View)"
    if all_sources and selected_sources:
        main_title += f" — {' + '.join(sorted(selected_sources))}"
    fig, filtered_count = _build_feature_map_figure(
        features, scatter_data, pipe_circ_mm,
        selected_sources, filter_by_source, x_column,
        main_title, height=450,
        use_opacity_overlay=filter_by_source,
    )
    st.plotly_chart(fig, use_container_width=True)

    filter_msg = ""
    if total_before_filter is not None and filtered_count != total_before_filter:
        filter_msg = f" (filtered from {total_before_filter})"
    elif filtered_count != len(features):
        filter_msg = f" (filtered from {len(features)})"
    st.info(f"**{filtered_count} features** visualized" + filter_msg)

    # Breakdown visuals: one per source when multiple ILI sources exist
    if len(all_sources) >= 2:
        st.markdown("---")
        st.markdown("#### 📊 Breakdown by ILI Source")
        st.caption("Individual feature maps for each ILI source.")
        for src in all_sources:
            fig_breakdown, count = _build_feature_map_figure(
                features, scatter_data, pipe_circ_mm,
                {src}, True, x_column,
                f"Source: {src}",
                height=380,
            )
            fig_breakdown.update_layout(title=f"Source: {src} ({count} features)")
            st.plotly_chart(fig_breakdown, use_container_width=True)

    # Feature list (table view)
    st.markdown("---")
    st.markdown("#### 📋 Feature List")
    st.caption("Tabular view of all features. Use the source filter above to narrow the list.")
    # Build DataFrame from features (respect source filter)
    def _source_ok(f):
        src = f.get("source", "") or ""
        if not filter_by_source:
            return True
        return not selected_sources or src in selected_sources

    filtered = [f for f in features if _source_ok(f)]
    if filtered:
        def _fmt(v, decimals=2):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "-"
            if isinstance(v, (int, float)):
                return str(round(v, decimals)) if v == v else "-"
            return str(v)

        list_df = pd.DataFrame([
            {
                "Feature ID": str(f.get("feature_id", "") or ""),
                "Type": str(f.get("feature_type", "") or ""),
                "GWD": str(f.get("gwd_number")) if f.get("gwd_number") is not None else "-",
                "Depth (%)": _fmt(f.get("depth")),
                "Length (mm)": _fmt(f.get("length")),
                "Width (mm)": _fmt(f.get("width")),
                "Orientation": f"{f.get('orientation_hours', 6):.2f}" if f.get("orientation_hours") is not None else "-",
                "X (m)": _fmt(f.get("x"), 3),
                "Source": str(f.get("source", "") or ""),
            }
            for f in filtered
        ])
        st.dataframe(list_df, use_container_width=True, hide_index=True)
    else:
        st.info("No features to display (try adjusting the source filter).")

    if feature_summary_raw:
        st.markdown("---")
        st.markdown("#### 📍 Feature Summary (Data Source)")
        cap_parts = [
            f"**Sheet:** {feature_summary_raw.get('sheet', '?')} | "
            f"**Header row:** {feature_summary_raw.get('header_row', '?')} | "
            f"**Columns:** {', '.join(feature_summary_raw.get('columns', []))}"
        ]
        tgwd = feature_summary_raw.get("target_gwd")
        tlabel = feature_summary_raw.get("target_longseam_label")
        if tgwd is not None and tlabel:
            cap_parts.append(f" | **Target GWD {tgwd} longseam:** {tlabel} (blue lines per span)")
        st.caption("".join(cap_parts))
        st.caption("Column mapping: " + str(feature_summary_raw.get("column_mapping_used", {})))
        sample = feature_summary_raw.get("sample_rows", [])
        if sample:
            sample_df = pd.DataFrame(sample).fillna("-")
            # Ensure Arrow-compatible types (avoid mixed int/str causing serialization errors)
            sample_df = sample_df.astype(str)
            st.dataframe(sample_df, use_container_width=True, hide_index=True)

    with st.expander("📊 Column mapping used"):
        st.json(mapping)

# Page configuration
set_page_config("ILI Visual Tool", "🛢️")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

cols, chat_visible = get_layout_with_chat()
left_col, right_col = cols

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

    # Input mode: Dig Package (default), Upload Excel, or Paste
    input_mode = st.radio(
        "**Input format**",
        options=["Dig Package", "Upload Excel File", "Paste from Clipboard"],
        horizontal=True,
        help="Dig Package: sectioned Excel with Feature summary & Joint Summary. Upload: raw ILI Excel. Paste: tabular data from clipboard.",
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
    if "upload_feature_map_data" not in st.session_state:
        st.session_state.upload_feature_map_data = None

    if input_mode == "Dig Package":
        # ========== DIG PACKAGE MODE: Sectioned Excel with Feature summary & Joint Summary ==========
        st.markdown("### 📦 Dig Package")
        st.caption(
            "Upload a dig package Excel file with section headers. The tool extracts ILI features from "
            "**Feature summary** (bottom section), longseam orientation from **Joint Summary**. "
            "Uses **Distance from TGW (m)** as default x-axis. Supports multiple ILI sources."
        )

        dig_file = st.file_uploader(
            "Choose a dig package Excel file (.xlsx)",
            type=["xlsx"],
            key="dig_package_upload",
            help="Sectioned Excel with 'Feature summary' and optionally 'Joint Summary'",
        )

        if dig_file is not None:
            if st.session_state.uploaded_file != dig_file.name:
                st.session_state.uploaded_file = dig_file.name
                st.session_state.upload_feature_map_data = None

            st.success(f"✅ File uploaded: **{dig_file.name}**")

            if st.button("🚀 Process Dig Package", type="primary"):
                with st.spinner("Parsing dig package (Feature summary, Joint Summary)..."):
                    result = asyncio.run(call_process_dig_package_api(dig_file))
                    if result and result.get("success"):
                        st.session_state.upload_feature_map_data = result
                        st.success(f"✅ Parsed {result.get('total_rows', 0)} features!")
                    elif result and not result.get("success"):
                        st.error(result.get("error", "Process failed"))

            if st.session_state.upload_feature_map_data and st.session_state.upload_feature_map_data.get("success"):
                st.markdown("---")
                fm = st.session_state.upload_feature_map_data
                total_before = fm.get("total_rows")
                render_feature_map_fragment(fm, total_before_filter=total_before)
        else:
            st.info(
                """
                👆 **Upload a dig package Excel file**

                Dig packages are sectioned Excel files with headers like "Feature summary" and "Joint Summary".
                The tool auto-extracts ILI features and longseam orientation for visualization.
                """
            )

    elif input_mode == "Paste from Clipboard":
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
            st.markdown("---")
            render_feature_map_fragment(st.session_state.feature_map_data)

        else:
            st.info(
                """
                👆 **Paste your ILI data into the table above**

                Copy a table from Excel (with headers) and paste directly into the table. 
                Column format is preserved. Click **Generate Feature Map** to visualize.
                """
            )

    else:
        # ========== UPLOAD EXCEL MODE: Raw ILI Excel with sheet selection ==========
        st.markdown("### 📁 Step 1: Upload Excel File")
        uploaded_file = st.file_uploader(
            "Choose an Excel file (.xlsx or .xls)",
            type=["xlsx", "xls"],
            help="Maximum file size: 100 MB",
        )

        if uploaded_file is not None:
            if st.session_state.uploaded_file != uploaded_file.name:
                st.session_state.uploaded_file = uploaded_file.name
                st.session_state.preview_data = None
                st.session_state.upload_feature_map_data = None

            st.success(f"✅ File uploaded: **{uploaded_file.name}**")

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("🔍 Preview File", type="primary"):
                    with st.spinner("Loading file preview..."):
                        preview_data = asyncio.run(call_preview_api(uploaded_file))
                        if preview_data:
                            st.session_state.preview_data = preview_data

            if st.session_state.preview_data:
                st.markdown("---")
                st.markdown("### 📋 Step 2: File Preview")
                preview = st.session_state.preview_data
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Sheets found:** {len(preview['sheet_names'])}")
                with col2:
                    st.info(f"**Total rows:** {sum(preview['row_counts'].values())}")
                for sheet_name in preview["sheet_names"]:
                    with st.expander(f"📄 Sheet: **{sheet_name}** ({preview['row_counts'][sheet_name]} rows)"):
                        columns = preview["columns"][sheet_name]
                        st.write(f"**Columns ({len(columns)}):**")
                        st.write(", ".join(columns))

                st.markdown("---")
                st.markdown("### ⚙️ Step 3: Process and Visualize")
                st.caption("Columns are auto-identified. Optionally zoom to a section by GWD range or center ±3.")

                selected_sheet = st.selectbox(
                    "Select sheet to process",
                    options=preview["sheet_names"],
                    help="Choose which sheet contains your ILI data",
                )

                # GWD zoom filter (gwd_numbers available after first process)
                gwd_numbers = (st.session_state.upload_feature_map_data or {}).get("gwd_numbers", [])
                zoom_mode = st.radio(
                    "**Zoom to section**",
                    options=["Show all", "GWD range (start–end)", "Center GWD ±3"],
                    horizontal=True,
                    help="Filter by GWD numbers. Process once with 'Show all' to load available GWDs.",
                )
                gwd_start, gwd_end, gwd_center = None, None, None
                gwd_opts = [str(g) for g in gwd_numbers]
                if zoom_mode == "GWD range (start–end)" and gwd_opts:
                    c1, c2 = st.columns(2)
                    with c1:
                        gwd_start = st.selectbox("Start GWD", options=[""] + gwd_opts, format_func=lambda x: x or "—")
                        gwd_start = int(gwd_start) if gwd_start and gwd_start.isdigit() else None
                    with c2:
                        gwd_end = st.selectbox("End GWD", options=[""] + gwd_opts, format_func=lambda x: x or "—")
                        gwd_end = int(gwd_end) if gwd_end and gwd_end.isdigit() else None
                elif zoom_mode == "Center GWD ±3" and gwd_opts:
                    gwd_center = st.selectbox("Center GWD", options=[""] + gwd_opts, format_func=lambda x: x or "—")
                    gwd_center = int(gwd_center) if gwd_center and gwd_center.isdigit() else None

                if st.button("🚀 Process Data", type="primary"):
                    with st.spinner("Processing data (columns auto-identified)..."):
                        result = asyncio.run(
                            call_process_feature_map_api(
                                uploaded_file,
                                selected_sheet,
                                gwd_start=gwd_start,
                                gwd_end=gwd_end,
                                gwd_center=gwd_center,
                            )
                        )
                        if result and result.get("success"):
                            st.session_state.upload_feature_map_data = result
                            st.success(f"✅ Parsed {result.get('total_rows', 0)} features!")
                        elif result and not result.get("success"):
                            st.error(result.get("error", "Process failed"))

                if st.session_state.upload_feature_map_data and st.session_state.upload_feature_map_data.get("success"):
                    st.markdown("---")
                    fm = st.session_state.upload_feature_map_data
                    total_before = fm.get("total_rows")
                    render_feature_map_fragment(fm, total_before_filter=total_before)

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
