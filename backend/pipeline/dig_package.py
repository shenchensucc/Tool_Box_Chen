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


# ============================================================================
# Keyword Definitions for Column Matching
# ============================================================================

COLUMN_KEYWORDS = {
    # MDL Keywords
    "Dig ID": ["Dig Name", "Dig ID", "DigName", "NEW Dig Name"],
    "Feature ID": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID", "Feature Number"],
    "Feature Type": ["Feature Type", "Feature", "Event", "Anomaly Type"],
    "Feature Description": ["Feature Description", "Description", "Feature", "Anomaly Description", "Event", "Anomaly"],
    "Feature Length": ["Length (in)", "Length (mm)", "Feature Length (mm)", "Feature Length (in)", "Length", "Length (in.)", "Length (mm)"],
    "Feature Width": ["Width (in)", "Width", "Width (mm)", "Feature Width (mm)", "Feature Width (in)", "Width (in.)", "Width (mm)"],
    "Feature Depth": ["Depth (%)", "Max Depth", "Max. Depth", "Peak Depth", "Peak Depth (% WT)", "Feature Depth", "Depth", "Depth (mm)"],
    "Feature Orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)", "Feature Orientation", "Feature Orientation (Center of feature) (hh:mm)", "(Degree)", "o'clock"],
    "ILI Chainage": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)", "Log Distance", "ILI Chainage/Odometer (m)", "ILI Chainage", "Odometer", "Wheel Count (ft.)", "ILI Distance (m)"],
    "Joint Number": ["Joint No. or US GW No.", "Joint No", "US GW No", "PNG Joint Number", "Client Jno.", "Feature Identifier"],
    "Joint Length": ["Joint Length", "Joint Length (ft)", "Joint Length (m)"],
    "Seam Orientation": ["Seam Weld Orientation (hh:mm)", "D/S Seam Weld Orientation", "Seam Orientation (clock)", "D/S Seam Weld Orientation (hh:mm)", "SWD Orientation (hh:mm)", "o'clock"],
    "Pipeline Name": ["Pipeline Name", "Pipeline_Name", "PipelineName"],
    "Pipe OD": ["Pipe OD", "Pipe_OD", "PipeOD", "OD (mm)"],
    "Pipe NWT": ["Pipe NWT", "Pipe_NWT", "PipeNWT", "Nominal Wall Thickness (mm)"],
    "Pipe Grade": ["Pipe Grade", "Pipe_Grade", "PipeGrade"],
    "Pipe Year": ["Pipe Year", "Pipe_Year", "PipeYear"],
    "MOP": ["MOP (psi)", "MOP", "PipeGrade", "MOP (PSI)"],
    "SEP": ["SEP (psi)", "Safe Excavation Pressure", "Excavation Pressure", "SEP"],
    "Milepost": ["Milepost", "MP", "US MP", "Field_1"],
    "Latitude": ["TGW Lat (deg)", "Lat", "Latitude", "Latitude (°)"],
    "Longitude": ["TGW Lon (deg)", "Long", "Longitude", "Lon", "Longitude (°)"],
    "Target Girth Weld": ["TGW", "Target Girth Weld"],
    "Assessment Length": ["Total Assessment Length (m)", "Total Assessment Length", "Assessment Length"],
    "Start Assessment": ["Start Assessment to TGW (m)", "Start Assessment to TGW", "Start Assessment"],
    "End Assessment": ["End Assessment to TGW (m)", "End Assessment to TGW", "End Assessment"],
    "Exposure Length": ["Total Exposed Pipe Length (m)", "Total Exposed Pipe Length", "Total Exposed Length"],
    "Start Exposure": ["Start Exposed Pipe to TGW (m)", "Start Exposed Pipe to TGW", "Start Exposed Pipe"],
    "End Exposure": ["End Exposed Pipe to TGW (m)", "End Exposed Pipe to TGW", "End Exposed Pipe"],
    "ILI Run Name": ["ILI", "ILI Run Name"],
    "ILI Run Accuracy": ["SEP Expiry Date", "XYZ Accuracy", "ILI Run Name Accuracy"],
    "Upstream AGM": ["U/S AGM"],
    "Downstream AGM": ["D/S AGM"],
    "Girth Weld": ["Girth Weld", "Weld", "Area End Installation", "Area End Launcher", "Area Start Installation", "Area Start Receiver", "Girth Weld wall thickness down", "Girth Weld wall thickness up", "GirthWeld"],
}

