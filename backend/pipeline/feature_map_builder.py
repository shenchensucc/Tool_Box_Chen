"""
Shared feature map builder for ILI Visual Tool.

Used by:
- main.py: process-feature-map, parse-paste
- dig_package_reader.py: reading dig package Excel format

Builds features, scatter_data, girth_welds, seam_welds from ILI DataFrames.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from backend.logging_config import get_logger

logger = get_logger("backend.pipeline.feature_map_builder")


def parse_orientation_to_degrees(val) -> Optional[float]:
    """Parse orientation (clock '2:48' or degrees) to degrees from 12 o'clock."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            h = float(parts[0])
            m = float(parts[1]) if len(parts) > 1 else 0
            clock_pos = h + m / 60.0
            return (clock_pos / 12.0) * 360.0
        except (ValueError, IndexError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_orientation_to_hours(val) -> Optional[float]:
    """Parse orientation (clock '2:48' or '08:22') to hours 0-12 for Y-axis."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            h = float(parts[0])
            m = float(parts[1]) if len(parts) > 1 else 0
            return h + m / 60.0
        except (ValueError, IndexError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def format_orientation_hours(hours: float) -> str:
    """Format hours (e.g. 8.37) as hh:mm for display."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h:02d}:{m:02d}"


def build_feature_map_from_df(
    df: pd.DataFrame,
    ili_cols: Dict[str, Optional[str]],
) -> tuple:
    """
    Build features, scatter_data, and sources from a DataFrame with identified ILI columns.
    Returns (features, scatter_data, sources).
    """
    dist_col = ili_cols.get("distance")
    depth_col = ili_cols.get("depth") or ili_cols.get("metal_loss")
    length_col = ili_cols.get("length")
    width_col = ili_cols.get("width")
    fid_col = ili_cols.get("feature_id")
    ftype_col = ili_cols.get("feature_type")
    fdesc_col = ili_cols.get("feature_desc")
    orient_col = ili_cols.get("orientation")
    joint_col = ili_cols.get("joint_number")
    source_col = ili_cols.get("source")
    gwd_col = next(
        (c for c in df.columns if "gwd" in str(c).lower() or ("u/s" in str(c).lower() and "ili" in str(c).lower() and "number" in str(c).lower())),
        joint_col,
    )
    seam_orient_col = next((c for c in df.columns if "seam" in str(c).lower() and "orientation" in str(c).lower()), None)

    for col in [c for c in [dist_col, depth_col, length_col, width_col] if c and c in df.columns]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    features = []
    for idx, row in df.iterrows():
        try:
            x_val = pd.to_numeric(row.get(dist_col), errors="coerce")
            if pd.isna(x_val):
                continue
        except (TypeError, ValueError):
            continue

        depth_val = 0.0
        if depth_col and depth_col in df.columns:
            try:
                dv = float(pd.to_numeric(row.get(depth_col), errors="coerce"))
                if dv is not None and not (isinstance(dv, float) and pd.isna(dv)):
                    depth_val = dv
            except (TypeError, ValueError):
                pass

        length_val = 0.0
        if length_col and length_col in df.columns:
            try:
                ln = float(pd.to_numeric(row.get(length_col), errors="coerce"))
                if ln and not (isinstance(ln, float) and pd.isna(ln)):
                    length_val = ln
            except (TypeError, ValueError):
                pass

        width_val = 0.0
        if width_col and width_col in df.columns:
            try:
                wd = float(pd.to_numeric(row.get(width_col), errors="coerce"))
                if wd and not (isinstance(wd, float) and pd.isna(wd)):
                    width_val = wd
            except (TypeError, ValueError):
                pass

        orient_val = row.get(orient_col) if orient_col and orient_col in df.columns else None
        orientation_deg = parse_orientation_to_degrees(orient_val)
        orientation_hours = parse_orientation_to_hours(orient_val)

        feature_type = str(row.get(ftype_col, "")).strip() if ftype_col and ftype_col in df.columns else ""
        gwd_number = None
        if (gwd_col and gwd_col in df.columns) or (joint_col and joint_col in df.columns):
            val = row.get(gwd_col or joint_col)
            if pd.notna(val):
                try:
                    gwd_number = int(float(val))
                except (ValueError, TypeError):
                    gwd_number = str(val).strip()
        seam_orient_val = row.get(seam_orient_col) if seam_orient_col and seam_orient_col in df.columns else None
        seam_orient_hours = parse_orientation_to_hours(seam_orient_val)

        source_val = str(row.get(source_col, "")).strip() if source_col and source_col in df.columns and pd.notna(row.get(source_col)) else ""

        parts = []
        if fid_col and fid_col in df.columns:
            parts.append(f"<b>Feature ID:</b> {row.get(fid_col, '')}")
        if ftype_col and ftype_col in df.columns:
            parts.append(f"<b>Type:</b> {row.get(ftype_col, '')}")
        if fdesc_col and fdesc_col in df.columns:
            parts.append(f"<b>Description:</b> {row.get(fdesc_col, '')}")
        if depth_col and depth_col in df.columns:
            parts.append(f"<b>Depth:</b> {row.get(depth_col, '')}")
        if length_col and length_col in df.columns:
            parts.append(f"<b>Length (mm):</b> {row.get(length_col, '')}")
        if width_col and width_col in df.columns:
            parts.append(f"<b>Width (mm):</b> {row.get(width_col, '')}")
        if orient_col and orient_col in df.columns:
            parts.append(f"<b>Orientation:</b> {row.get(orient_col, '')}")
        if source_val:
            parts.append(f"<b>Source:</b> {source_val}")
        parts.append(f"<b>Chainage (m):</b> {x_val}")
        hover_text = "<br>".join(parts)

        feat = {
            "x": float(x_val),
            "y": float(depth_val),
            "depth": float(depth_val),
            "length": float(length_val),
            "width": float(width_val),
            "orientation_deg": orientation_deg,
            "orientation_hours": float(orientation_hours) if orientation_hours is not None else 6.0,
            "feature_type": feature_type,
            "gwd_number": gwd_number,
            "seam_orient_hours": float(seam_orient_hours) if seam_orient_hours is not None else None,
            "hover_text": hover_text,
            "feature_id": str(row.get(fid_col, idx)) if fid_col and fid_col in df.columns else str(idx),
            "source": source_val,
        }
        features.append(feat)

    scatter_data = None
    girth_welds = []
    seam_welds = []
    if features and dist_col:
        x_vals = [f["x"] for f in features]
        orient_vals = [f.get("orientation_hours", 6.0) for f in features]
        scatter_data = {
            "x_column": dist_col,
            "x_values": x_vals,
            "y_data": {"depth": [f["y"] for f in features], "metal_loss": [f["y"] for f in features]},
            "orientation_hours": orient_vals,
        }
        gwd_sorted = sorted(
            [f for f in features if "girth" in (f.get("feature_type") or "").lower() or "gwd" in (f.get("feature_type") or "").lower()],
            key=lambda x: x["x"],
        )
        for f in gwd_sorted:
            lbl = f"GWD {f['gwd_number']}" if f.get("gwd_number") is not None else ""
            girth_welds.append({"chainage": f["x"], "gwd_number": f.get("gwd_number"), "label": lbl, "source": f.get("source", "")})
        idx_next = {gwd_sorted[i]["x"]: gwd_sorted[i + 1]["x"] for i in range(len(gwd_sorted) - 1)}
        for f in gwd_sorted:
            if f.get("seam_orient_hours") is not None:
                end = idx_next.get(f["x"])
                seam_welds.append({
                    "chainage_start": f["x"],
                    "chainage_end": end,
                    "orientation_hours": f["seam_orient_hours"],
                    "orientation_label": format_orientation_hours(f["seam_orient_hours"]),
                    "source": f.get("source", ""),
                })
        for f in features:
            ft = (f.get("feature_type") or "").lower()
            if "seam" in ft and "girth" not in ft and "gwd" not in ft:
                seam_welds.append({
                    "chainage_start": None,
                    "chainage_end": None,
                    "orientation_hours": f.get("orientation_hours", 6.0),
                    "orientation_label": format_orientation_hours(f.get("orientation_hours", 6.0)),
                    "source": f.get("source", ""),
                })
        if scatter_data:
            scatter_data["girth_welds"] = girth_welds
            scatter_data["seam_welds"] = seam_welds

    sources = sorted({str(f.get("source", "")).strip() for f in features if f.get("source")})
    return features, scatter_data, sources
