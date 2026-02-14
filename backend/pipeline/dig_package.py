"""
Dig Package Generation Module

This module handles the generation of dig package Excel and PDF files from:
- MDL (Master Dig List)
- ILI (In-Line Inspection) data
- Template Excel file

It matches features, populates templates, and generates individual dig packages.
"""

import io
import os
import json
import base64
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from backend.pipeline.ili_reader import find_column_names, identify_ili_columns, COLUMN_KEYWORDS as GLOBAL_KEYWORDS
from backend.logging_config import get_logger

logger = get_logger("backend.pipeline.dig_package")


# ============================================================================
# Keyword Definitions for Column Matching
# ============================================================================

# Vendor-specific mappings can still be used for specialized matching if needed,
# but we'll prefer the global COLUMN_KEYWORDS from ili_reader.py for general tasks.
VENDOR_MAPPINGS = {
    "TDW": {
        "Feature ID": ["ID", "Feature Number", "FeatureID", "Target ID"],
        "Feature Type": ["Type", "Feature Type", "Anomaly Type"],
        "Feature Description": ["Description", "Feature Description", "Anomaly Description"],
        "Feature Length": ["Length", "Length (in)", "Length (mm)"],
        "Feature Width": ["Width", "Width (in)", "Width (mm)"],
        "Feature Depth": ["Depth", "Depth (%)", "Max Depth"],
        "Feature Orientation": ["Orientation", "Clock Orientation", "O'Clock"],
        "ILI Chainage": ["Chainage", "Odometer", "Distance"],
        "Joint Number": ["Joint", "Joint Number", "Weld Number"],
    },
    "Rosen-MFLA": {
        "Feature ID": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
        "Feature Type": ["Feature Type", "Feature", "Event"],
        "Feature Description": ["Feature Description", "Description", "Anomaly"],
        "Feature Length": ["Length (mm)", "Length (in)", "Length"],
        "Feature Width": ["Width (mm)", "Width (in)", "Width"],
        "Feature Depth": ["Depth (%)", "Max Depth", "Peak Depth"],
        "Feature Orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
        "ILI Chainage": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
        "Joint Number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
    },
    "Rosen-MFLC": {
        "Feature ID": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
        "Feature Type": ["Feature Type", "Feature", "Event"],
        "Feature Description": ["Feature Description", "Description", "Anomaly"],
        "Feature Length": ["Length (mm)", "Length (in)", "Length"],
        "Feature Width": ["Width (mm)", "Width (in)", "Width"],
        "Feature Depth": ["Depth (%)", "Max Depth", "Peak Depth"],
        "Feature Orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
        "ILI Chainage": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
        "Joint Number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
    },
    "Rosen-EMAT": {
        "Feature ID": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
        "Feature Type": ["Feature Type", "Feature", "Event"],
        "Feature Description": ["Feature Description", "Description", "Anomaly"],
        "Feature Length": ["Length (mm)", "Length (in)", "Length"],
        "Feature Width": ["Width (mm)", "Width (in)", "Width"],
        "Feature Depth": ["Depth (%)", "Max Depth", "Peak Depth"],
        "Feature Orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
        "ILI Chainage": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
        "Joint Number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
    }
}

# Worksheet name keywords
MDL_WORKSHEET_KEYWORDS = ["Features&Dig", "Features", "Dig"]
ILI_WORKSHEET_KEYWORDS = ["Pipetally", "Pipe Tally", "Tally", "True", "Page-1", "PNG ILI Pipeline Tally"]
ANOMALIES_WORKSHEET_KEYWORDS = ["Anomalies", "Anomaly", "Anomaly Listing"]


# ============================================================================
# Utility Functions
# ============================================================================


def find_worksheet_by_keywords(workbook, keywords: List[str]) -> Optional[str]:
    """
    Find worksheet name by matching against keywords.
    
    Args:
        workbook: openpyxl workbook object
        keywords: List of possible worksheet names
        
    Returns:
        Worksheet name if found, None otherwise
    """
    sheet_names = workbook.sheetnames
    sheet_names_lower = {name.lower(): name for name in sheet_names}
    
    for keyword in keywords:
        keyword_lower = keyword.lower().strip()
        if keyword_lower in sheet_names_lower:
            return sheet_names_lower[keyword_lower]
    return None


