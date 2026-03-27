"""
Dig Package Generation Module

This module handles the generation of dig package Excel and PDF files from:
- MDL (Master Dig List)
- ILI (In-Line Inspection) data
- Template Excel file

It matches features, populates templates, and generates individual dig packages.
"""

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

from backend.logging_config import get_logger
from backend.pipeline.ili_reader import (
    COLUMN_KEYWORDS as ILI_COLUMN_KEYWORDS,
    find_column_names,
    merge_keyword_sets,
    read_excel_with_detected_header,
)

logger = get_logger("backend.pipeline.dig_package")


# ============================================================================
# Keyword Definitions for Column Matching
# ============================================================================

# MDL columns use a different schema from source ILI files.
MDL_COLUMN_KEYWORDS = {
    # Prefer "Dig ID" (numeric Integrity IDs like 6000); "Dig Name" is the long package label for filenames.
    "dig_id": ["Dig ID", "NEW Dig Name", "Excavation ID"],
    "dig_name": ["Dig Name", "DigName", "Dig Package Name"],
    "feature_id": ["Feature ID", "ILI Feature ID", "ID#", "Feature Identifier", "Target ID"],
    "pipeline_name": ["Pipeline Name", "Pipeline_Name", "PipelineName", "Line Name"],
    "pipe_od": ["Pipe OD", "Pipe_OD", "PipeOD", "OD (mm)", "Pipe Diameter"],
    "pipe_nwt": ["Pipe NWT", "Pipe_NWT", "PipeNWT", "Nominal Wall Thickness (mm)", "Wall Thickness"],
    "mop": ["MOP", "MAOP", "Maximum Operating Pressure"],
    "sep": ["SEP", "Safe Excavation Pressure"],
    "latitude": ["Latitude", "Lat"],
    "longitude": ["Longitude", "Lon", "Long"],
    "milepost": ["Milepost", "MP", "Mile Post"],
    "pipe_year": ["Pipe Year", "Year", "Installation Year"],
    "pipe_grade": ["Pipe Grade", "Grade", "Material Grade"],
    "ili_run_name": ["ILI Run Name", "ILI Run", "Run Name"],
    "ili_run_accuracy": ["ILI Run Accuracy", "Run Accuracy", "ILI Accuracy"],
    "upstream_agm": ["Upstream AGM", "US AGM", "US_AGM"],
    "downstream_agm": ["Downstream AGM", "DS AGM", "DS_AGM"],
    "assessment_length": ["Assessment Length", "Assess Length"],
    "start_assessment": ["Start Assessment", "Assessment Start", "US Assessment"],
    "end_assessment": ["End Assessment", "Assessment End", "DS Assessment"],
    "exposure_length": ["Exposure Length", "Expose Length"],
    "start_exposure": ["Start Exposure", "Exposure Start", "US Exposure"],
    "end_exposure": ["End Exposure", "Exposure End", "DS Exposure"],
    "target_girth_weld": ["Target Girth Weld (TGW)", "Target Girth Weld", "Target GW", "TGW", "Target Joint"],
    "length": ["Feature Length", "Length", "Length (mm)", "Length (in)"],
    "width": ["Feature Width", "Width", "Width (mm)", "Width (in)"],
}

