import pandas as pd
from typing import List, Optional, Dict

from backend.logging_config import get_logger

logger = get_logger("backend.pipeline.ili_reader")

# Version string - change when fixing column matching; appears in logs on reload
ILI_READER_VERSION = "v2-depth-fix"
logger.info(f"ili_reader loaded ({ILI_READER_VERSION})")

# Configurable keywords for column identification
# Users can manually update these lists to support different ILI vendors
COLUMN_KEYWORDS = {
    "depth": [
        "depth", "defect depth", "Max. Depth", "dimp", "depth (%)", "depth (mm)",
        "Peak Depth", "Peak Depth (% WT)", "Feature Depth", "Max Depth",
        "Max. Depth (%)", "Depth (%)", "As-Reported Anomaly Depth (%WT)",
        "Feature Depth (%WT for Corrosion & Cracks, %OD for Dents)"
    ],
    "length": [
        "length", "Length", "defect length", "Limp", "length (mm)",
        "Feature Length", "Feature Length (mm)", "Length (in)", "Length (in.)"
    ],
    "width": [
        "width", "Width", "defect width", "Wimp", "width (mm)",
        "Feature Width", "Feature Width (mm)", "Width (in)", "Width (in.)"
    ],
    "distance": [
        "distance", "Distance", "Odometer", "Log Distance", "Chainage",
        "Wheel Count (ft)", "Wheel Count (ft.)", "Log Dist.", "ILI Chainage (m)",
        "Odometer (m)", "ILI Chainage/Odometer (m)", "ILI Chainage", "ILI Distance (m)",
        "Distance from TGW (m)", "Distance from TGW"
    ],
    "feature_id": [
        "feature id", "feature", "id", "f_id", "Feature Number", "Anomaly ID",
        "ID", "FeatureID", "Target ID", "ID#", "Feature Identifier", "ILI Feature ID"
    ],
    "feature_type": ["Feature Type", "Feature", "Event", "Anomaly Type", "Type"],
    "feature_desc": ["Feature Description", "Description", "Anomaly Description", "Anomaly", "Event"],
    "orientation": [
        "Orientation", "Clock Orientation", "O'Clock", "Orientation (clock)",
        "Clock Orient.", "Orientation (hh:mm)", "Feature Orientation",
        "Feature Orientation (Center of feature) (hh:mm)", "Feature Orientation (deg. or clock)",
        "(Degree)", "o'clock"
    ],
    "joint_number": [
        "Joint", "Joint Number", "Weld Number", "Joint No. or US GW No.",
        "Joint No", "US GW No", "PNG Joint Number", "Client Jno."
    ]
}

def find_column_names(df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
    """
    Find a column name in the DataFrame that matches one of the possible names (case-insensitive).
    Tries exact match first, then substring match (longest keywords first) for robustness.
    """
    df_columns_lower = [str(col).lower().strip() for col in df.columns]
    # Try longest keywords first so "As-Reported Anomaly Depth (%WT)" matches before "depth"
    sorted_names = sorted(possible_names, key=lambda n: len(n), reverse=True)
    for name in sorted_names:
        name_lower = name.lower().strip()
        if name_lower in df_columns_lower:
            idx = df_columns_lower.index(name_lower)
            return df.columns[idx]
    # Fallback: substring match (column contains keyword) for vendor-specific names
    for name in sorted_names:
        name_lower = name.lower().strip()
        if len(name_lower) < 4:
            continue  # Skip very short keywords to avoid false matches
        for i, col_lower in enumerate(df_columns_lower):
            if name_lower in col_lower:
                return df.columns[i]
    return None

def identify_ili_columns(df: pd.DataFrame, custom_keywords: Optional[Dict[str, List[str]]] = None) -> Dict[str, Optional[str]]:
    """
    Automatically identify ILI columns based on keywords.
    
    Returns a dictionary mapping standardized keys (depth, length, etc.) 
    to the actual column names found in the DataFrame.
    """
    keywords = custom_keywords or COLUMN_KEYWORDS
    results = {}
    for key, possible_names in keywords.items():
        results[key] = find_column_names(df, possible_names)
    found = {k: v for k, v in results.items() if v is not None}
    logger.debug(f"identify_ili_columns: Found {len(found)} columns: {found}")
    return results

def parse_pasted_ili_text(text: str) -> pd.DataFrame:
    """
    Parse pasted tabular text (e.g. from Excel copy) into a DataFrame.
    Tries tab separator first (Excel default), then comma.
    """
    import io
    text = text.strip()
    if not text:
        logger.warning("parse_pasted_ili_text: empty input")
        return pd.DataFrame()

    for sep, name in [("\t", "tab"), (",", "comma")]:
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str)
            if df.shape[1] > 1:
                logger.info(f"parse_pasted_ili_text: parsed {df.shape} with {name} separator")
                return df
        except Exception as e:
            logger.debug(f"parse_pasted_ili_text: {name} sep failed: {e}")
            continue
    logger.warning("parse_pasted_ili_text: could not parse input")
    return pd.DataFrame()


def read_ili_data(file_path_or_buffer, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    Read an ILI dataset from an Excel file.
    """
    logger.debug(f"read_ili_data: sheet_name={sheet_name}, input_type={type(file_path_or_buffer).__name__}")
    try:
        df = pd.read_excel(file_path_or_buffer, sheet_name=sheet_name)
    except Exception as e:
        logger.error(f"read_ili_data failed: {type(e).__name__}: {e}")
        raise

    # If the result is a dictionary (multiple sheets), take the first sheet
    if isinstance(df, dict):
        if not df:
            logger.warning("read_ili_data: Excel returned empty dict of sheets")
            return pd.DataFrame()
        first_sheet = list(df.keys())[0]
        df = df[first_sheet]
        logger.debug(f"read_ili_data: Using first sheet '{first_sheet}', shape={df.shape}")

    logger.info(f"read_ili_data: Loaded shape={df.shape}, columns={list(df.columns)[:10]}...")
    return df
