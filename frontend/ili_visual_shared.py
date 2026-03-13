import asyncio

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend_utils import (
    call_parse_paste_api,
    call_preview_api,
    call_process_dig_package_api,
    call_process_feature_map_api,
)

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


def _format_joint_context_summary(joint_context: dict | None) -> str:
    if not joint_context:
        return ""
    parts = []
    role_labels = [("upstream", "U/S"), ("target", "Target"), ("downstream", "D/S")]
    for role_key, role_label in role_labels:
        item = joint_context.get(role_key)
        if not item:
            continue
        gwd = item.get("gwd_number")
        seam = item.get("longseam_label")
        if gwd is None:
            continue
        text = f"{role_label} GWD {gwd}"
        if seam:
            text += f" @ {seam}"
        parts.append(text)
    joint_source = joint_context.get("joint_source")
    if joint_source and parts:
        return f"{joint_source}: " + " | ".join(parts)
    return " | ".join(parts)


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
        src = f_or_gw.get("feature_source") or f_or_gw.get("source", "") or ""
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
        plot_features = [
            f
            for f in features
            if "girth" not in (f.get("feature_type") or "").lower()
            and "seam" not in (f.get("feature_type") or "").lower()
            and "gwd" not in (f.get("feature_type") or "").lower()
        ]
        girth_list = scatter_data.get("girth_welds", [])
        seam_list = scatter_data.get("seam_welds", [])
        selected_count = sum(1 for f in features if _is_selected(f))
    else:
        filtered_features = [f for f in features if _is_selected(f)]
        plot_features = [
            f
            for f in filtered_features
            if "girth" not in (f.get("feature_type") or "").lower()
            and "seam" not in (f.get("feature_type") or "").lower()
            and "gwd" not in (f.get("feature_type") or "").lower()
        ]
        girth_list = [gw for gw in scatter_data.get("girth_welds", []) if _is_selected(gw)]
        seam_list = [sw for sw in scatter_data.get("seam_welds", []) if _is_selected(sw)]
        selected_count = len(filtered_features)

    x_values = scatter_data.get("x_values", [f["x"] for f in features])
    orient_hours = scatter_data.get("orientation_hours")
    use_orientation = orient_hours and len(orient_hours) == len(features)
    y_values = orient_hours if use_orientation else [f["y"] for f in features]
    joint_context_by_source = scatter_data.get("joint_context_by_source", {})

    fig = go.Figure()
    # Draw deselected first (lower layer), then selected (on top) for clearer overlap
    for layer_alpha, layer_features in [
        (0.2, [f for f in plot_features if not _is_selected(f)]),
        (1.0, [f for f in plot_features if _is_selected(f)]),
    ]:
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
            fig.add_shape(
                type="rect",
                x0=x0,
                x1=x1,
                y0=y0,
                y1=y1,
                line=dict(color=f"rgba(0,0,0,{line_alpha})", width=2.5),
                fillcolor=color,
            )

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
        fig.add_trace(
            go.Scatter(
                x=[ch_start, ch_end],
                y=[oh, oh],
                mode="lines",
                line=dict(color=f"rgba(0,0,255,{a})", width=2.5),
                showlegend=False,
                hoverinfo="skip",
            )
        )

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
        dict(
            x=1.02,
            y=0.98,
            xref="paper",
            yref="paper",
            text="Depth: 0-20% green, 20-40% yellow, 40-60% orange, >60% red",
            showarrow=False,
            font=dict(size=9),
            xanchor="left",
        ),
        dict(
            x=1.02,
            y=0.88,
            xref="paper",
            yref="paper",
            text="Box size: length (mm) × width (mm)",
            showarrow=False,
            font=dict(size=8),
            xanchor="left",
        ),
    ]
    for gw in girth_list:
        lbl = gw.get("label", "")
        if lbl:
            y_pos = y_min_plot + 0.7 * (y_max_plot - y_min_plot) if y_values else 6
            annotations.append(
                dict(
                    x=gw["chainage"],
                    y=y_pos,
                    text=lbl,
                    showarrow=False,
                    font=dict(size=9, color="darkred"),
                    textangle=-90,
                    xanchor="right",
                    yanchor="middle",
                )
            )
    for sw in seam_list:
        lbl = sw.get("orientation_label", "")
        if lbl:
            ch_s, ch_e = sw.get("chainage_start"), sw.get("chainage_end")
            mid_x = (
                ((ch_s or 0) + (ch_e or 0)) / 2
                if (ch_s is not None or ch_e is not None)
                else (x_min_plot + x_max_plot) / 2
            )
            annotations.append(
                dict(
                    x=mid_x,
                    y=sw.get("orientation_hours", 6) + 0.3,
                    text=lbl,
                    showarrow=False,
                    font=dict(size=8, color="blue"),
                    xanchor="center",
                    yanchor="bottom",
                )
            )

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
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.2)",
            showline=True,
            linewidth=2,
            linecolor="black",
            mirror=True,
            tickformat=".3f",
            ticksuffix=" m",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.2)",
            showline=True,
            linewidth=2,
            linecolor="black",
            mirror=True,
            tickvals=list(range(0, 13)),
            ticktext=[f"{h:02d}:00" for h in range(0, 13)],
            range=[0, 12],
        ),
        annotations=annotations,
    )
    count = len(features) if use_opacity_overlay else selected_count
    return fig, count


