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
    m = int(round((hours - h) * 60))
    if m >= 60:
        h += 1
        m -= 60
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


# ─────────────────────────────────────────────────────────────────────────────
# Pipe-Tally builder
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_map_from_pipe_tally_df(
    df: pd.DataFrame,
    ili_cols: Dict[str, Optional[str]],
) -> tuple:
    """
    Build features, scatter_data, and sources from a **Pipe Tally** DataFrame.

    Pipe Tally rows represent individual pipe joints, not anomalies.

    Mapping:
    - ``distance`` (US chainage)   → girth-weld position + joint left edge
    - ``ds_distance`` (DS chainage) → joint right edge / next girth weld
    - ``length``                   → joint length in metres (fallback when DS absent)
    - ``orientation`` / seam col   → longseam orientation per joint (seam_welds)
    - ``wall_thickness``           → metadata (stored in hover; not used for depth colour)
    - ``pipe_grade``               → metadata (stored in hover)
    - ``joint_number``             → GWD number at the US end

    The 2D view shows:
    - Red vertical lines  = girth welds (US chainage of each joint, plus the final DS)
    - Coloured horizontal lines = longseam per joint span (seam_welds)
    - Thin feature boxes centred at mid-joint at the seam orientation (hoverable)

    Returns (features, scatter_data, sources) — same contract as :func:`build_feature_map_from_df`.
    """
    us_col  = ili_cols.get("distance")       # US-end chainage
    ds_col  = ili_cols.get("ds_distance")    # DS-end chainage
    len_col = ili_cols.get("length")         # joint length (fallback)
    wt_col  = ili_cols.get("wall_thickness")
    gr_col  = ili_cols.get("pipe_grade")
    jt_col  = ili_cols.get("joint_number")
    src_col = ili_cols.get("source")
    fid_col = ili_cols.get("feature_id")

    # Seam orientation: prefer a column whose name contains both "seam"/"longseam"
    # and "orient"/"position", then fall back to the generic orientation column.
    orient_col = ili_cols.get("orientation")
    seam_orient_col: Optional[str] = next(
        (
            c for c in df.columns
            if ("seam" in str(c).lower() or "longseam" in str(c).lower() or " ls " in f" {str(c).lower()} ")
            and ("orient" in str(c).lower() or "position" in str(c).lower() or "o'clock" in str(c).lower())
        ),
        orient_col,
    )

    for col in [c for c in [us_col, ds_col, wt_col, len_col] if c and c in df.columns]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    features: list = []
    # Collect (chainage, gwd_number, source) for girth-weld list
    girth_entries: list[tuple] = []

    for idx, row in df.iterrows():
        # US chainage — mandatory; skip rows without it
        us_val = pd.to_numeric(row.get(us_col), errors="coerce") if us_col else None
        if us_val is None or (isinstance(us_val, float) and pd.isna(us_val)):
            continue
        us_val = float(us_val)

        # DS chainage
        ds_val: Optional[float] = None
        if ds_col and ds_col in df.columns:
            dv = pd.to_numeric(row.get(ds_col), errors="coerce")
            if not (isinstance(dv, float) and pd.isna(dv)):
                ds_val = float(dv)

        # Joint length in metres
        jt_length_m: Optional[float] = None
        if ds_val is not None:
            jt_length_m = abs(ds_val - us_val)
        elif len_col and len_col in df.columns:
            lv = pd.to_numeric(row.get(len_col), errors="coerce")
            if not (isinstance(lv, float) and pd.isna(lv)):
                # len_col keywords include "Joint Length (m)" → assume metres
                jt_length_m = float(lv)

        jt_length_mm = (jt_length_m * 1000.0) if jt_length_m else 0.001

        # Centre chainage (x position for the feature box)
        if ds_val is not None:
            center_x = (us_val + ds_val) / 2.0
        elif jt_length_m:
            center_x = us_val + jt_length_m / 2.0
        else:
            center_x = us_val

        # Wall thickness
        wt_val = 0.0
        if wt_col and wt_col in df.columns:
            wv = pd.to_numeric(row.get(wt_col), errors="coerce")
            if not (isinstance(wv, float) and pd.isna(wv)):
                wt_val = float(wv)

        # Grade
        gr_val = str(row.get(gr_col, "")).strip() if gr_col and gr_col in df.columns and pd.notna(row.get(gr_col)) else ""

        # Seam orientation
        seam_raw = row.get(seam_orient_col) if seam_orient_col and seam_orient_col in df.columns else None
        seam_hours = parse_orientation_to_hours(seam_raw)

        # GWD number
        gwd_number: Optional[Any] = None
        if jt_col and jt_col in df.columns:
            jv = row.get(jt_col)
            if pd.notna(jv):
                try:
                    gwd_number = int(float(jv))
                except (ValueError, TypeError):
                    gwd_number = str(jv).strip()

        # Source
        src_val = (
            str(row.get(src_col, "")).strip()
            if src_col and src_col in df.columns and pd.notna(row.get(src_col))
            else ""
        )

        # Hover text
        parts = []
        if gwd_number is not None:
            parts.append(f"<b>GWD:</b> {gwd_number}")
        parts.append(f"<b>US Chainage (m):</b> {us_val:.3f}")
        if ds_val is not None:
            parts.append(f"<b>DS Chainage (m):</b> {ds_val:.3f}")
        if jt_length_m is not None:
            parts.append(f"<b>Joint Length (m):</b> {jt_length_m:.3f}")
        if wt_val:
            parts.append(f"<b>Wall Thickness (mm):</b> {wt_val}")
        if gr_val:
            parts.append(f"<b>Grade:</b> {gr_val}")
        if seam_raw is not None:
            parts.append(f"<b>Seam Orientation:</b> {seam_raw}")
        if src_val:
            parts.append(f"<b>Source:</b> {src_val}")

        feat: Dict[str, Any] = {
            "x": center_x,
            "y": 0.0,
            "depth": 0.0,       # no anomaly depth for pipe joints
            "length": jt_length_mm,
            "width": 0.001,     # thin tick; seam line carries the orientation info
            "orientation_deg": None,
            "orientation_hours": seam_hours if seam_hours is not None else 6.0,
            "feature_type": "Pipe Joint",
            "gwd_number": gwd_number,
            "seam_orient_hours": seam_hours,
            "hover_text": "<br>".join(parts),
            "feature_id": str(row.get(fid_col, idx)) if fid_col and fid_col in df.columns else str(idx),
            "source": src_val,
            "wall_thickness": wt_val,
            "pipe_grade": gr_val,
            "_us_chainage": us_val,
            "_ds_chainage": ds_val,
        }
        features.append(feat)
        girth_entries.append((us_val, gwd_number, src_val))

    if not features:
        return [], None, []

    # ── Girth welds: one per unique US chainage (+ last DS) ───────────────
    seen_ch: set = set()
    girth_welds: List[Dict] = []
    for ch, gn, src in sorted(girth_entries, key=lambda t: t[0]):
        key = round(ch, 3)
        if key in seen_ch:
            continue
        seen_ch.add(key)
        lbl = f"GWD {gn}" if gn is not None else f"{ch:.3f} m"
        girth_welds.append({"chainage": ch, "gwd_number": gn, "label": lbl, "source": src})

    # Add the DS end of the last joint so the rightmost boundary appears
    last = features[-1]
    if last.get("_ds_chainage") is not None:
        last_ds = last["_ds_chainage"]
        key = round(last_ds, 3)
        if key not in seen_ch:
            girth_welds.append({"chainage": last_ds, "gwd_number": None, "label": "DS end", "source": ""})

    # ── Seam welds: per-joint longseam spans ──────────────────────────────
    seam_welds: List[Dict] = []
    for f in features:
        us = f.get("_us_chainage")
        ds = f.get("_ds_chainage")
        oh = f.get("seam_orient_hours")
        if us is None or oh is None:
            continue
        end = ds if ds is not None else us + f["length"] / 1000.0
        seam_welds.append({
            "chainage_start": us,
            "chainage_end": end,
            "orientation_hours": oh,
            "orientation_label": format_orientation_hours(oh),
            "source": f.get("source", ""),
            "gwd_number": f.get("gwd_number"),
        })

    x_vals = [f["x"] for f in features]
    scatter_data: Dict[str, Any] = {
        "x_column": us_col or "US Chainage (m)",
        "x_values": x_vals,
        "y_data": {
            "depth": [0.0] * len(features),
            "metal_loss": [0.0] * len(features),
        },
        "orientation_hours": [f.get("orientation_hours", 6.0) for f in features],
        "girth_welds": girth_welds,
        "seam_welds": seam_welds,
    }

    sources = sorted({str(f.get("source", "")).strip() for f in features if f.get("source")})
    return features, scatter_data, sources