def get_cell_from_named_range(workbook, range_name: str):
    """
    Get cell from Excel named range.
    
    Args:
        workbook: openpyxl workbook object
        range_name: Name of the defined range
        
    Returns:
        Cell object if found, None otherwise
    """
    try:
        if range_name not in workbook.defined_names:
            return None
        
        named_range = workbook.defined_names[range_name]
        destinations = list(named_range.destinations)
        
        if not destinations:
            return None
        
        sheet_name, cell_address = destinations[0]
        sheet = workbook[sheet_name]
        return sheet[cell_address]
    except Exception as e:
        logger.debug(f"Error getting named range '{range_name}': {e}")
        return None


def is_valid_dig_id(dig_id: str) -> bool:
    """
    Check if dig ID is valid (must contain 'GW').
    
    Args:
        dig_id: Dig ID string
        
    Returns:
        True if valid, False otherwise
    """
    if not dig_id or pd.isna(dig_id):
        return False
    return "GW" in str(dig_id).upper()


# ============================================================================
# MDL Parsing Functions
# ============================================================================

def parse_mdl_file(file_content: bytes) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Parse MDL (Master Dig List) Excel file.
    
    Args:
        file_content: Bytes content of Excel file
        
    Returns:
        Tuple of (DataFrame with mapped columns, column mapping dict)
    """
    # Load workbook
    wb = load_workbook(io.BytesIO(file_content), data_only=True)
    
    # Find MDL worksheet
    sheet_name = find_worksheet_by_keywords(wb, MDL_WORKSHEET_KEYWORDS)
    if not sheet_name:
        sheet_name = wb.sheetnames[0]  # Default to first sheet
    
    # Read data
    ws = wb[sheet_name]
    data = []
    headers = []
    
    # Find header row (first non-empty row)
    for row in ws.iter_rows():
        row_values = [cell.value for cell in row]
        if any(val for val in row_values):
            headers = row_values
            break
    
    # Read data rows
    header_found = False
    for row in ws.iter_rows():
        row_values = [cell.value for cell in row]
        if not header_found:
            if row_values == headers:
                header_found = True
            continue
        if any(val for val in row_values):
            data.append(row_values)
    
    # Create DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    # Map columns to standard names
    column_mapping = {}
    for standard_name, keywords in GLOBAL_KEYWORDS.items():
        found_col = find_column_names(df, keywords)
        if found_col:
            column_mapping[standard_name] = found_col
    
    return df, column_mapping


def extract_dig_ids(mdl_df: pd.DataFrame, column_mapping: Dict[str, str]) -> List[str]:
    """
    Extract unique valid Dig IDs from MDL.
    
    Args:
        mdl_df: MDL DataFrame
        column_mapping: Column name mapping
        
    Returns:
        List of unique valid Dig IDs
    """
    dig_id_col = column_mapping.get("Dig ID")
    if not dig_id_col:
        return []
    
    dig_ids = mdl_df[dig_id_col].dropna().unique().tolist()
    valid_dig_ids = [dig_id for dig_id in dig_ids if is_valid_dig_id(dig_id)]
    
    return sorted(valid_dig_ids)


# ============================================================================
# ILI Parsing Functions
# ============================================================================

def parse_ili_file(file_content: bytes, vendor_format: str = "Rosen-MFLA") -> Tuple[pd.DataFrame, Dict[str, str], Optional[str]]:
    """
    Parse ILI (In-Line Inspection) Excel file using vendor-specific mapping.
    
    Args:
        file_content: Bytes content of Excel file
        vendor_format: Format of the ILI file (TDW, Rosen-MFLA, etc.)
        
    Returns:
        Tuple of (DataFrame with mapped columns, column mapping dict, worksheet name)
    """
    # Load workbook
    wb = load_workbook(io.BytesIO(file_content), data_only=True)
    
    # Find ILI worksheet
    sheet_name = find_worksheet_by_keywords(wb, ILI_WORKSHEET_KEYWORDS)
    if not sheet_name:
        sheet_name = wb.sheetnames[0]  # Default to first sheet
    
    # Check for Rosen-type data (has Anomalies worksheet)
    anomalies_sheet = find_worksheet_by_keywords(wb, ANOMALIES_WORKSHEET_KEYWORDS)
    if "Rosen" in vendor_format and anomalies_sheet:
        # Use Anomalies worksheet for Rosen-type data
        sheet_name = anomalies_sheet
    
    # Read data
    ws = wb[sheet_name]
    data = []
    headers = []
    
    # Find header row
    for row in ws.iter_rows():
        row_values = [cell.value for cell in row]
        if any(val is not None for val in row_values):
            headers = row_values
            break
    
    # Read data rows
    header_found = False
    for row in ws.iter_rows():
        row_values = [cell.value for cell in row]
        if not header_found:
            if row_values == headers:
                header_found = True
            continue
        if any(val is not None for val in row_values):
            data.append(row_values)
    
    # Create DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    # Map columns to standard names using vendor mapping
    column_mapping = {}
    vendor_keywords = VENDOR_MAPPINGS.get(vendor_format, VENDOR_MAPPINGS["Rosen-MFLA"])
    
    for standard_name, keywords in vendor_keywords.items():
        found_col = find_column_names(df, keywords)
        if found_col:
            column_mapping[standard_name] = found_col
    
    return df, column_mapping, sheet_name


# ============================================================================
# Feature Matching Functions
# ============================================================================

def match_features_by_id(mdl_feature_id: Any, ili_df: pd.DataFrame, ili_col_map: Dict[str, str]) -> pd.DataFrame:
    """
    Match features by Feature ID.
    
    Args:
        mdl_feature_id: Feature ID from MDL
        ili_df: ILI DataFrame
        ili_col_map: ILI column mapping
        
    Returns:
        Matched rows from ILI DataFrame
    """
    feat_id_col = ili_col_map.get("Feature ID")
    if not feat_id_col:
        return pd.DataFrame()
    
    matched = ili_df[ili_df[feat_id_col] == mdl_feature_id]
    return matched


def match_features_by_dimensions(mdl_length: float, mdl_width: float, 
                                 ili_df: pd.DataFrame, ili_col_map: Dict[str, str]) -> pd.DataFrame:
    """
    Match features by dimensions (length and width).
    
    Args:
        mdl_length: Feature length from MDL
        mdl_width: Feature width from MDL
        ili_df: ILI DataFrame
        ili_col_map: ILI column mapping
        
    Returns:
        Matched rows from ILI DataFrame
    """
    length_col = ili_col_map.get("Feature Length")
    width_col = ili_col_map.get("Feature Width")
    
    if not length_col or not width_col:
        return pd.DataFrame()
    
    # Round to 3 decimal places for matching
    mdl_length_rounded = round(float(mdl_length), 3) if pd.notna(mdl_length) else None
    mdl_width_rounded = round(float(mdl_width), 3) if pd.notna(mdl_width) else None
    
    if mdl_length_rounded is None or mdl_width_rounded is None:
        return pd.DataFrame()
    
    # Filter ILI data
    matched = ili_df[
        (ili_df[length_col].apply(lambda x: round(float(x), 3) if pd.notna(x) else None) == mdl_length_rounded) &
        (ili_df[width_col].apply(lambda x: round(float(x), 3) if pd.notna(x) else None) == mdl_width_rounded)
    ]
    
    return matched


def get_target_feature_indices(mdl_features: pd.DataFrame, ili_df: pd.DataFrame,
                               mdl_col_map: Dict[str, str], ili_col_map: Dict[str, str]) -> List[int]:
    """
    Get indices of target features in ILI DataFrame.
    
    Args:
        mdl_features: MDL features for current dig ID
        ili_df: ILI DataFrame
        mdl_col_map: MDL column mapping
        ili_col_map: ILI column mapping
        
    Returns:
        List of ILI DataFrame indices that are target features
    """
    target_indices = []
    
    feat_id_col_mdl = mdl_col_map.get("Feature ID")
    length_col_mdl = mdl_col_map.get("Feature Length")
    width_col_mdl = mdl_col_map.get("Feature Width")
    
    for _, mdl_row in mdl_features.iterrows():
        # Try Feature ID matching first
        if feat_id_col_mdl and feat_id_col_mdl in mdl_row.index:
            feat_id = mdl_row[feat_id_col_mdl]
            if pd.notna(feat_id) and str(feat_id).strip() != "-":
                matched = match_features_by_id(feat_id, ili_df, ili_col_map)
                if not matched.empty:
                    target_indices.extend(matched.index.tolist())
                    continue
        
        # Fallback to dimension matching
        if length_col_mdl and width_col_mdl:
            length = mdl_row.get(length_col_mdl)
            width = mdl_row.get(width_col_mdl)
            if pd.notna(length) and pd.notna(width):
                matched = match_features_by_dimensions(length, width, ili_df, ili_col_map)
                if not matched.empty:
                    target_indices.extend(matched.index.tolist())
    
    return list(set(target_indices))  # Remove duplicates


# ============================================================================
# Template Population Functions
# ============================================================================

def populate_single_value_fields(wb, mdl_row: pd.Series, mdl_col_map: Dict[str, str], 
                                 revision: str, excavation_num: int):
    """
    Populate single-value fields in template using named ranges.
    
    Args:
        wb: openpyxl workbook object
        mdl_row: Single row from MDL for current dig ID
        mdl_col_map: MDL column mapping
        revision: Revision identifier (e.g., '1', '2', 'draft', etc.)
        excavation_num: Excavation number
    """
    # Helper function to get value safely
    def get_value(col_name):
        col = mdl_col_map.get(col_name)
        if col and col in mdl_row.index:
            val = mdl_row[col]
            return val if pd.notna(val) else "-"
        return "-"
    
    # Populate fields
    field_mapping = {
        "tmp_DigID_": get_value("Dig ID"),
        "tmp_revNum": revision,
        "tmp_pipNme": get_value("Pipeline Name"),
        "tmp_pipeOD": get_value("Pipe OD"),
        "tmp_pipeNWT": get_value("Pipe NWT"),
        "tmp_mop": get_value("MOP"),
        "tmp_sep": get_value("SEP"),
        "tmp_Lat": get_value("Latitude"),
        "tmp_Lon": get_value("Longitude"),
        "tmp_mp_": get_value("Milepost"),
        "tmp_tarGWsPipYer": get_value("Pipe Year"),
        "tmp_tarGWsPipGrd": get_value("Pipe Grade"),
        "tmp_ILI_Run_Name": get_value("ILI Run Name"),
        "tmp_ILI_Run_Name_Acc": get_value("ILI Run Accuracy"),
        "US_AGM": get_value("Upstream AGM"),
        "DS_AGM": get_value("Downstream AGM"),
        "tmp_numExv": excavation_num,
    }
    
    for range_name, value in field_mapping.items():
        cell = get_cell_from_named_range(wb, range_name)
        if cell:
            cell.value = value
    
    # Set today's date
    date_cell = get_cell_from_named_range(wb, "tmp_dddIss")
    if date_cell:
        date_cell.value = "=TODAY()"


def populate_excavation_summary(wb, mdl_row: pd.Series, mdl_col_map: Dict[str, str], excavation_num: int):
    """
    Populate excavation summary section.
    
    Args:
        wb: openpyxl workbook object
        mdl_row: Single row from MDL for current dig ID
        mdl_col_map: MDL column mapping
        excavation_num: Excavation number
    """
    def get_value(col_name):
        col = mdl_col_map.get(col_name)
        if col and col in mdl_row.index:
            val = mdl_row[col]
            return val if pd.notna(val) else "-"
        return "-"
    
    # Get active sheet
    ws = wb.active
    
    # Assessment section
    exv_num_cell = get_cell_from_named_range(wb, "tmp_numExv_num")
    if exv_num_cell:
        row = exv_num_cell.row
        col = exv_num_cell.column
        ws.cell(row, col).value = f"Excavation #{excavation_num}"
        ws.cell(row + 1, col).value = get_value("Assessment Length")
        ws.cell(row + 2, col).value = get_value("Start Assessment")
        ws.cell(row + 3, col).value = get_value("End Assessment")
    
    # Exposure section
    exp_num_cell = get_cell_from_named_range(wb, "tmp_numExp_num")
    if exp_num_cell:
        row = exp_num_cell.row
        col = exp_num_cell.column
        ws.cell(row, col).value = f"Excavation #{excavation_num}"
        ws.cell(row + 1, col).value = get_value("Exposure Length")
        ws.cell(row + 2, col).value = get_value("Start Exposure")
        ws.cell(row + 3, col).value = get_value("End Exposure")


def populate_feature_table(wb, ili_datasets: List[Dict[str, Any]], excavation_num: int):
    """
    Populate feature tables for multiple ILI datasets with dynamic rows.
    
    Args:
        wb: openpyxl workbook object
        ili_datasets: List of dicts containing:
            - df: Filtered ILI DataFrame
            - col_map: ILI column mapping
            - target_indices: Indices of target features
            - target_gw_chainage: Target girth weld chainage value
            - format: Vendor format (TDW, Rosen-MFLA, etc.)
        excavation_num: Excavation number
    """
    ws = wb.active
    
    # Find starting row
    start_row_cell = get_cell_from_named_range(wb, "tmp_feaIDs_row")
    if not start_row_cell:
        return
    
    current_row = start_row_cell.row + 2
    
    # Helper for ILI values
    def get_ili_value(row, col_map, col_name):
        col = col_map.get(col_name)
        if col and col in row.index:
            val = row[col]
            if pd.notna(val):
                if isinstance(val, (int, float)):
                    return val if val >= 0 else 0.0
                return val
        return "-"

    # Loop through each ILI dataset
    for ds_idx, dataset in enumerate(ili_datasets):
        ili_df = dataset["df"]
        ili_col_map = dataset["col_map"]
        target_indices = dataset["target_indices"]
        target_gw_chainage = dataset["target_gw_chainage"]
        vendor_format = dataset["format"]

        # Add header for different datasets if more than one
        if len(ili_datasets) > 1:
            ws.insert_rows(current_row)
            header_cell = ws.cell(current_row, 1)
            header_cell.value = f"--- ILI DATA SOURCE: {vendor_format} ---"
            header_cell.font = Font(bold=True, size=12, color="0000FF")
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=10)
            current_row += 1

        # Populate rows for this dataset
        for idx, (ili_idx, ili_row) in enumerate(ili_df.iterrows()):
            # Insert row
            ws.insert_rows(current_row)
            
            # Check if this is a target feature
            is_target = ili_idx in target_indices
            
            # Values
            feat_id = get_ili_value(ili_row, ili_col_map, "Feature ID")
            chainage = get_ili_value(ili_row, ili_col_map, "ILI Chainage")
            
            # Calculate distance from TGW
            dist_from_tgw = "-"
            if isinstance(chainage, (int, float)) and isinstance(target_gw_chainage, (int, float)):
                dist_from_tgw = chainage - target_gw_chainage
            
            # Set values
            ws.cell(current_row, 1).value = str(feat_id)
            ws.cell(current_row, 2).value = excavation_num
            ws.cell(current_row, 3).value = get_ili_value(ili_row, ili_col_map, "Feature Type")
            ws.cell(current_row, 4).value = get_ili_value(ili_row, ili_col_map, "Feature Description")
            ws.cell(current_row, 5).value = get_ili_value(ili_row, ili_col_map, "Feature Depth")
            ws.cell(current_row, 6).value = get_ili_value(ili_row, ili_col_map, "Feature Length")
            ws.cell(current_row, 7).value = get_ili_value(ili_row, ili_col_map, "Feature Width")
            ws.cell(current_row, 8).value = get_ili_value(ili_row, ili_col_map, "Feature Orientation")
            ws.cell(current_row, 9).value = chainage
            ws.cell(current_row, 10).value = dist_from_tgw
            
            # Apply formatting
            if is_target:
                for col_idx in range(1, 11):
                    cell = ws.cell(current_row, col_idx)
                    cell.font = Font(bold=True, color="FF0000")
                    cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
            
            current_row += 1
        
        # Add spacing between datasets
        if ds_idx < len(ili_datasets) - 1:
            ws.insert_rows(current_row)
            current_row += 1


# ============================================================================
# PDF Conversion Functions
# ============================================================================

def convert_excel_to_pdf(excel_path: str, pdf_path: str) -> bool:
    """
    Convert Excel file to PDF.
    
    Args:
        excel_path: Path to Excel file
        pdf_path: Path to output PDF file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Try Windows COM automation (best quality)
        import win32com.client
        
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        wb = excel.Workbooks.Open(str(Path(excel_path).absolute()))
        wb.ActiveSheet.ExportAsFixedFormat(0, str(Path(pdf_path).absolute()))
        wb.Close(False)
        excel.Quit()
        
        return True
    except ImportError:
        # Fallback: Copy Excel as PDF placeholder
        # Note: This won't create actual PDF, just copy the Excel
        # For production, consider weasyprint or reportlab
        logger.warning(f"win32com not available. PDF conversion skipped for {excel_path}")
        return False
    except Exception as e:
        logger.error(f"Error converting Excel to PDF: {type(e).__name__}: {e}")
        return False