@st.fragment
def render_feature_map_fragment(
    fm: dict,
    total_before_filter: int | None = None,
    key_prefix: str = "ili",
):
    """
    Fragment wrapper: when source checkboxes change, only this reruns (not the full app).
    Avoids slow re-execution of file upload, preview, backend calls, etc.
    """
    render_feature_map(fm, total_before_filter=total_before_filter, key_prefix=key_prefix)


def render_feature_map(
    fm: dict,
    total_before_filter: int | None = None,
    key_prefix: str = "ili",
):
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

    nps_options = sorted(NPS_TO_OD_MM.keys())
    nps_default = 10 if 10 in nps_options else nps_options[0]
    nps = st.selectbox(
        "**Pipe NPS (Nominal Pipe Size)**",
        options=nps_options,
        index=nps_options.index(nps_default),
        format_func=lambda x: f"NPS {x}",
        help="Select pipe size for width scaling. OD is used to convert feature width (mm) to circumferential position.",
        key=f"{key_prefix}_nps_select",
    )
    pipe_od_mm = NPS_TO_OD_MM.get(nps, 273.0)
    pipe_circ_mm = 3.14159 * pipe_od_mm

    selected_sources = set()
    if all_sources:
        st.markdown("**Filter by ILI Source** — check/uncheck to compare:")
        cols = st.columns(min(len(all_sources), 6))
        for i, src in enumerate(all_sources):
            with cols[i % len(cols)]:
                if st.checkbox(src, value=True, key=f"{key_prefix}_source_{src}"):
                    selected_sources.add(src)
    filter_by_source = bool(all_sources)

    x_column = scatter_data.get("x_column", "ILI Chainage (m)")
    joint_context_by_source = scatter_data.get("joint_context_by_source", {})

    def _selected_joint_contexts(active_sources: set[str]) -> list[dict]:
        if not joint_context_by_source:
            return []
        if active_sources:
            return [
                joint_context_by_source[src]
                for src in all_sources
                if src in active_sources and src in joint_context_by_source
            ]
        return [joint_context_by_source[src] for src in all_sources if src in joint_context_by_source]

    main_title = "ILI Feature Map (Unwrapped Pipe View)"
    if all_sources and selected_sources:
        main_title += f" — {' + '.join(sorted(selected_sources))}"
    fig, filtered_count = _build_feature_map_figure(
        features,
        scatter_data,
        pipe_circ_mm,
        selected_sources,
        filter_by_source,
        x_column,
        main_title,
        height=450,
        use_opacity_overlay=filter_by_source,
    )
    st.plotly_chart(fig, use_container_width=True)

    combined_contexts = _selected_joint_contexts(selected_sources)
    if combined_contexts:
        st.caption(
            "Joint context: "
            + " || ".join(
                _format_joint_context_summary(ctx)
                for ctx in combined_contexts
                if _format_joint_context_summary(ctx)
            )
        )

    filter_msg = ""
    if total_before_filter is not None and filtered_count != total_before_filter:
        filter_msg = f" (filtered from {total_before_filter})"
    elif filtered_count != len(features):
        filter_msg = f" (filtered from {len(features)})"
    st.info(f"**{filtered_count} features** visualized" + filter_msg)

    if len(all_sources) >= 2:
        st.markdown("---")
        st.markdown("#### 📊 Breakdown by ILI Source")
        st.caption("Individual feature maps for each ILI source.")
        for src in all_sources:
            fig_breakdown, count = _build_feature_map_figure(
                features,
                scatter_data,
                pipe_circ_mm,
                {src},
                True,
                x_column,
                f"Source: {src}",
                height=380,
            )
            fig_breakdown.update_layout(title=f"Source: {src} ({count} features)")
            st.plotly_chart(fig_breakdown, use_container_width=True)
            src_context = joint_context_by_source.get(src)
            if src_context:
                st.caption("Joint context: " + _format_joint_context_summary(src_context))

    st.markdown("---")
    st.markdown("#### 📋 Feature List")
    st.caption("Tabular view of all features. Use the source filter above to narrow the list.")

    def _source_ok(feature: dict) -> bool:
        src = feature.get("source", "") or ""
        if not filter_by_source:
            return True
        return not selected_sources or src in selected_sources

    filtered = [feature for feature in features if _source_ok(feature)]
    if filtered:

        def _fmt(value, decimals=2):
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return "-"
            if isinstance(value, (int, float)):
                return str(round(value, decimals)) if value == value else "-"
            return str(value)

        list_df = pd.DataFrame(
            [
                {
                    "Feature ID": str(feature.get("feature_id", "") or ""),
                    "Type": str(feature.get("feature_type", "") or ""),
                    "GWD": str(feature.get("gwd_number"))
                    if feature.get("gwd_number") is not None
                    else "-",
                    "Depth (%)": _fmt(feature.get("depth")),
                    "Length (mm)": _fmt(feature.get("length")),
                    "Width (mm)": _fmt(feature.get("width")),
                    "Orientation": f"{feature.get('orientation_hours', 6):.2f}"
                    if feature.get("orientation_hours") is not None
                    else "-",
                    "X (m)": _fmt(feature.get("x"), 3),
                    "Source": str(feature.get("source", "") or ""),
                }
                for feature in filtered
            ]
        )
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
        joint_contexts = feature_summary_raw.get("joint_context_by_source", {})
        if joint_contexts:
            for src, ctx in joint_contexts.items():
                summary = _format_joint_context_summary(ctx)
                if summary:
                    st.caption(f"**{src}** -> {summary}")
        st.caption("Column mapping: " + str(feature_summary_raw.get("column_mapping_used", {})))
        sample = feature_summary_raw.get("sample_rows", [])
        if sample:
            sample_df = pd.DataFrame(sample).fillna("-")
            sample_df = sample_df.astype(str)
            st.dataframe(sample_df, use_container_width=True, hide_index=True)

    with st.expander("📊 Column mapping used"):
        st.json(mapping)


