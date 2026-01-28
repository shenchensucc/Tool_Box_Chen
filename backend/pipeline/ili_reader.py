import pandas as pd
from typing import List, Optional, Dict

# Configurable keywords for column identification
# Users can manually update these lists to support different ILI vendors
COLUMN_KEYWORDS = {
    "depth": [
        "depth", "defect depth", "Max. Depth", "dimp", "depth (%)", "depth (mm)",
        "Peak Depth", "Peak Depth (% WT)", "Feature Depth", "Max Depth",
        "Max. Depth (%)", "Depth (%)"
    ],
    "length": [
        "length", "Length", "defect length", "Limp", "length (mm)",
        "Feature Length", "Length (in)", "Length (in.)"
    ],
    "width": [
        "width", "Width", "defect width", "Wimp", "width (mm)",
        "Feature Width", "Width (in)", "Width (in.)"
    ],
    "distance": [
        "distance", "Distance", "Odometer", "Log Distance", "Chainage",
        "Wheel Count (ft)", "Wheel Count (ft.)", "Log Dist.", "ILI Chainage (m)",
        "Odometer (m)", "ILI Chainage/Odometer (m)", "ILI Chainage", "ILI Distance (m)"
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
        "Feature Orientation (Center of feature) (hh:mm)", "(Degree)", "o'clock"
    ],
    "joint_number": [
        "Joint", "Joint Number", "Weld Number", "Joint No. or US GW No.",
        "Joint No", "US GW No", "PNG Joint Number", "Client Jno."
    ]
}

def find_column_names(df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
    """
    Find a column name in the DataFrame that matches one of the possible names (case-insensitive).
    """
    df_columns = [str(col).lower().strip() for col in df.columns]
    for name in possible_names:
        name_lower = name.lower().strip()
        if name_lower in df_columns:
            # Find the original case name
            idx = df_columns.index(name_lower)
            return df.columns[idx]
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
    return results

def read_ili_data(file_path_or_buffer, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """
    Read an ILI dataset from an Excel file.
    """
    df = pd.read_excel(file_path_or_buffer, sheet_name=sheet_name)
    
    # If the result is a dictionary (multiple sheets), take the first sheet
    if isinstance(df, dict):
        if not df:
            return pd.DataFrame()
        first_sheet = list(df.keys())[0]
        return df[first_sheet]
    
    return df