# Worksheet name keywords
MDL_WORKSHEET_KEYWORDS = ["Features&Dig", "Features", "Dig"]
ILI_WORKSHEET_KEYWORDS = ["Pipetally", "Pipe Tally", "Tally", "True", "Page-1", "PNG ILI Pipeline Tally"]
ANOMALIES_WORKSHEET_KEYWORDS = ["Anomalies", "Anomaly", "Anomaly Listing"]


# ============================================================================
# Utility Functions
# ============================================================================

def find_column_by_keywords(headers: List[str], keywords: List[str]) -> Optional[str]:
    """
    Search for column name by matching header against list of keywords.
    
    Args:
        headers: List of column headers from Excel
        keywords: List of possible keyword matches
        
    Returns:
        Column name if found, None otherwise
    """
    headers_lower = {h.strip(): h for h in headers if h}
    
    for keyword in keywords:
        keyword_lower = keyword.lower().strip()
        for header_lower, header_original in headers_lower.items():
            if header_lower.lower() == keyword_lower:
                return header_original
    return None


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
        print(f"Error getting named range '{range_name}': {e}")
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
    for standard_name, keywords in COLUMN_KEYWORDS.items():
        found_col = find_column_by_keywords(df.columns.tolist(), keywords)
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

def parse_ili_file(file_content: bytes) -> Tuple[pd.DataFrame, Dict[str, str], Optional[str]]:
    """
    Parse ILI (In-Line Inspection) Excel file.
    
    Args:
        file_content: Bytes content of Excel file
        
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
    if sheet_name == "Pipetally" and anomalies_sheet:
        # Use Anomalies worksheet for Rosen-type data
        sheet_name = anomalies_sheet
    
    # Read data
    ws = wb[sheet_name]
    data = []
    headers = []
    
    # Find header row
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
    for standard_name, keywords in COLUMN_KEYWORDS.items():
        found_col = find_column_by_keywords(df.columns.tolist(), keywords)
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


def populate_feature_table(wb, ili_df_filtered: pd.DataFrame, ili_col_map: Dict[str, str],
                           target_indices: List[int], excavation_num: int, target_gw_chainage: float):
    """
    Populate feature table with dynamic rows.
    
    Args:
        wb: openpyxl workbook object
        ili_df_filtered: Filtered ILI DataFrame
        ili_col_map: ILI column mapping
        target_indices: Indices of target features
        excavation_num: Excavation number
        target_gw_chainage: Target girth weld chainage value
    """
    ws = wb.active
    
    # Find starting row
    start_row_cell = get_cell_from_named_range(wb, "tmp_feaIDs_row")
    if not start_row_cell:
        return
    
    start_row = start_row_cell.row + 2
    
    # Column mapping
    def get_ili_value(row, col_name):
        col = ili_col_map.get(col_name)
        if col and col in row.index:
            val = row[col]
            if pd.notna(val):
                return val if val >= 0 or not isinstance(val, (int, float)) else "-"
        return "-"
    
    # Populate rows
    for idx, (ili_idx, ili_row) in enumerate(ili_df_filtered.iterrows()):
        current_row = start_row + idx
        
        # Insert row if needed (except for first row)
        if idx > 0:
            ws.insert_rows(current_row)
        
        # Check if this is a target feature
        is_target = ili_idx in target_indices
        
        # Populate columns
        feat_id = get_ili_value(ili_row, "Feature ID")
        chainage = get_ili_value(ili_row, "ILI Chainage")
        
        # Calculate distance from TGW
        dist_from_tgw = "-"
        if isinstance(chainage, (int, float)) and isinstance(target_gw_chainage, (int, float)):
            dist_from_tgw = chainage - target_gw_chainage
        
        # Set values
        ws.cell(current_row, 1).value = str(feat_id)
        ws.cell(current_row, 2).value = excavation_num
        ws.cell(current_row, 3).value = get_ili_value(ili_row, "Feature Type")
        ws.cell(current_row, 4).value = get_ili_value(ili_row, "Feature Description")
        ws.cell(current_row, 5).value = get_ili_value(ili_row, "Feature Depth")
        ws.cell(current_row, 6).value = get_ili_value(ili_row, "Feature Length")
        ws.cell(current_row, 7).value = get_ili_value(ili_row, "Feature Width")
        ws.cell(current_row, 8).value = get_ili_value(ili_row, "Feature Orientation")
        ws.cell(current_row, 9).value = chainage
        ws.cell(current_row, 10).value = dist_from_tgw
        
        # Apply formatting
        if is_target:
            # Target feature: Bold, Red, Grey background
            for col_idx in range(1, 11):
                cell = ws.cell(current_row, col_idx)
                cell.font = Font(bold=True, color="FF0000")
                cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
        else:
            # Regular feature: Normal formatting
            for col_idx in range(1, 11):
                cell = ws.cell(current_row, col_idx)
                cell.font = Font(bold=False, color="000000")
                cell.fill = PatternFill(fill_type=None)


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
        print(f"Warning: win32com not available. PDF conversion skipped for {excel_path}")
        return False
    except Exception as e:
        print(f"Error converting Excel to PDF: {e}")
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


def generate_dig_packages(mdl_content: bytes, ili_content: bytes, template_content: bytes,
                         revision: str):
    """
    Generate dig packages from source files (Generator).
    
    Args:
        mdl_content: MDL Excel file content
        ili_content: ILI Excel file content
        template_content: Template Excel file content
        revision: Revision identifier (e.g., '1', '2', 'draft', etc.)
        
    Yields:
        JSON string with progress update or final result
    """
    # Parse files
    mdl_df, mdl_col_map = parse_mdl_file(mdl_content)
    ili_df, ili_col_map, ili_sheet = parse_ili_file(ili_content)
    
    # Extract dig IDs
    dig_ids = extract_dig_ids(mdl_df, mdl_col_map)
    
    if not dig_ids:
        raise ValueError("No valid Dig IDs found in MDL file")
        
    total_digs = len(dig_ids)
    yield json.dumps({"type": "start", "total": total_digs}) + "\n"
    
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
            
            # Get first row for single-value fields
            mdl_first_row = mdl_features.iloc[0]
            
            # Extract parameters for logging
            params = {}
            for key in ["Pipe OD", "Pipe NWT", "MOP", "Target Girth Weld", "Pipeline Name"]:
                 col = mdl_col_map.get(key)
                 if col and col in mdl_first_row.index:
                     params[key] = str(mdl_first_row[col])
            
            yield json.dumps({
                "type": "progress", 
                "current": excavation_num, 
                "dig_id": dig_id, 
                "stage": "processing",
                "params": params
            }) + "\n"
            
            # Get target girth weld chainage
            target_gw_chainage = get_target_gw_chainage(mdl_first_row, ili_df, mdl_col_map, ili_col_map)
            
            if target_gw_chainage is not None:
                ili_df_filtered = filter_ili_data_by_range(ili_df, target_gw_chainage, 
                                                         mdl_first_row, mdl_col_map, ili_col_map)
            else:
                # Fallback if TGW not found
                # Use full dataframe but set TGW chainage to 0.0 (distances will be absolute)
                ili_df_filtered = ili_df.copy()
                target_gw_chainage = 0.0
            
            # Get target feature indices
            target_indices = get_target_feature_indices(mdl_features, ili_df_filtered, 
                                                       mdl_col_map, ili_col_map)
            
            
            # Load template
            wb = load_workbook(io.BytesIO(template_content))
            
            # Populate template
            populate_single_value_fields(wb, mdl_first_row, mdl_col_map, revision, excavation_num)
            populate_excavation_summary(wb, mdl_first_row, mdl_col_map, excavation_num)
            populate_feature_table(wb, ili_df_filtered, ili_col_map, target_indices, 
                                  excavation_num, target_gw_chainage)
            
            # Save Excel file
            excel_filename = f"{dig_id}_DP_R{revision}.xlsx"
            excel_path = temp_path / excel_filename
            wb.save(str(excel_path))
            
            # Convert to PDF
            pdf_filename = f"{dig_id}_DP_R{revision}.pdf"
            pdf_path = temp_path / pdf_filename
            convert_excel_to_pdf(str(excel_path), str(pdf_path))
        
        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in temp_path.glob("*"):
                if file_path.is_file():
                    zip_file.write(file_path, file_path.name)
        
        zip_buffer.seek(0)
        zip_base64 = base64.b64encode(zip_buffer.getvalue()).decode('utf-8')
        
        yield json.dumps({
            "type": "result",
            "zip_data": zip_base64,
            "filename": f"Dig_Packages_R{revision}.zip"
        }) + "\n"