def _prepare_data_for_api(df: pd.DataFrame) -> str:
    """If first row looks like ILI headers, use it as column names."""
    if df.empty or len(df) < 1:
        return ""
    first_row = df.iloc[0].astype(str).str.strip()
    header_keywords = [
        "ili",
        "chainage",
        "distance",
        "depth",
        "feature",
        "length",
        "width",
        "orientation",
        "odometer",
    ]
    first_row_lower = " ".join(first_row.str.lower())
    if len(df) >= 2 and any(keyword in first_row_lower for keyword in header_keywords):
        new_cols = [str(value).strip() or f"_col{i}" for i, value in enumerate(first_row)]
        out = df.iloc[1:].copy()
        column_count = len(out.columns)
        out.columns = [new_cols[i] if i < len(new_cols) else f"_col{i}" for i in range(column_count)]
        return out.to_csv(index=False).strip()
    return df.to_csv(index=False).strip()


def _init_ili_session_state() -> None:
    st.session_state.setdefault("ili_preview_data", None)
    st.session_state.setdefault("ili_feature_map_data", None)
    st.session_state.setdefault("ili_upload_file_name", None)
    st.session_state.setdefault("ili_upload_feature_map_data", None)
    st.session_state.setdefault("ili_pasted_df", pd.DataFrame([[""] * 15]))


