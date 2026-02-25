"""
Excel Reader Module for TML Data Processing

Reusable Excel reading with flexible column name mapping.
Supports column header variations (e.g., "Sort Field" vs "sort field", "Circuit ID" vs "Circuit #").

This module can be used by both TML Data Loader and De-active CML tools.
"""

import os
from typing import Dict, List, Optional, Tuple

import pandas as pd


# Column alias mapping: canonical_name -> list of acceptable variants (case-insensitive)
# Add more aliases as needed - structure is ready for user customization
COLUMN_ALIASES: Dict[str, List[str]] = {
    "Equipment ID": ["Equipment ID", "Equipment #", "Equip ID", "EquipmentID"],
    "Circuit ID": ["Circuit ID", "Circuit", "Circuit #", "CircuitID", "Circuit Number"],
    "CML Group ID": ["CML Group ID", "CML Group", "TML Group ID", "CMLGroupID"],
    "sub-CML ID": ["sub-CML ID", "Sub CML ID", "TML_ID", "TML ID", "SubCMLID", "CML ID", "CML_ID", "CMLID"],
    "AER_Status_CML": ["AER_Status_CML", "AER Status CML", "AERStatusCML"],
    "Sort Field": ["Sort Field", "sort field", "SortField"],
    "Circuit ID": ["Circuit ID", "Circuit #", "CircuitID", "Circuit Number"],
}


def _normalize_for_match(s: str) -> str:
    """Normalize string for case-insensitive matching (strip, lower)."""
    return str(s).strip().lower() if pd.notna(s) else ""


def _find_canonical_column(df_columns: List[str], canonical_name: str) -> Optional[str]:
    """
    Find the actual column name in DataFrame that matches the canonical name or its aliases.
    
    Args:
        df_columns: List of column names in the DataFrame
        canonical_name: The canonical column name to look for
        
    Returns:
        The actual column name from df_columns if found, None otherwise
    """
    aliases = COLUMN_ALIASES.get(canonical_name, [canonical_name])
    df_cols_normalized = {_normalize_for_match(c): c for c in df_columns}
    
    for alias in aliases:
        normalized = _normalize_for_match(alias)
        if normalized in df_cols_normalized:
            return df_cols_normalized[normalized]
    
    # Also try exact canonical name
    normalized_canonical = _normalize_for_match(canonical_name)
    if normalized_canonical in df_cols_normalized:
        return df_cols_normalized[normalized_canonical]
    
    return None


def build_column_mapping(df_columns: List[str], required_canonical: List[str]) -> Dict[str, str]:
    """
    Build a mapping from actual column names to canonical names.
    
    Args:
        df_columns: List of column names in the source DataFrame
        required_canonical: List of canonical column names needed
        
    Returns:
        Dict mapping actual_column_name -> canonical_name
        Empty dict entries are omitted (column not found)
    """
    mapping = {}
    for canonical in required_canonical:
        actual = _find_canonical_column(df_columns, canonical)
        if actual:
            mapping[actual] = canonical
    return mapping


def read_excel_with_flexible_columns(
    file_path: str,
    sheet_name: str,
    required_columns: List[str],
    dtype: Optional[Dict[str, type]] = None,
) -> pd.DataFrame:
    """
    Read Excel file and normalize column names using alias mapping.
    
    Args:
        file_path: Path to the Excel file
        sheet_name: Name of the sheet to read
        required_columns: List of canonical column names required (e.g., ["Equipment ID", "CML Group ID", "sub-CML ID"])
        dtype: Optional dict for column dtypes (e.g., {"Equipment ID": str})
        
    Returns:
        DataFrame with normalized (canonical) column names
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If required columns cannot be mapped
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Read raw Excel
    read_dtype = dtype or {}
    df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=read_dtype)
    
    # Build column mapping
    mapping = build_column_mapping(df.columns.tolist(), required_columns)
    
    # Check for missing required columns
    found_canonical = set(mapping.values())
    missing = [c for c in required_columns if c not in found_canonical]
    if missing:
        raise ValueError(
            f"Could not find required columns: {missing}. "
            f"Available columns: {df.columns.tolist()}. "
            f"Add aliases in COLUMN_ALIASES if your headers use different names."
        )
    
    # Rename columns to canonical names (keep only required columns)
    df = df.rename(columns=mapping)
    df = df[[c for c in required_columns if c in df.columns]]
    
    return df


def read_excel_simple(
    file_path: str,
    sheet_name: str,
    dtype: Optional[Dict[str, type]] = None,
) -> pd.DataFrame:
    """
    Simple Excel read without column mapping (for backward compatibility).
    Use when exact column names are known.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    return pd.read_excel(file_path, sheet_name=sheet_name, dtype=dtype or {})


def read_excel_auto_sheet(
    file_path: str,
    required_columns: List[str],
    preferred_sheet: str = "Source_Data",
    dtype: Optional[Dict[str, type]] = None,
) -> Tuple[pd.DataFrame, str]:
    """
    Read Excel and auto-detect which sheet has the required columns.
    Tries preferred_sheet first, then iterates through all sheets.

    Returns:
        Tuple of (DataFrame, sheet_name_used)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    xl = pd.ExcelFile(file_path)
    sheet_names = xl.sheet_names
    if not sheet_names:
        raise ValueError(f"No sheets found in file: {file_path}")

    # Try preferred sheet first
    sheets_to_try = [preferred_sheet] if preferred_sheet in sheet_names else []
    sheets_to_try += [s for s in sheet_names if s not in sheets_to_try]

    last_error = None
    for sheet_name in sheets_to_try:
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=dtype or {})
            if df.empty:
                continue
            mapping = build_column_mapping(df.columns.tolist(), required_columns)
            found = set(mapping.values())
            missing = [c for c in required_columns if c not in found]
            if not missing:
                df = df.rename(columns=mapping)
                df = df[[c for c in required_columns if c in df.columns]]
                return (df, sheet_name)
            last_error = ValueError(
                f"Sheet '{sheet_name}': missing columns {missing}. "
                f"Available: {df.columns.tolist()}"
            )
        except Exception as e:
            last_error = e
            continue

    if last_error:
        raise ValueError(
            f"Could not find a sheet with required columns {required_columns}. "
            f"Tried sheets: {sheets_to_try}. "
            f"Last error: {last_error}"
        )
    raise ValueError(f"No sheet with required columns. Available sheets: {sheet_names}")