# ============================================================================
# Main Generation Function
# ============================================================================

def get_target_gw_chainage(mdl_row: pd.Series, ili_df: pd.DataFrame, 
                          mdl_col_map: Dict[str, str], ili_col_map: Dict[str, str]) -> Optional[float]:
    """
    Get chainage of Target Girth Weld.
    
    Args:
        mdl_row: MDL row for current dig
        ili_df: ILI DataFrame
        mdl_col_map: MDL column mapping
        ili_col_map: ILI column mapping
        
    Returns:
        Chainage value or None if not found
    """
    # Get TGW ID from MDL
    tgw_col = mdl_col_map.get("Target Girth Weld")
    if not tgw_col or tgw_col not in mdl_row.index:
        return None
        
    tgw_id = mdl_row[tgw_col]
    if pd.isna(tgw_id):
        return None
        
    tgw_id_str = str(tgw_id).strip()
    
    # Columns to search in ILI
    search_cols = ["Joint Number", "Girth Weld", "Feature ID", "Feature Description"]
    
    for col_key in search_cols:
        col_name = ili_col_map.get(col_key)
        if not col_name or col_name not in ili_df.columns:
            continue
            
        # Search for exact match
        # We convert column to string for comparison
        matches = ili_df[ili_df[col_name].astype(str).str.strip() == tgw_id_str]
        
        if not matches.empty:
            chainage_col = ili_col_map.get("ILI Chainage")
            if chainage_col and chainage_col in matches.columns:
                return float(matches.iloc[0][chainage_col])
                
    return None


