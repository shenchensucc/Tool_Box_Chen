"""
Dig Package Reader for ILI Visual Tool

Parses dig package Excel files that are visually broken down by sections with headers.
- Extracts ILI feature details from "Feature summary" section (typically bottom)
- Extracts longseam orientation from "Joint Summary" section
- Supports multiple ILI sources
- Uses "Distance from TGW (m)" as default x-axis

Shared with dig_package module: uses ili_reader.identify_ili_columns and similar column mapping.
"""

import io
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook

from backend.logging_config import get_logger
from backend.pipeline.ili_reader import identify_ili_columns, find_column_names
from backend.pipeline.ili_reader import COLUMN_KEYWORDS
from backend.pipeline.feature_map_builder import (
    build_feature_map_from_df,
    format_orientation_hours,
    parse_orientation_to_hours,
)

logger = get_logger("backend.pipeline.dig_package_reader")

# Section header keywords (case-insensitive) to locate data blocks
FEATURE_SUMMARY_KEYWORDS = ["feature summary", "feature summary table", "ili feature summary"]
JOINT_SUMMARY_KEYWORDS = ["joint summary", "joint summary table", "girth weld summary"]

# Prefer "Distance from TGW (m)" as default x-axis for dig packages
DIG_PACKAGE_DISTANCE_KEYWORDS = [
    "Distance from TGW (m)",
    "Distance from TGW",
    "distance from tgw",
    "ILI Chainage (m)",
    "Chainage",
    "Odometer",
    "Log Dist.",
]


def _find_section_start_row(ws, keywords: List[str]) -> Optional[int]:
    """
    Find the first row where a section header matches any keyword.
    Section headers are typically in column A or merged cells.
    """
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=500), start=1):
        for cell in row[:5]:  # Check first 5 columns
            val = cell.value
            if val is None:
                continue
            val_str = str(val).strip().lower()
            for kw in keywords:
                if kw.lower() in val_str or val_str in kw.lower():
                    return row_idx
    return None


def _find_header_row_after(ws, start_row: int) -> Optional[int]:
    """
    Find the row containing column headers (first row with multiple non-empty cells).
    Typically the row immediately after section header or a few rows down.
    """
    for row_idx in range(start_row + 1, min(start_row + 20, ws.max_row + 1)):
        row = list(ws.iter_rows(min_row=row_idx, max_row=row_idx))[0]
        vals = [str(c.value).strip() if c.value is not None else "" for c in row[:20]]
        non_empty = [v for v in vals if v and len(v) > 1]
        if len(non_empty) >= 3:  # At least 3 columns with content
            return row_idx
    return None


def _read_section_as_dataframe(ws, header_row: int) -> pd.DataFrame:
    """Read data from header_row to end of contiguous data."""
    headers = [cell.value for cell in list(ws.iter_rows(min_row=header_row, max_row=header_row))[0]]
    # Clean headers
    headers = [str(h).strip() if h is not None else f"_col{i}" for i, h in enumerate(headers)]
    data = []
    for row_idx in range(header_row + 1, ws.max_row + 1):
        row = list(ws.iter_rows(min_row=row_idx, max_row=row_idx))[0]
        vals = [cell.value for cell in row[:len(headers)]]
        if not any(v is not None and str(v).strip() for v in vals):
            # Empty row - stop if we've seen data, or continue for sparse tables
            if data:
                break
            continue
        data.append(vals)
    # Pad rows to match header length
    n_cols = len(headers)
    for i, row in enumerate(data):
        if len(row) < n_cols:
            data[i] = row + [None] * (n_cols - len(row))
        elif len(row) > n_cols:
            data[i] = row[:n_cols]
    return pd.DataFrame(data, columns=headers)