# ─────────────────────────────────────────────────────────────────────────────
# Extensible format registry + dispatcher
# ─────────────────────────────────────────────────────────────────────────────

#: Mapping of data-format name → builder callable.
#: Add new entries here to support additional data types without touching any
#: other code — the API dispatcher calls ``build_feature_map_auto`` which looks
#: up the right builder from this dict.
DATA_FORMAT_BUILDERS: Dict[str, Any] = {
    "anomaly":    build_feature_map_from_df,
    "pipe_tally": build_feature_map_from_pipe_tally_df,
    # Future examples:
    # "cathodic_protection": build_feature_map_from_cp_df,
    # "depth_of_cover":      build_feature_map_from_doc_df,
}

#: Human-readable labels for each data format (used by frontend selectbox).
DATA_FORMAT_LABELS: Dict[str, str] = {
    "anomaly":    "ILI Anomaly / Feature Data",
    "pipe_tally": "Pipe Tally (Joint Inventory)",
}


def build_feature_map_auto(
    df: pd.DataFrame,
    ili_cols: Dict[str, Optional[str]],
    data_format: str = "anomaly",
) -> tuple:
    """
    Dispatch to the correct feature-map builder for the detected data format.

    ``data_format`` should be one of :data:`DATA_FORMAT_BUILDERS`; unknown
    values fall back to the anomaly builder so callers never crash on new keys.
    """
    builder = DATA_FORMAT_BUILDERS.get(data_format, build_feature_map_from_df)
    return builder(df, ili_cols)