def filter_ili_data_by_range(ili_df: pd.DataFrame, target_gw_chainage: float,
                            mdl_row: pd.Series, mdl_col_map: Dict[str, str],
                            ili_col_map: Dict[str, str]) -> pd.DataFrame:
    """
    Filter ILI data by range around Target Girth Weld.
    
    Args:
        ili_df: ILI DataFrame
        target_gw_chainage: Chainage of TGW
        mdl_row: MDL row
        mdl_col_map: MDL column mapping
        ili_col_map: ILI column mapping
        
    Returns:
        Filtered ILI DataFrame
    """
    chainage_col = ili_col_map.get("ILI Chainage")
    if not chainage_col or chainage_col not in ili_df.columns:
        return ili_df
        
    # Get assessment lengths from MDL
    start_assess_col = mdl_col_map.get("Start Assessment")
    end_assess_col = mdl_col_map.get("End Assessment")
    
    start_offset = 30.0  # Default 30m
    end_offset = 30.0    # Default 30m
    
    if start_assess_col and start_assess_col in mdl_row.index:
        val = mdl_row[start_assess_col]
        if pd.notna(val) and isinstance(val, (int, float)):
            start_offset = abs(float(val))
            
    if end_assess_col and end_assess_col in mdl_row.index:
        val = mdl_row[end_assess_col]
        if pd.notna(val) and isinstance(val, (int, float)):
            end_offset = abs(float(val))
            
    min_chainage = target_gw_chainage - start_offset
    max_chainage = target_gw_chainage + end_offset
    
    # Filter
    mask = (ili_df[chainage_col] >= min_chainage) & (ili_df[chainage_col] <= max_chainage)
    return ili_df[mask].copy()