ILI_VENDOR_KEYWORD_OVERRIDES = {
    "TDW": {
        "feature_id": ["ID", "Feature Number", "FeatureID", "Target ID"],
        "feature_type": ["Type", "Feature Type", "Anomaly Type"],
        "feature_desc": ["Description", "Feature Description", "Anomaly Description"],
        "length": ["Length", "Length (in)", "Length (mm)"],
        "width": ["Width", "Width (in)", "Width (mm)"],
        "depth": ["Depth", "Depth (%)", "Max Depth"],
        "orientation": ["Orientation", "Clock Orientation", "O'Clock"],
        "distance": ["Chainage", "Odometer", "Distance"],
        "joint_number": ["Joint", "Joint Number", "Weld Number"],
    },
    "Rosen-MFLA": {
        "feature_id": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
        "feature_type": ["Feature Type", "Feature", "Event"],
        "feature_desc": ["Feature Description", "Description", "Anomaly"],
        "length": ["Length (mm)", "Length (in)", "Length"],
        "width": ["Width (mm)", "Width (in)", "Width"],
        "depth": ["Depth (%)", "Max Depth", "Peak Depth"],
        "orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
        "distance": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
        "joint_number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
    },
    "Rosen-MFLC": {
        "feature_id": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
        "feature_type": ["Feature Type", "Feature", "Event"],
        "feature_desc": ["Feature Description", "Description", "Anomaly"],
        "length": ["Length (mm)", "Length (in)", "Length"],
        "width": ["Width (mm)", "Width (in)", "Width"],
        "depth": ["Depth (%)", "Max Depth", "Peak Depth"],
        "orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
        "distance": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
        "joint_number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
    },
    "Rosen-EMAT": {
        "feature_id": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
        "feature_type": ["Feature Type", "Feature", "Event"],
        "feature_desc": ["Feature Description", "Description", "Anomaly"],
        "length": ["Length (mm)", "Length (in)", "Length"],
        "width": ["Width (mm)", "Width (in)", "Width"],
        "depth": ["Depth (%)", "Max Depth", "Peak Depth"],
        "orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
        "distance": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
        "joint_number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
    }
}

# Worksheet name keywords
MDL_WORKSHEET_KEYWORDS = [
    "Dig Notification Log",
    "Features&Dig",
    "Features",
    "Dig",
]
ILI_WORKSHEET_KEYWORDS = ["Pipetally", "Pipe Tally", "Tally", "True", "Page-1", "PNG ILI Pipeline Tally"]
ANOMALIES_WORKSHEET_KEYWORDS = ["Anomalies", "Anomaly", "Anomaly Listing"]


# ============================================================================
# Utility Functions
# ============================================================================


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


def is_valid_dig_id(dig_id: Union[str, int, float, None]) -> bool:
    """
    Accept Integrity-style numeric dig IDs (e.g. 6000) or legacy IDs containing 'GW'.
    """
    if dig_id is None or (isinstance(dig_id, float) and pd.isna(dig_id)):
        return False
    s = str(dig_id).strip()
    if not s or s.lower() in {"-", "nan", "none"}:
        return False
    if "GW" in s.upper():
        return True
    # PNG Integrity program: short numeric Dig ID (column "Dig ID")
    try:
        n = float(s.replace(",", ""))
        if n.is_integer() and 1000 <= abs(n) <= 999999:
            return True
    except (ValueError, TypeError, AttributeError):
        pass
    return False


def _sanitize_package_filename_base(name: str) -> str:
    """Safe single segment for Excel/PDF output stem (PNG-style dig package names)."""
    out = "".join(c if c not in '<>:"/\\|?*' else "_" for c in str(name).strip())
    return out.strip(" ._") or "dig_package"


def _mdl_rows_for_dig_id(mdl_df: pd.DataFrame, dig_id_col: str, dig_id: Any) -> pd.DataFrame:
    """Match MDL rows where Dig ID may be int, float, or string (e.g. 6000 vs 6000.0)."""
    col = mdl_df[dig_id_col]
    tnum = pd.to_numeric(pd.Series([dig_id]), errors="coerce").iloc[0]
    cnum = pd.to_numeric(col, errors="coerce")
    if pd.notna(tnum):
        mask = cnum == tnum
        if bool(mask.any()):
            return mdl_df[mask]
    ds = col.astype(str).str.strip()
    return mdl_df[ds == str(dig_id).strip()]


def package_output_stem(mdl_row: pd.Series, mdl_col_map: Dict[str, str], dig_id: Any) -> str:
    """Excel/PDF base name: prefer **Dig Name** (e.g. ID6000_R1R2_..._ML), else dig id."""
    name_col = mdl_col_map.get("dig_name")
    if name_col and name_col in mdl_row.index:
        val = mdl_row[name_col]
        if pd.notna(val) and str(val).strip() not in ("", "-"):
            return _sanitize_package_filename_base(str(val).strip())
    return _sanitize_package_filename_base(dig_id)


