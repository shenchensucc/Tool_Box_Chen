"""
ILI Visual Dig Package Dev Tool

Local development tool for the ILI Visual dig package path. Uses the same
backend parser logic as the app and exposes what the visual pipeline can read
from an uploaded dig package Excel file.

Run:
    streamlit run dev_tools/ili_visual_dig_package_tool.py --server.runOnSave true
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.pipeline.dig_package_reader import (  # noqa: E402
    build_feature_map_from_dig_package,
    parse_dig_package_excel,
)
from backend.pipeline.ili_reader import identify_ili_columns  # noqa: E402


def _run_with_error_capture(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None, None
    except Exception as exc:  # pragma: no cover - dev tool diagnostics
        return None, str(exc), traceback.format_exc()


def _json_safe(val: Any):
    if pd.isna(val):
        return None
    if isinstance(val, (str, int, float, bool)) or val is None:
        return val
    try:
        fval = float(val)
        return int(fval) if fval == int(fval) else fval
    except (TypeError, ValueError):
        return str(val)


def _records(df: pd.DataFrame, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    if limit is not None:
        df = df.head(limit)
    return [{k: _json_safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _safe_df_for_display(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Avoid Streamlit/pyarrow crashes on duplicate column names."""
    if df is None:
        return None
    display_df = df.copy()
    counts: dict[str, int] = {}
    renamed = []
    for idx, col in enumerate(display_df.columns):
        base = str(col) if col is not None else f"_col{idx}"
        current = counts.get(base, 0)
        renamed.append(base if current == 0 else f"{base}__{current + 1}")
        counts[base] = current + 1
    display_df.columns = renamed
    return display_df


def _normalize_source_name(source: str) -> str:
    src = (source or "").strip().lower()
    for token in ["mfl-a", "mfl-c", "emat", "tool", "inspection"]:
        src = src.replace(token, "")
    return " ".join(src.split())