def generate_dig_packages(mdl_content: bytes, ili_contents: List[bytes], template_content: bytes,
                         revision: str, ili_formats: List[str]):
    """
    Generate dig packages from MDL, multiple ILI datasets, and template.
    
    Args:
        mdl_content: MDL Excel file content
        ili_contents: List of ILI Excel file contents
        template_content: Template Excel file content
        revision: Revision identifier
        ili_formats: List of vendor formats corresponding to ili_contents
        
    Returns:
        BytesIO object containing the ZIP file
    """
    # Parse MDL
    logger.info(f"generate_dig_packages: Parsing MDL, {len(ili_contents)} ILI files, formats={ili_formats}")
    mdl_df, mdl_col_map = parse_mdl_file(mdl_content)
    logger.debug(f"MDL columns mapped: {list(mdl_col_map.keys())}")
    
    # Parse all ILI files
    ili_data_parsed = []
    for i, (content, v_format) in enumerate(zip(ili_contents, ili_formats)):
        try:
            df, col_map, sheet = parse_ili_file(content, v_format)
            ili_data_parsed.append({
                "df": df,
                "col_map": col_map,
                "format": v_format
            })
            logger.info(f"ILI file {i+1} ({v_format}): sheet={sheet}, shape={df.shape}")
        except Exception as e:
            logger.error(f"Error parsing ILI file ({v_format}): {type(e).__name__}: {e}")
    
    if not ili_data_parsed:
        logger.error("No ILI files could be parsed successfully")
        raise ValueError("No ILI files could be parsed successfully")

    # Extract dig IDs
    dig_ids = extract_dig_ids(mdl_df, mdl_col_map)
    logger.info(f"Extracted {len(dig_ids)} dig IDs: {dig_ids[:5]}..." if len(dig_ids) > 5 else f"Extracted dig IDs: {dig_ids}")
    if not dig_ids:
        logger.error("No valid Dig IDs found in MDL file")
        raise ValueError("No valid Dig IDs found in MDL file")
        
    # Create temporary directory for files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Process each dig ID
        for excavation_num, dig_id in enumerate(dig_ids, start=1):
            # Filter MDL for current dig ID
            dig_id_col = mdl_col_map.get("Dig ID")
            mdl_features = mdl_df[mdl_df[dig_id_col] == dig_id]
            if mdl_features.empty:
                continue
            
            mdl_first_row = mdl_features.iloc[0]
            
            # Prepare datasets for this dig ID
            ili_datasets_for_dig = []
            
            for ili_item in ili_data_parsed:
                df = ili_item["df"]
                col_map = ili_item["col_map"]
                v_format = ili_item["format"]
                
                # Find TGW chainage
                target_gw_chainage = get_target_gw_chainage(mdl_first_row, df, mdl_col_map, col_map)
                
                if target_gw_chainage is not None:
                    df_filtered = filter_ili_data_by_range(df, target_gw_chainage, 
                                                         mdl_first_row, mdl_col_map, col_map)
                else:
                    # Fallback
                    df_filtered = df.copy()
                    target_gw_chainage = 0.0
                
                # Get matching features
                target_indices = get_target_feature_indices(mdl_features, df_filtered, 
                                                           mdl_col_map, col_map)
                
                # Only add if there are features in range or it's the first dataset
                if not df_filtered.empty:
                    ili_datasets_for_dig.append({
                        "df": df_filtered,
                        "col_map": col_map,
                        "target_indices": target_indices,
                        "target_gw_chainage": target_gw_chainage,
                        "format": v_format
                    })
            
            if not ili_datasets_for_dig:
                continue

            # Load and populate template
            wb = load_workbook(io.BytesIO(template_content))
            populate_single_value_fields(wb, mdl_first_row, mdl_col_map, revision, excavation_num)
            populate_excavation_summary(wb, mdl_first_row, mdl_col_map, excavation_num)
            populate_feature_table(wb, ili_datasets_for_dig, excavation_num)
            
            # Save Excel
            excel_filename = f"{dig_id}_DP_R{revision}.xlsx"
            excel_path = temp_path / excel_filename
            wb.save(str(excel_path))
            
            # Convert to PDF
            pdf_filename = f"{dig_id}_DP_R{revision}.pdf"
            pdf_path = temp_path / pdf_filename
            convert_excel_to_pdf(str(excel_path), str(pdf_path))
        
        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in temp_path.glob("*"):
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)
        
        zip_buffer.seek(0)
        file_count = len([f for f in temp_path.glob("*") if f.is_file()])
        logger.info(f"generate_dig_packages: Created ZIP with {file_count} files for {len(dig_ids)} dig IDs")
        return zip_buffer