def parse_dig_package_excel(file_content: bytes) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Dict[str, Any]]:
    """
    Parse a dig package Excel file with section headers.

    Returns:
        (feature_summary_df, joint_summary_df, metadata)
        - feature_summary_df: ILI features from "Feature summary" section
        - joint_summary_df: Joint/girth weld data from "Joint Summary" (for longseam orientation)
        - metadata: dict with section info, sheet used, etc.
    """
    wb = load_workbook(io.BytesIO(file_content), data_only=True, read_only=False)
    metadata = {"sheets_searched": [], "feature_section_found": False, "joint_section_found": False}

    feature_df = None
    joint_df = None

    for sheet_name in wb.sheetnames:
        metadata["sheets_searched"].append(sheet_name)
        ws = wb[sheet_name]

        # Look for Feature summary section
        if feature_df is None:
            start_row = _find_section_start_row(ws, FEATURE_SUMMARY_KEYWORDS)
            if start_row is not None:
                header_row = _find_header_row_after(ws, start_row)
                if header_row is not None:
                    feature_df = _read_section_as_dataframe(ws, header_row)
                    if not feature_df.empty:
                        metadata["feature_section_found"] = True
                        metadata["feature_sheet"] = sheet_name
                        metadata["feature_header_row"] = header_row

        # Look for Joint Summary section (for longseam orientation)
        if joint_df is None:
            start_row = _find_section_start_row(ws, JOINT_SUMMARY_KEYWORDS)
            if start_row is not None:
                header_row = _find_header_row_after(ws, start_row)
                if header_row is not None:
                    joint_df = _read_section_as_dataframe(ws, header_row)
                    if not joint_df.empty:
                        metadata["joint_section_found"] = True
                        metadata["joint_sheet"] = sheet_name
                        metadata["joint_header_row"] = header_row

        if feature_df is not None and joint_df is not None:
            break

    wb.close()
    return feature_df, joint_df, metadata


def _parse_joint_summary_matrix(
    joint_df: pd.DataFrame,
    parse_orientation_to_hours,
    logger,
) -> Optional[Dict[str, Any]]:
    """
    Parse Joint Summary when structure is: GWDs as columns, rows per ILI source.
    E.g. | Girth Weld No. | 3150 | 3160 | 3170 | 3180 | ...
         | 2022 Rosen | 01:36 | 07:42 | 11:50 | 11:30 | ...
         | 2025 TDW | 01:30 | 07:42 | 11:38 | 11:30 | ...
    Value at column GWD_i = D/S longseam at that GWD. For span [GWD_i, GWD_{i+1}], use value at GWD_i.
    """
    if joint_df.empty or len(joint_df.columns) < 2:
        return None

    # Get GWD numbers from column headers. Prefer D/S over U/S when both exist (e.g. "GWD 7000 D/S Longseam Ori.")
    gwd_col_indices = {}  # gwd -> (col_idx, is_ds)
    for col_idx, col_name in enumerate(joint_df.columns):
        # Handle multi-level headers (e.g. ("GWD 7000", "D/S Longseam Ori."))
        col_str = " ".join(str(c) for c in (col_name if isinstance(col_name, tuple) else [col_name]))
        cn = col_str.strip().lower()
        try:
            # Extract GWD from header (e.g. "GWD 7000", "7000", "GWD 7020 D/S Longseam Ori.")
            for part in col_str.replace(",", "").split():
                try:
                    gwd = int(float(part))
                    if 100 < gwd < 99999:
                        is_ds = "d/s" in cn or "downstream" in cn
                        if gwd not in gwd_col_indices or (is_ds and not gwd_col_indices.get(gwd, (None, False))[1]):
                            gwd_col_indices[gwd] = (col_idx, is_ds)
                        break
                except (ValueError, TypeError):
                    continue
        except (ValueError, TypeError):
            pass

    # If not in headers, try first data row
    if len(gwd_col_indices) < 2:
        for idx, row in joint_df.iterrows():
            for col_idx, val in enumerate(row):
                try:
                    gwd = int(float(str(val).replace(",", "")))
                    if 100 < gwd < 99999:
                        gwd_col_indices[gwd] = (col_idx, False)
                except (ValueError, TypeError):
                    pass
            if len(gwd_col_indices) >= 2:
                break

    # Flatten to col_idx only
    gwd_col_indices = {gwd: (c[0] if isinstance(c, tuple) else c) for gwd, c in gwd_col_indices.items()}

    if len(gwd_col_indices) < 2:
        logger.debug("[Joint Summary] Matrix: could not find GWD columns")
        return None

    # Find rows with longseam data (contain Rosen, TDW, or orientation values)
    by_source: Dict[str, Dict[int, float]] = {}
    parsed = []
    seen_sources = set()

    for idx, row in joint_df.iterrows():
        first_cell = str(row.iloc[0] or "").strip()
        first_lower = first_cell.lower()
        # Skip header/label rows
        if "girth weld" in first_lower or "joint" in first_lower and "no" in first_lower:
            continue
        # Look for ILI source rows (2022 Rosen, 2025 TDW) or "Long Seam" rows
        if not any(kw in first_lower for kw in ["rosen", "tdw", "long seam", "longseam", "seam"]):
            # Check if row has orientation-like values (hh:mm)
            has_orient = False
            for col_idx in gwd_col_indices.values():
                if col_idx < len(row):
                    v = str(row.iloc[col_idx] or "")
                    if ":" in v and any(c.isdigit() for c in v):
                        has_orient = True
                        break
            if not has_orient:
                continue

        source_name = first_cell
        for part in ["Long Seam Orientation (hh:mm)", "Long Seam", "Longseam", "Orientation", "hh:mm", "(", ")"]:
            source_name = source_name.replace(part, "").strip()
        if not source_name or source_name in seen_sources:
            source_name = source_name or f"Source_{idx}"
        seen_sources.add(source_name)

        gwd_to_hours = {}
        for gwd, col_idx in gwd_col_indices.items():
            if col_idx >= len(row):
                continue
            val = row.iloc[col_idx]
            hours = parse_orientation_to_hours(val) if val is not None else None
            if hours is not None:
                gwd_to_hours[gwd] = hours
                parsed.append({
                    "GWD": gwd,
                    "Source": source_name,
                    "Long Seam (D/S)": str(val) if val is not None else None,
                    "Longseam (hours)": round(hours, 2),
                })

        if gwd_to_hours:
            by_source[source_name] = gwd_to_hours
            logger.debug(f"[Joint Summary] Matrix: source '{source_name}' -> {len(gwd_to_hours)} GWDs")

    if not by_source:
        return None

    return {
        "by_source": by_source,
        "gwd_by_source": by_source,
        "parsed": parsed,
        "gwd_to_chainage": {},
        "gwd_order": sorted(gwd_col_indices.keys()),
    }