def _build_diagnostics(
    metadata: dict[str, Any],
    feature_df: pd.DataFrame | None,
    joint_df: pd.DataFrame | None,
    features: list[dict[str, Any]],
    scatter_data: dict[str, Any] | None,
    joint_summary_parsed: list[dict[str, Any]],
    feature_summary_raw: dict[str, Any] | None,
    sources: list[str],
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    notes: list[str] = []

    if not metadata.get("feature_section_found"):
        warnings.append("Feature summary section was not found.")
    if metadata.get("feature_section_found") and (feature_df is None or feature_df.empty):
        warnings.append("Feature summary section was detected but produced no rows.")

    if not metadata.get("joint_section_found"):
        warnings.append("Joint Summary section was not found. Blue longseam lines cannot be built from Joint Summary.")
    if metadata.get("joint_section_found") and (joint_df is None or joint_df.empty):
        warnings.append("Joint Summary section was detected but produced no rows.")
    if metadata.get("joint_section_found") and not joint_summary_parsed:
        warnings.append("Joint Summary was found but no longseam rows were parsed.")

    girth_welds = (scatter_data or {}).get("girth_welds", [])
    seam_welds = (scatter_data or {}).get("seam_welds", [])
    if len(girth_welds) >= 2 and not seam_welds:
        warnings.append("Girth welds were found but no seam weld spans were built.")
    if len(girth_welds) >= 2 and 0 < len(seam_welds) < (len(girth_welds) - 1):
        warnings.append(
            f"Only {len(seam_welds)} seam span(s) were built for {len(girth_welds)} girth welds; some spans may be missing."
        )

    target_label = (feature_summary_raw or {}).get("target_longseam_label")
    if metadata.get("joint_section_found") and not target_label:
        warnings.append("No target GWD longseam was merged into the feature-summary payload.")

    parsed_joint_sources = {
        _normalize_source_name(str(row.get("Source", "")))
        for row in joint_summary_parsed
        if row.get("Source")
    }
    feature_sources = {_normalize_source_name(src) for src in sources if src}
    if parsed_joint_sources and feature_sources:
        unmatched = sorted(src for src in feature_sources if src and src not in parsed_joint_sources)
        if unmatched:
            notes.append(
                "Some feature sources do not directly match parsed Joint Summary sources after simple normalization: "
                + ", ".join(unmatched[:6])
            )

    notes.append(f"Parsed {len(features)} features across {len(sources)} source(s).")
    notes.append(f"Built {len(girth_welds)} girth weld markers and {len(seam_welds)} seam line segment(s).")
    return warnings, notes


def _metric_value(val: Any, fallback: str = "-") -> str:
    return fallback if val is None or val == "" else str(val)


def _build_export_snapshot(
    filename: str,
    metadata: dict[str, Any],
    feature_df: pd.DataFrame | None,
    joint_df: pd.DataFrame | None,
    feature_mapping: dict[str, Any],
    result: tuple[list[dict[str, Any]], dict[str, Any] | None, list[str], dict[str, Any], list[dict[str, Any]], dict[str, Any] | None],
    warnings: list[str],
    notes: list[str],
) -> dict[str, Any]:
    features, scatter_data, sources, column_mapping, joint_summary_parsed, feature_summary_raw = result
    scatter_data = scatter_data or {}
    return {
        "filename": filename,
        "metadata": metadata,
        "feature_summary_shape": list(feature_df.shape) if feature_df is not None else None,
        "joint_summary_shape": list(joint_df.shape) if joint_df is not None else None,
        "feature_mapping_detected": feature_mapping,
        "column_mapping_used": column_mapping,
        "sources": sources,
        "girth_weld_count": len(scatter_data.get("girth_welds", [])),
        "seam_weld_count": len(scatter_data.get("seam_welds", [])),
        "feature_count": len(features),
        "target_gwd": (feature_summary_raw or {}).get("target_gwd"),
        "target_longseam_label": (feature_summary_raw or {}).get("target_longseam_label"),
        "joint_summary_parsed": joint_summary_parsed,
        "seam_welds": scatter_data.get("seam_welds", []),
        "girth_welds": scatter_data.get("girth_welds", []),
        "feature_summary_raw": feature_summary_raw,
        "feature_summary_sample": _records(feature_df, limit=20),
        "joint_summary_sample": _records(joint_df, limit=20),
        "warnings": warnings,
        "notes": notes,
    }


def main():
    st.set_page_config(page_title="ILI Visual Dig Package Dev Tool", page_icon="toolbox", layout="wide")
    st.title("ILI Visual Dig Package Dev Tool")
    st.caption(
        "Developer-only inspector for the ILI Visual dig package path. "
        "Upload one dig package and see exactly what the parser reads, maps, and turns into blue seam lines."
    )

    with st.sidebar:
        st.subheader("Run")
        st.code("streamlit run dev_tools/ili_visual_dig_package_tool.py --server.runOnSave true", language="bash")
        st.subheader("Focus")
        st.caption("This tool is only for the ILI Visual dig package workflow, not dig package generation.")

    col_upload, col_path = st.columns(2)
    with col_upload:
        upload = st.file_uploader("Upload dig package Excel (.xlsx)", type=["xlsx"], key="ili_dp_upload")
    with col_path:
        rel_path = st.text_input(
            "Or enter path relative to project root",
            placeholder="dev_tools/fixtures/sample_dig_package.xlsx",
            key="ili_dp_path",
        )

    file_bytes = None
    file_name = None
    if upload is not None:
        file_bytes = upload.getvalue()
        file_name = upload.name
    elif rel_path.strip():
        path = ROOT / rel_path.strip()
        if path.exists():
            file_bytes = path.read_bytes()
            file_name = path.name
        else:
            st.warning(f"Path not found: {path}")

    if not file_bytes:
        st.info("Upload a dig package Excel file or enter a relative path to inspect what the ILI visual parser can read.")
        return

    st.success(f"Loaded file: {file_name}")

    parsed_sections, parse_err, parse_tb = _run_with_error_capture(parse_dig_package_excel, file_bytes)
    if parse_err:
        st.error(f"Section parse failed: {parse_err}")
        with st.expander("Full traceback"):
            st.code(parse_tb, language="text")
        return

    feature_df, joint_df, metadata = parsed_sections
    feature_mapping = identify_ili_columns(feature_df) if feature_df is not None and not feature_df.empty else {}

    full_result, build_err, build_tb = _run_with_error_capture(build_feature_map_from_dig_package, file_bytes)
    if build_err:
        st.error(f"Feature-map build failed: {build_err}")
        with st.expander("Full traceback"):
            st.code(build_tb, language="text")
        full_result = ([], None, [], {}, [], None)

    features, scatter_data, sources, column_mapping, joint_summary_parsed, feature_summary_raw = full_result
    scatter_data = scatter_data or {}
    warnings, notes = _build_diagnostics(
        metadata,
        feature_df,
        joint_df,
        features,
        scatter_data,
        joint_summary_parsed,
        feature_summary_raw,
        sources,
    )

    target_gwd = (feature_summary_raw or {}).get("target_gwd")
    target_longseam = (feature_summary_raw or {}).get("target_longseam_label")

    st.subheader("Summary")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Feature rows", len(feature_df) if feature_df is not None else 0)
    m2.metric("Joint rows", len(joint_df) if joint_df is not None else 0)
    m3.metric("Features built", len(features))
    m4.metric("Girth welds", len(scatter_data.get("girth_welds", [])))
    m5.metric("Seam spans", len(scatter_data.get("seam_welds", [])))
    m6.metric("Sources", len(sources))

    m7, m8, m9, m10 = st.columns(4)
    m7.metric("Feature section", "yes" if metadata.get("feature_section_found") else "no")
    m8.metric("Joint section", "yes" if metadata.get("joint_section_found") else "no")
    m9.metric("Target GWD", _metric_value(target_gwd))
    m10.metric("Target longseam", _metric_value(target_longseam))

    if warnings:
        st.subheader("Diagnostics")
        for item in warnings:
            st.warning(item)
    else:
        st.subheader("Diagnostics")
        st.success("No obvious parsing gaps were detected for this file.")

    for item in notes:
        st.caption(item)

    tab_summary, tab_feature, tab_joint, tab_outputs, tab_export = st.tabs(
        ["Metadata", "Feature Summary", "Joint Summary", "Visual Outputs", "Export Snapshot"]
    )

    with tab_summary:
        left, right = st.columns(2)
        with left:
            st.markdown("**Section metadata**")
            st.json(metadata)
        with right:
            st.markdown("**Column mapping used by visual path**")
            if column_mapping:
                st.dataframe(
                    pd.DataFrame(
                        [(k, v) for k, v in column_mapping.items()],
                        columns=["Standard key", "Actual column"],
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No final column mapping was built.")

        st.markdown("**Auto-detected ILI columns from Feature summary**")
        if feature_mapping:
            st.dataframe(
                pd.DataFrame(
                    [(k, v) for k, v in feature_mapping.items()],
                    columns=["Detected key", "Actual column"],
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No feature summary mapping could be detected.")

        st.markdown("**Feature summary payload merged into visual response**")
        if feature_summary_raw:
            st.json(feature_summary_raw)
        else:
            st.info("No feature summary raw payload was returned.")

    with tab_feature:
        st.markdown("**Raw Feature summary table**")
        if feature_df is not None and not feature_df.empty:
            st.dataframe(_safe_df_for_display(feature_df), use_container_width=True, height=320)
        else:
            st.info("Feature summary table is empty.")

        st.markdown("**Feature rows sent to the visual**")
        if features:
            feature_preview = pd.DataFrame(features)
            preferred_cols = [
                "feature_id",
                "feature_type",
                "x",
                "depth",
                "length",
                "width",
                "orientation_hours",
                "seam_orient_hours",
                "gwd_number",
                "source",
            ]
            preview_cols = [c for c in preferred_cols if c in feature_preview.columns]
            st.dataframe(
                feature_preview[preview_cols] if preview_cols else feature_preview,
                use_container_width=True,
                height=360,
            )
        else:
            st.info("No features were built.")

    with tab_joint:
        st.markdown("**Raw Joint Summary table**")
        if joint_df is not None and not joint_df.empty:
            st.dataframe(_safe_df_for_display(joint_df), use_container_width=True, height=320)
        else:
            st.info("Joint Summary table is empty or missing.")

        st.markdown("**Parsed Joint Summary rows used for longseam logic**")
        if joint_summary_parsed:
            st.dataframe(pd.DataFrame(joint_summary_parsed), use_container_width=True, height=360)
        else:
            st.info("No parsed Joint Summary rows were produced.")

    with tab_outputs:
        left, right = st.columns(2)
        with left:
            st.markdown("**Girth weld markers**")
            girth_welds = scatter_data.get("girth_welds", [])
            if girth_welds:
                st.dataframe(pd.DataFrame(girth_welds), use_container_width=True, height=320)
            else:
                st.info("No girth weld markers were built.")
        with right:
            st.markdown("**Blue seam line segments**")
            seam_welds = scatter_data.get("seam_welds", [])
            if seam_welds:
                st.dataframe(pd.DataFrame(seam_welds), use_container_width=True, height=320)
            else:
                st.info("No seam line segments were built.")

        st.markdown("**Scatter payload**")
        st.json(
            {
                "x_column": scatter_data.get("x_column"),
                "source_count": len(sources),
                "girth_weld_count": len(scatter_data.get("girth_welds", [])),
                "seam_weld_count": len(scatter_data.get("seam_welds", [])),
            }
        )

    with tab_export:
        snapshot = _build_export_snapshot(
            file_name,
            metadata,
            feature_df,
            joint_df,
            feature_mapping,
            full_result,
            warnings,
            notes,
        )
        st.markdown("**JSON snapshot**")
        st.json(snapshot)
        st.download_button(
            "Download JSON snapshot",
            data=json.dumps(snapshot, indent=2),
            file_name=f"{Path(file_name).stem}_ili_visual_debug.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