def _normalize_match_value(value: Any) -> str:
    """Normalize IDs and labels so matching is resilient to whitespace and numeric formatting."""
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else f"{float(value):.6f}".rstrip("0").rstrip(".")
    text = str(value).strip()
    try:
        numeric_value = float(text.replace(",", ""))
        return str(int(numeric_value)) if numeric_value.is_integer() else f"{numeric_value:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return " ".join(text.upper().split())


def _coerce_numeric(value: Any) -> Optional[float]:
    numeric = pd.to_numeric(value, errors="coerce")
    return float(numeric) if pd.notna(numeric) else None


def _dimensions_match(mdl_value: Any, ili_value: Any) -> bool:
    """
    Match numeric dimensions directly or via mm/in conversion.
    This catches common MDL-vs-vendor unit differences without overfitting.
    """
    mdl_num = _coerce_numeric(mdl_value)
    ili_num = _coerce_numeric(ili_value)
    if mdl_num is None or ili_num is None:
        return False

    direct_match = abs(mdl_num - ili_num) <= max(0.01, 0.01 * max(abs(mdl_num), abs(ili_num)))
    if direct_match:
        return True

    mm_to_in = mdl_num / 25.4
    in_to_mm = mdl_num * 25.4
    tolerance = max(0.02, 0.02 * max(abs(ili_num), abs(mm_to_in), abs(in_to_mm)))
    return abs(mm_to_in - ili_num) <= tolerance or abs(in_to_mm - ili_num) <= tolerance


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
    df, column_mapping, sheet_name, header_row = read_excel_with_detected_header(
        file_content=file_content,
        keyword_map=MDL_COLUMN_KEYWORDS,
        sheet_keywords=MDL_WORKSHEET_KEYWORDS,
        min_matches=3,
    )
    logger.info(
        f"parse_mdl_file: sheet='{sheet_name}', header_row={header_row}, mapped={list(column_mapping.keys())}"
    )
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
    dig_id_col = column_mapping.get("dig_id")
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
    sheet_keywords = ANOMALIES_WORKSHEET_KEYWORDS if "Rosen" in vendor_format else ILI_WORKSHEET_KEYWORDS
    keyword_map = merge_keyword_sets(
        ILI_COLUMN_KEYWORDS,
        ILI_VENDOR_KEYWORD_OVERRIDES.get(vendor_format, ILI_VENDOR_KEYWORD_OVERRIDES["Rosen-MFLA"]),
    )
    df, column_mapping, sheet_name, header_row = read_excel_with_detected_header(
        file_content=file_content,
        keyword_map=keyword_map,
        sheet_keywords=sheet_keywords,
        min_matches=4,
    )
    logger.info(
        f"parse_ili_file: vendor={vendor_format}, sheet='{sheet_name}', header_row={header_row}, mapped={list(column_mapping.keys())}"
    )
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
    feat_id_col = ili_col_map.get("feature_id")
    if not feat_id_col:
        return pd.DataFrame()

    mdl_key = _normalize_match_value(mdl_feature_id)
    matched = ili_df[ili_df[feat_id_col].apply(_normalize_match_value) == mdl_key]
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
    length_col = ili_col_map.get("length")
    width_col = ili_col_map.get("width")
    
    if not length_col or not width_col:
        return pd.DataFrame()
    
    if pd.isna(mdl_length) or pd.isna(mdl_width):
        return pd.DataFrame()

    matched = ili_df[
        ili_df[length_col].apply(lambda x: _dimensions_match(mdl_length, x)) &
        ili_df[width_col].apply(lambda x: _dimensions_match(mdl_width, x))
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
    
    feat_id_col_mdl = mdl_col_map.get("feature_id")
    length_col_mdl = mdl_col_map.get("length")
    width_col_mdl = mdl_col_map.get("width")
    
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
    
    def get_dig_display_for_template() -> str:
        """PNG-style packages label the dig using **Dig Name** (e.g. ID6000_…_ML), not the numeric Dig ID."""
        name_col = mdl_col_map.get("dig_name")
        if name_col and name_col in mdl_row.index:
            val = mdl_row[name_col]
            if pd.notna(val) and str(val).strip() not in ("", "-"):
                return str(val).strip()
        return get_value("dig_id")

    # Populate fields
    field_mapping = {
        "tmp_DigID_": get_dig_display_for_template(),
        "tmp_revNum": revision,
        "tmp_pipNme": get_value("pipeline_name"),
        "tmp_pipeOD": get_value("pipe_od"),
        "tmp_pipeNWT": get_value("pipe_nwt"),
        "tmp_mop": get_value("mop"),
        "tmp_sep": get_value("sep"),
        "tmp_Lat": get_value("latitude"),
        "tmp_Lon": get_value("longitude"),
        "tmp_mp_": get_value("milepost"),
        "tmp_tarGWsPipYer": get_value("pipe_year"),
        "tmp_tarGWsPipGrd": get_value("pipe_grade"),
        "tmp_ILI_Run_Name": get_value("ili_run_name"),
        "tmp_ILI_Run_Name_Acc": get_value("ili_run_accuracy"),
        "US_AGM": get_value("upstream_agm"),
        "DS_AGM": get_value("downstream_agm"),
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
    
    # Assessment section
    exv_num_cell = get_cell_from_named_range(wb, "tmp_numExv_num")
    if exv_num_cell:
        ws = exv_num_cell.parent
        row = exv_num_cell.row
        col = exv_num_cell.column
        ws.cell(row, col).value = f"Excavation #{excavation_num}"
        ws.cell(row + 1, col).value = get_value("assessment_length")
        ws.cell(row + 2, col).value = get_value("start_assessment")
        ws.cell(row + 3, col).value = get_value("end_assessment")
    
    # Exposure section
    exp_num_cell = get_cell_from_named_range(wb, "tmp_numExp_num")
    if exp_num_cell:
        ws = exp_num_cell.parent
        row = exp_num_cell.row
        col = exp_num_cell.column
        ws.cell(row, col).value = f"Excavation #{excavation_num}"
        ws.cell(row + 1, col).value = get_value("exposure_length")
        ws.cell(row + 2, col).value = get_value("start_exposure")
        ws.cell(row + 3, col).value = get_value("end_exposure")


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
    # Find starting row
    start_row_cell = get_cell_from_named_range(wb, "tmp_feaIDs_row")
    if not start_row_cell:
        return
    ws = start_row_cell.parent
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
            feat_id = get_ili_value(ili_row, ili_col_map, "feature_id")
            chainage = get_ili_value(ili_row, ili_col_map, "distance")
            
            # Calculate distance from TGW
            dist_from_tgw = "-"
            if isinstance(chainage, (int, float)) and isinstance(target_gw_chainage, (int, float)):
                dist_from_tgw = chainage - target_gw_chainage
            
            # Set values
            ws.cell(current_row, 1).value = str(feat_id)
            ws.cell(current_row, 2).value = excavation_num
            ws.cell(current_row, 3).value = get_ili_value(ili_row, ili_col_map, "feature_type")
            ws.cell(current_row, 4).value = get_ili_value(ili_row, ili_col_map, "feature_desc")
            ws.cell(current_row, 5).value = get_ili_value(ili_row, ili_col_map, "depth")
            ws.cell(current_row, 6).value = get_ili_value(ili_row, ili_col_map, "length")
            ws.cell(current_row, 7).value = get_ili_value(ili_row, ili_col_map, "width")
            ws.cell(current_row, 8).value = get_ili_value(ili_row, ili_col_map, "orientation")
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
    excel = None
    workbook = None
    try:
        # Try Windows COM automation (best quality)
        import win32com.client

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        workbook = excel.Workbooks.Open(str(Path(excel_path).absolute()))
        workbook.ExportAsFixedFormat(0, str(Path(pdf_path).absolute()))
        return True
    except ImportError:
        logger.warning(f"win32com not available. PDF conversion skipped for {excel_path}")
        return False
    except Exception as e:
        logger.error(f"Error converting Excel to PDF: {type(e).__name__}: {e}")
        return False
    finally:
        if workbook is not None:
            try:
                workbook.Close(False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass


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
    tgw_col = mdl_col_map.get("target_girth_weld")
    if not tgw_col or tgw_col not in mdl_row.index:
        return None
        
    tgw_id = mdl_row[tgw_col]
    if pd.isna(tgw_id):
        return None
        
    tgw_id_str = _normalize_match_value(tgw_id)

    # Columns to search in ILI
    search_columns = [
        ili_col_map.get("joint_number"),
        ili_col_map.get("feature_id"),
        ili_col_map.get("feature_desc"),
        find_column_names(ili_df, ["Girth Weld", "Girth Weld No", "GWD", "GW"]),
    ]

    chainage_col = ili_col_map.get("distance")
    if not chainage_col or chainage_col not in ili_df.columns:
        return None

    for col_name in search_columns:
        if not col_name or col_name not in ili_df.columns:
            continue

        matches = ili_df[ili_df[col_name].apply(_normalize_match_value) == tgw_id_str]
        if not matches.empty:
            chainage = _coerce_numeric(matches.iloc[0][chainage_col])
            if chainage is not None:
                return chainage

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
    chainage_col = ili_col_map.get("distance")
    if not chainage_col or chainage_col not in ili_df.columns:
        return ili_df
        
    # Get assessment lengths from MDL
    start_assess_col = mdl_col_map.get("start_assessment")
    end_assess_col = mdl_col_map.get("end_assessment")
    
    start_offset = 30.0  # Default 30m
    end_offset = 30.0    # Default 30m
    
    if start_assess_col and start_assess_col in mdl_row.index:
        val = _coerce_numeric(mdl_row[start_assess_col])
        if val is not None:
            start_offset = abs(val)

    if end_assess_col and end_assess_col in mdl_row.index:
        val = _coerce_numeric(mdl_row[end_assess_col])
        if val is not None:
            end_offset = abs(val)

    min_chainage = target_gw_chainage - start_offset
    max_chainage = target_gw_chainage + end_offset

    chainage_numeric = pd.to_numeric(ili_df[chainage_col], errors="coerce")
    mask = (chainage_numeric >= min_chainage) & (chainage_numeric <= max_chainage)
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
    if len(ili_contents) != len(ili_formats):
        raise ValueError(
            f"ILI file count ({len(ili_contents)}) does not match format count ({len(ili_formats)})."
        )

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
        
        summary = {
            "revision": revision,
            "dig_ids_requested": dig_ids,
            "generated": [],
            "skipped": [],
            "ili_files": [{"format": item["format"], "rows": len(item["df"])} for item in ili_data_parsed],
        }

        # Process each dig ID
        for excavation_num, dig_id in enumerate(dig_ids, start=1):
            # Filter MDL for current dig ID
            dig_id_col = mdl_col_map.get("dig_id")
            mdl_features = _mdl_rows_for_dig_id(mdl_df, dig_id_col, dig_id)
            if mdl_features.empty:
                summary["skipped"].append({"dig_id": dig_id, "reason": "No MDL rows matched dig ID after parsing"})
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
                summary["skipped"].append({"dig_id": dig_id, "reason": "No ILI rows found in assessment range"})
                continue

            # Load and populate template
            wb = load_workbook(io.BytesIO(template_content))
            populate_single_value_fields(wb, mdl_first_row, mdl_col_map, revision, excavation_num)
            populate_excavation_summary(wb, mdl_first_row, mdl_col_map, excavation_num)
            populate_feature_table(wb, ili_datasets_for_dig, excavation_num)

            out_stem = package_output_stem(mdl_first_row, mdl_col_map, dig_id)
            # Save Excel
            excel_filename = f"{out_stem}_DP_R{revision}.xlsx"
            excel_path = temp_path / excel_filename
            wb.save(str(excel_path))
            
            # Convert to PDF
            pdf_filename = f"{out_stem}_DP_R{revision}.pdf"
            pdf_path = temp_path / pdf_filename
            pdf_generated = convert_excel_to_pdf(str(excel_path), str(pdf_path))
            summary["generated"].append({
                "dig_id": dig_id,
                "excavation_num": excavation_num,
                "excel_file": excel_filename,
                "pdf_file": pdf_filename if pdf_generated else None,
                "pdf_generated": pdf_generated,
                "ili_dataset_count": len(ili_datasets_for_dig),
            })

        if not summary["generated"]:
            raise ValueError("No dig packages were generated. Check MDL mapping and ILI matching results.")

        summary_path = temp_path / f"Dig_Package_Generation_Summary_R{revision}.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        
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