def _get_dig_package_distance_column(df: pd.DataFrame) -> Optional[str]:
    """Prefer 'Distance from TGW (m)' for dig packages, fallback to standard distance columns."""
    for kw in DIG_PACKAGE_DISTANCE_KEYWORDS:
        found = find_column_names(df, [kw])
        if found:
            return found
    return find_column_names(df, COLUMN_KEYWORDS["distance"])


def build_feature_map_from_dig_package(
    file_content: bytes,
) -> Tuple[List[Dict], Optional[Dict], List[str], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse dig package Excel and build feature map data for ILI Visual Tool.

    Returns:
        (features, scatter_data, sources, column_mapping, joint_summary_parsed, feature_summary_raw)
    """
    feature_df, joint_df, metadata = parse_dig_package_excel(file_content)

    if feature_df is None or feature_df.empty:
        raise ValueError(
            "Could not find 'Feature summary' section in the dig package. "
            "Ensure the Excel has a section header containing 'Feature summary'."
        )

    # Use dig-package-specific distance column (prefer Distance from TGW)
    ili_cols = identify_ili_columns(feature_df)
    dist_col = _get_dig_package_distance_column(feature_df)
    if not dist_col:
        dist_col = ili_cols.get("distance")
    if not dist_col:
        raise ValueError(
            "No distance/chainage column found. Dig packages typically have 'Distance from TGW (m)'."
        )
    ili_cols["distance"] = dist_col

    # Parse Joint Summary for longseam orientation
    # Supports two structures:
    # 1) Row-based: one row per GWD, columns for Long Seam Orientation
    # 2) Matrix: GWDs as columns, rows "Long Seam - 2022 Rosen", "Long Seam - 2025 TDW"
    # U/S seam = longseam at upstream GWD (left of target). D/S seam = longseam at this GWD.
    # For span [GWD_i, GWD_{i+1}]: use D/S of GWD_i = value at left boundary.
    # "2022 Rosen" applies to all Rosen (MFL-A, MFL-C, EMAT).
    joint_summary_parsed = []
    gwd_to_seam_by_source: Dict[str, Dict[int, float]] = {}  # source -> {gwd_number -> hours} (matrix)
    gwd_to_seam: Dict[float, float] = {}  # fallback: chainage -> hours (row-based)
    gwd_to_chainage: Dict[int, float] = {}
    use_gwd_lookup = False  # True when matrix structure (no chainage in Joint Summary)

    if joint_df is not None and not joint_df.empty:
        logger.info(f"[Joint Summary] Columns: {list(joint_df.columns)}, shape={joint_df.shape}")

        # Try matrix structure: GWDs as column headers, longseam rows per ILI source
        parsed_matrix = _parse_joint_summary_matrix(joint_df, parse_orientation_to_hours, logger)
        if parsed_matrix:
            gwd_to_seam_by_source = parsed_matrix.get("gwd_by_source", parsed_matrix.get("by_source", {}))
            joint_summary_parsed = parsed_matrix.get("parsed", [])
            gwd_to_chainage = parsed_matrix.get("gwd_to_chainage", {})
            use_gwd_lookup = True
            logger.info(f"[Joint Summary] Matrix parsed: sources={list(gwd_to_seam_by_source.keys())}, GWDs={list(next(iter(gwd_to_seam_by_source.values()), {}).keys())[:5] if gwd_to_seam_by_source else []}...")
        else:
            # Fallback: row-based structure
            dist_to_target_col = find_column_names(
                joint_df,
                ["Distance from TGW (m)", "Distance to Target", "Distance to target", "Distance from TGW"],
            )
            chainage_col = find_column_names(joint_df, ["Chainage", "ILI Chainage (m)", "Odometer"])
            orient_col = find_column_names(
                joint_df,
                [
                    "Long Seam Orientation for the Target",
                    "Longseam Orientation for the Target",
                    "Long Seam Orientation (hh:mm)",
                    "Longseam Orientation",
                    "Seam Orientation",
                    "Longseam Orient",
                    "Orientation (hh:mm)",
                    "Orientation (clock)",
                ],
            )
            gwd_col = find_column_names(joint_df, ["GWD", "Joint", "Joint Number", "Joint No", "Girth Weld No"])

            if orient_col:
                rows_data = []
                for _, row in joint_df.iterrows():
                    gwd_val = row.get(gwd_col) if gwd_col else None
                    ch = pd.to_numeric(row.get(chainage_col or dist_to_target_col), errors="coerce")
                    dist_to_target = pd.to_numeric(row.get(dist_to_target_col), errors="coerce") if dist_to_target_col else None
                    orient = row.get(orient_col)
                    hours = parse_orientation_to_hours(orient) if orient is not None else None
                    if pd.notna(ch):
                        rows_data.append({
                            "gwd": gwd_val,
                            "chainage": float(ch),
                            "distance_to_target": float(dist_to_target) if pd.notna(dist_to_target) else None,
                            "longseam_hours": hours,
                            "longseam_raw": str(orient) if orient is not None else None,
                        })
                        joint_summary_parsed.append({
                            "GWD": gwd_val,
                            "Chainage": float(ch),
                            "Distance to Target": dist_to_target,
                            "Long Seam Orientation": str(orient) if orient is not None else None,
                            "Longseam (hours)": round(hours, 2) if hours is not None else None,
                        })

                rows_data.sort(key=lambda r: r["chainage"])
                for i, r in enumerate(rows_data):
                    dist = r.get("distance_to_target")
                    if dist is not None and dist < 0 and i > 0:
                        effective_hours = rows_data[i - 1].get("longseam_hours")
                        used_from = "GWD-1 (left)"
                    else:
                        effective_hours = r.get("longseam_hours")
                        used_from = "this row"
                    if effective_hours is not None:
                        gwd_to_seam[r["chainage"]] = effective_hours
                        if r.get("gwd") is not None:
                            try:
                                gwd_num = int(float(r["gwd"]))
                                gwd_to_chainage[gwd_num] = r["chainage"]
                            except (TypeError, ValueError):
                                pass
                    for jp in joint_summary_parsed:
                        if jp.get("Chainage") == r["chainage"]:
                            jp["Effective Longseam (hours)"] = round(effective_hours, 2) if effective_hours is not None else None
                            jp["Used from"] = used_from
                            break
                logger.info(f"[Joint Summary] Row-based parsed: {len(gwd_to_seam)} chainage->seam entries")
            else:
                logger.warning("[Joint Summary] No orientation column found for row-based structure")

    features, scatter_data, sources = build_feature_map_from_df(feature_df, ili_cols)

    # Build per-span seam welds: when longseam passes a GWD (after joint length), use GWD+1's longseam.
    # For span [GWD_i, GWD_{i+1}]: use D/S longseam of GWD_i (value at left boundary).
    # Map feature source to Joint Summary source: Rosen MFL-A/MFL-C/EMAT -> "2022 Rosen", TDW -> "2025 TDW"
    def _match_joint_source(feature_source: str) -> Optional[str]:
        fs = (feature_source or "").lower()
        for js_source in list(gwd_to_seam_by_source.keys()) if gwd_to_seam_by_source else []:
            js_lower = js_source.lower()
            if "rosen" in js_lower and ("rosen" in fs or "mfl" in fs or "emat" in fs):
                return js_source
            if "tdw" in js_lower and "tdw" in fs:
                return js_source
        return next(iter(gwd_to_seam_by_source.keys()), None) if gwd_to_seam_by_source else None

    girth_sorted = sorted(
        scatter_data.get("girth_welds", []) if scatter_data else [],
        key=lambda gw: gw.get("chainage", 0) or 0,
    )

    target_gwd: Optional[int] = None
    target_longseam_hours: Optional[float] = None

    if girth_sorted and (gwd_to_seam_by_source or gwd_to_seam):
        seam_welds = []
        seen_span_source = set()
        for i in range(len(girth_sorted) - 1):
            ch_start = girth_sorted[i].get("chainage")
            ch_end = girth_sorted[i + 1].get("chainage")
            gwd_start = girth_sorted[i].get("gwd_number")
            feat_source = girth_sorted[i].get("source", "")

            if ch_start is None or ch_end is None:
                continue

            oh = None
            if gwd_to_seam_by_source and use_gwd_lookup:
                matched = _match_joint_source(feat_source)
                seam_map = gwd_to_seam_by_source.get(matched, {}) if matched else {}
                if not seam_map and gwd_to_seam_by_source:
                    seam_map = next(iter(gwd_to_seam_by_source.values()), {})
                try:
                    gwd_int = int(float(gwd_start)) if gwd_start is not None else None
                except (ValueError, TypeError):
                    gwd_int = None
                if gwd_int is not None and gwd_int in seam_map:
                    oh = seam_map[gwd_int]
                elif gwd_int is not None and seam_map:
                    nearest = min(seam_map.keys(), key=lambda k: abs(k - gwd_int), default=None)
                    if nearest is not None and abs(nearest - gwd_int) <= 15:
                        oh = seam_map[nearest]
            elif gwd_to_seam_by_source and not use_gwd_lookup:
                matched = _match_joint_source(feat_source)
                seam_map = gwd_to_seam_by_source.get(matched, {}) if matched else {}
                if not seam_map:
                    seam_map = next(iter(gwd_to_seam_by_source.values()), {})
                best = min(seam_map.keys(), key=lambda k: abs(k - ch_start), default=None) if seam_map else None
                if best is not None and abs(best - ch_start) < 2.0:
                    oh = seam_map[best]
            elif gwd_to_seam:
                best = min(gwd_to_seam.keys(), key=lambda k: abs(k - ch_start), default=None)
                if best is not None and abs(best - ch_start) < 2.0:
                    oh = gwd_to_seam[best]

            if oh is not None:
                js_src = _match_joint_source(feat_source) or feat_source
                span_key = (ch_start, ch_end, js_src)
                if span_key not in seen_span_source:
                    seen_span_source.add(span_key)
                    seam_welds.append({
                        "chainage_start": ch_start,
                        "chainage_end": ch_end,
                        "orientation_hours": oh,
                        "orientation_label": format_orientation_hours(oh),
                        "source": js_src,
                    })

        # Target GWD = girth weld at chainage 0 (Distance from TGW = 0)
        for gw in girth_sorted:
            ch = gw.get("chainage")
            if ch is not None and abs(ch) < 0.001:
                gwd_val = gw.get("gwd_number")
                if gwd_val is not None:
                    try:
                        target_gwd = int(float(gwd_val))
                        seam_map = next(iter(gwd_to_seam_by_source.values()), {}) if gwd_to_seam_by_source else {}
                        if target_gwd in seam_map:
                            target_longseam_hours = seam_map[target_gwd]
                        elif gwd_to_seam:
                            target_longseam_hours = next(iter(gwd_to_seam.values()), None)
                        break
                    except (ValueError, TypeError):
                        pass

        if seam_welds:
            scatter_data = scatter_data or {}
            scatter_data["seam_welds"] = seam_welds
            logger.info(f"[Joint Summary] Built {len(seam_welds)} per-span seam welds (longseam changes at each GWD)")

    # Fallback: when < 2 girth welds OR no per-span seam welds built, draw single blue line at target GWD longseam
    has_seam_welds = bool(scatter_data and scatter_data.get("seam_welds"))
    if not has_seam_welds and (gwd_to_seam_by_source or gwd_to_seam) and scatter_data:
        fallback_longseam = None
        fallback_gwd = target_gwd
        if gwd_to_seam_by_source:
            gwd_order = sorted(next(iter(gwd_to_seam_by_source.values()), {}).keys())
            fallback_gwd = gwd_order[len(gwd_order) // 2] if gwd_order else None
            if fallback_gwd is not None:
                fallback_longseam = next(iter(gwd_to_seam_by_source.values()), {}).get(fallback_gwd)
        if fallback_longseam is None and gwd_to_seam:
            fallback_longseam = next(iter(gwd_to_seam.values()), None)
        if fallback_longseam is not None:
            target_gwd = fallback_gwd
            target_longseam_hours = fallback_longseam
            scatter_data["seam_welds"] = [{
                "chainage_start": None,
                "chainage_end": None,
                "orientation_hours": fallback_longseam,
                "orientation_label": format_orientation_hours(fallback_longseam),
                "source": next(iter(gwd_to_seam_by_source.keys()), "") if gwd_to_seam_by_source else "",
            }]
            logger.info(f"[Joint Summary] Fallback: single blue line at {format_orientation_hours(fallback_longseam)} (target GWD {fallback_gwd})")

    # Ensure x_column reflects Distance from TGW when used
    if scatter_data and dist_col:
        scatter_data["x_column"] = dist_col

    column_mapping = {k: v for k, v in ili_cols.items() if v}

    # Build feature_summary_raw for data tracing (which Excel cells/columns produced each value)
    feature_summary_raw = None
    if feature_df is not None and not feature_df.empty:
        def _json_safe(val):
            if pd.isna(val):
                return None
            try:
                f = float(val)
                return int(f) if f == int(f) else f
            except (TypeError, ValueError):
                return str(val)

        sample = feature_df.head(50)
        sample_rows = [
            {k: _json_safe(v) for k, v in row.items()}
            for row in sample.to_dict(orient="records")
        ]
        feature_summary_raw = {
            "sheet": metadata.get("feature_sheet"),
            "header_row": metadata.get("feature_header_row"),
            "columns": list(feature_df.columns),
            "column_mapping_used": {k: v for k, v in ili_cols.items() if v},
            "sample_rows": sample_rows,
        }
        # Merge target GWD longseam into Feature Summary (single blue line, no separate Joint Summary)
        if target_gwd is not None:
            feature_summary_raw["target_gwd"] = target_gwd
        if target_longseam_hours is not None:
            feature_summary_raw["target_longseam_hours"] = target_longseam_hours
            feature_summary_raw["target_longseam_label"] = format_orientation_hours(target_longseam_hours)

    return features, scatter_data, sources, column_mapping, [], feature_summary_raw