def _init_dig_package_session_state() -> None:
    st.session_state.setdefault("dig_package_uploaded_file", None)
    st.session_state.setdefault("dig_package_feature_map_data", None)


def render_dig_package_visual_tool() -> None:
    _init_dig_package_session_state()

    st.markdown("### 📦 Dig Package")
    st.caption(
        "Upload a dig package Excel file with section headers. The tool extracts ILI features from "
        "**Feature summary** and longseam orientation from **Joint Summary**. "
        "Uses **Distance from TGW (m)** as the default x-axis and supports multiple ILI sources."
    )

    dig_file = st.file_uploader(
        "Choose a dig package Excel file (.xlsx)",
        type=["xlsx"],
        key="dig_package_upload",
        help="Sectioned Excel with 'Feature summary' and optionally 'Joint Summary'",
    )

    if dig_file is not None:
        if st.session_state.dig_package_uploaded_file != dig_file.name:
            st.session_state.dig_package_uploaded_file = dig_file.name
            st.session_state.dig_package_feature_map_data = None

        st.success(f"✅ File uploaded: **{dig_file.name}**")

        if st.button("🚀 Process Dig Package", type="primary", key="dig_package_process_button"):
            with st.spinner("Parsing dig package (Feature summary, Joint Summary)..."):
                result = asyncio.run(call_process_dig_package_api(dig_file))
                if result and result.get("success"):
                    st.session_state.dig_package_feature_map_data = result
                    st.success(f"✅ Parsed {result.get('total_rows', 0)} features!")
                elif result and not result.get("success"):
                    st.error(result.get("error", "Process failed"))

        if (
            st.session_state.dig_package_feature_map_data
            and st.session_state.dig_package_feature_map_data.get("success")
        ):
            st.markdown("---")
            fm = st.session_state.dig_package_feature_map_data
            total_before = fm.get("total_rows")
            render_feature_map_fragment(
                fm,
                total_before_filter=total_before,
                key_prefix="dig_package",
            )
    else:
        st.info(
            """
            👆 **Upload a dig package Excel file**

            Dig packages are sectioned Excel files with headers like "Feature summary" and "Joint Summary".
            The tool auto-extracts ILI features and longseam orientation for visualization.
            """
        )


def _render_ili_paste_mode() -> None:
    st.markdown("### 📋 Paste ILI Data")
    st.caption(
        "Copy a table from Excel (including header row) and paste directly into the table below. "
        "Click Generate to visualize."
    )

    col_config = {
        str(i): st.column_config.TextColumn(label=" ", width="small") for i in range(20)
    }
    edited_df = st.data_editor(
        st.session_state.ili_pasted_df,
        use_container_width=True,
        num_rows="dynamic",
        key="ili_paste_editor",
        hide_index=True,
        column_config=col_config,
    )
    st.session_state.ili_pasted_df = edited_df

    if st.button("🗺️ Generate Feature Map", type="primary", key="ili_paste_generate"):
        to_send = _prepare_data_for_api(edited_df) if not edited_df.empty else ""
        if not to_send or edited_df.empty:
            st.warning("Please paste data into the table above (copy from Excel and paste).")
        else:
            with st.spinner("Parsing and mapping columns..."):
                result = asyncio.run(call_parse_paste_api(to_send))
                if result and result.get("success"):
                    st.session_state.ili_feature_map_data = result
                    st.success(f"✅ Parsed {result.get('total_rows', 0)} features!")
                elif result and not result.get("success"):
                    st.error(result.get("error", "Parse failed"))

    if st.session_state.ili_feature_map_data and st.session_state.ili_feature_map_data.get("success"):
        st.markdown("---")
        render_feature_map_fragment(st.session_state.ili_feature_map_data, key_prefix="ili_paste")
    else:
        st.info(
            """
            👆 **Paste your ILI data into the table above**

            Copy a table from Excel (with headers) and paste directly into the table.
            Column format is preserved. Click **Generate Feature Map** to visualize.
            """
        )


