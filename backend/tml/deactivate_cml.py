"""
De-active CML Module

Processes a source Excel file to generate a dataloader that deactivates all CMLs
included in the uploaded sheet. Output: Status Indicator = "Inactive".
"""

import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from .data_processor import DataProcessor
from .excel_reader import read_excel_auto_sheet
from .file_handler import FileHandler


# Required columns for deactivation (uses flexible column mapping)
DEACTIVATE_REQUIRED_COLUMNS = ["Equipment ID", "CML Group ID", "sub-CML ID"]


def process_deactivate_cml(
    source_path: str,
    template_path: str,
    output_path: str,
    source_sheet: str = "Source_Data",
) -> Tuple[int, Optional[str], Optional[str]]:
    """
    Process source file to generate deactivation dataloader.
    
    All CMLs in the source sheet are marked as Inactive (no filtering).
    Auto-detects which sheet has the required columns (tries Source_Data first, then others).
    
    Args:
        source_path: Path to source Excel file
        template_path: Path to TM_Loader template file
        output_path: Path for output file (e.g., "upload_name_deactive.xlsx")
        source_sheet: Preferred sheet name (default: Source_Data); will try others if not found
        
    Returns:
        Tuple of (records_count, output_file_path, sheet_used) or (0, None, None) if no records
    """
    processor = DataProcessor()
    
    # Read source with auto-detect sheet (tries Source_Data first, then any sheet with required columns)
    source, sheet_used = read_excel_auto_sheet(
        source_path,
        required_columns=DEACTIVATE_REQUIRED_COLUMNS,
        preferred_sheet=source_sheet,
        dtype={"Equipment ID": str},
    )
    
    if source.empty:
        return (0, None, None)
    
    # Add Status Indicator column
    source = source.copy()
    source["Status Indicator"] = "Inactive"
    
    # Read template
    file_handler = FileHandler(
        source_path=source_path,
        template_path=template_path,
        output_dir=str(Path(output_path).parent),
    )
    loader_Assets = file_handler.read_excel("template", "Assets")
    loader_TML = file_handler.read_excel("template", "TML")
    
    column_map = {
        "CML Group ID": "TML Group ID",
        "sub-CML ID": "TML_ID",
        "Status Indicator": "Status Indicator",
    }
    
    records_added = processor.append_and_save(
        loader_Assets,
        loader_TML,
        source,
        column_map,
        output_path,
        "Assets",
        "TML",
    )
    
    return (records_added, output_path if records_added > 0 else None, sheet_used)