def _render_ili_upload_mode() -> None:
    st.markdown("### 📁 Step 1: Upload Excel File")
    uploaded_file = st.file_uploader(
        "Choose an Excel file (.xlsx or .xls)",
        type=["xlsx", "xls"],
        help="Maximum file size: 100 MB",
        key="ili_upload_excel_file",
    )

    if uploaded_file is not None:
        if st.session_state.ili_upload_file_name != uploaded_file.name:
            st.session_state.ili_upload_file_name = uploaded_file.name
            st.session_state.ili_preview_data = None
            st.session_state.ili_upload_feature_map_data = None

        st.success(f"✅ File uploaded: **{uploaded_file.name}**")

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🔍 Preview File", type="primary", key="ili_preview_button"):
                with st.spinner("Loading file preview..."):
                    preview_data = asyncio.run(call_preview_api(uploaded_file))
                    if preview_data:
                        st.session_state.ili_preview_data = preview_data

        if st.session_state.ili_preview_data:
            st.markdown("---")
            st.markdown("### 📋 Step 2: File Preview")
            preview = st.session_state.ili_preview_data
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
                key="ili_selected_sheet",
            )

            gwd_numbers = (st.session_state.ili_upload_feature_map_data or {}).get("gwd_numbers", [])
            zoom_mode = st.radio(
                "**Zoom to section**",
                options=["Show all", "GWD range (start–end)", "Center GWD ±3"],
                horizontal=True,
                help="Filter by GWD numbers. Process once with 'Show all' to load available GWDs.",
                key="ili_zoom_mode",
            )
            gwd_start, gwd_end, gwd_center = None, None, None
            gwd_opts = [str(gwd) for gwd in gwd_numbers]
            if zoom_mode == "GWD range (start–end)" and gwd_opts:
                c1, c2 = st.columns(2)
                with c1:
                    gwd_start = st.selectbox(
                        "Start GWD",
                        options=[""] + gwd_opts,
                        format_func=lambda x: x or "—",
                        key="ili_gwd_start",
                    )
                    gwd_start = int(gwd_start) if gwd_start and gwd_start.isdigit() else None
                with c2:
                    gwd_end = st.selectbox(
                        "End GWD",
                        options=[""] + gwd_opts,
                        format_func=lambda x: x or "—",
                        key="ili_gwd_end",
                    )
                    gwd_end = int(gwd_end) if gwd_end and gwd_end.isdigit() else None
            elif zoom_mode == "Center GWD ±3" and gwd_opts:
                gwd_center = st.selectbox(
                    "Center GWD",
                    options=[""] + gwd_opts,
                    format_func=lambda x: x or "—",
                    key="ili_gwd_center",
                )
                gwd_center = int(gwd_center) if gwd_center and gwd_center.isdigit() else None

            if st.button("🚀 Process Data", type="primary", key="ili_process_button"):
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
                        st.session_state.ili_upload_feature_map_data = result
                        st.success(f"✅ Parsed {result.get('total_rows', 0)} features!")
                    elif result and not result.get("success"):
                        st.error(result.get("error", "Process failed"))

            if (
                st.session_state.ili_upload_feature_map_data
                and st.session_state.ili_upload_feature_map_data.get("success")
            ):
                st.markdown("---")
                fm = st.session_state.ili_upload_feature_map_data
                total_before = fm.get("total_rows")
                render_feature_map_fragment(
                    fm,
                    total_before_filter=total_before,
                    key_prefix="ili_upload",
                )
    else:
        st.info(
            """
            👆 **Upload an Excel file** with ILI (In-Line Inspection) data

            The tool visualizes pipeline features by chainage and depth.
            No assessment or statistics — visualization only.
            """
        )


def render_ili_visual_tool() -> None:
    _init_ili_session_state()

    input_mode = st.radio(
        "**Input format**",
        options=["Upload Excel File", "Paste from Clipboard"],
        horizontal=True,
        help="Upload a raw ILI Excel file or paste tabular ILI data from the clipboard.",
        key="ili_input_mode",
    )

    if input_mode == "Paste from Clipboard":
        _render_ili_paste_mode()
    else:
        _render_ili_upload_mode()
