"""
Shared TML batch execution for /api/tml/process and New CML Helper generate step.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List

import pandas as pd

from backend.logging_config import get_logger, log_error
from backend.models import TMLProcessResponse
from backend.tml.data_processor import DataProcessor
from backend.tml.file_handler import FileHandler
from backend.tml.workflows._01_status import process_status_indicator
from backend.tml.workflows._02_follow_up_cml import process_follow_up_cml
from backend.tml.workflows._03_code_year_tmin import process_code_year_tmin
from backend.tml.workflows._04_design_code import process_design_code
from backend.tml.workflows._05_material_spec import process_material_specification
from backend.tml.workflows._06_material_grade import process_material_grade
from backend.tml.workflows._07_design_temperature import process_design_temperature
from backend.tml.workflows._08_piping_formula import process_piping_formula
from backend.tml.workflows._09_od import process_od
from backend.tml.workflows._10_nps import process_nps
from backend.tml.workflows._11_schedule import process_schedule
from backend.tml.workflows._12_design_pressure import process_design_pressure
from backend.tml.workflows._13_temperature_coefficient import process_temperature_coefficient
from backend.tml.workflows._14_tnom import process_tnom
from backend.tml.workflows._15_tmin import process_tmin
from backend.tml.workflows._16_override_allowable_stress import process_override_allowable_stress
from backend.tml.workflows._17_allowable_stress import process_allowable_stress
from backend.tml.workflows._18_design_factor import process_design_factor
from backend.tml.workflows._19_joint_factor import process_joint_factor
from backend.tml.workflows._20_location_factor import process_location_factor

logger = get_logger("backend.tml.tml_batch_runner")

WORKFLOW_MAP = {
    1: (process_status_indicator, "Status"),
    2: (process_follow_up_cml, "FollowUp"),
    3: (process_code_year_tmin, "CodeYearTmin"),
    4: (process_design_code, "DesignCode"),
    5: (process_material_specification, "MaterialSpec"),
    6: (process_material_grade, "MaterialGrade"),
    7: (process_design_temperature, "T"),
    8: (process_piping_formula, "PF"),
    9: (process_od, "OD"),
    10: (process_nps, "NPS"),
    11: (process_schedule, "Schedule"),
    12: (process_design_pressure, "P"),
    13: (process_temperature_coefficient, "TempCoef"),
    14: (process_tnom, "Tnom"),
    15: (process_tmin, "Tmin"),
    16: (process_override_allowable_stress, "OAS"),
    17: (process_allowable_stress, "AS"),
    18: (process_design_factor, "DF"),
    19: (process_joint_factor, "JF"),
    20: (process_location_factor, "LF"),
}


class TMLBatchError(Exception):
    """Validation or processing failure for TML batch; maps to HTTP error."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def read_and_filter_source(file_handler: FileHandler) -> pd.DataFrame:
    try:
        source = file_handler.read_excel("source", "Source_Data")
        logger.info(f"[tml_batch] Source data shape: {source.shape}")
    except Exception as e:
        raise TMLBatchError(
            f"Error reading source file. Ensure it has a sheet named 'Source_Data'. Error: {str(e)}"
        ) from e

    if "AER_Status_CML" not in source.columns:
        raise TMLBatchError(
            "Source file missing required column 'AER_Status_CML'. Found columns: "
            + ", ".join(source.columns.tolist())
        )

    filtered = source[source["AER_Status_CML"].astype(str).str.contains("Yes", na=False)].copy()
    logger.info(f"[tml_batch] Filtered source data shape: {filtered.shape}")

    if filtered.empty:
        raise TMLBatchError(
            "No records found with AER_Status_CML containing 'Yes'. Please check your source data."
        )

    return filtered


def run_tml_batch(
    temp_source: Path,
    temp_template: Path,
    workflow_ids: List[int],
    temp_dir: Path,
    store_token_fn: Callable[[str], str],
) -> TMLProcessResponse:
    """
    Run selected TML workflows; write ZIP + combined workbook under temp_dir.

    store_token_fn: callable(path_str) -> token_str for download registry (backend-specific).
    """
    temp_output_dir = temp_dir / "output"
    temp_output_dir.mkdir(exist_ok=True)

    file_handler = FileHandler(
        source_path=str(temp_source),
        template_path=str(temp_template),
        output_dir=str(temp_output_dir),
    )

    source = read_and_filter_source(file_handler)

    try:
        loader_assets = file_handler.read_excel("template", "Assets")
        loader_tml = file_handler.read_excel("template", "TML")
    except Exception as e:
        raise TMLBatchError(
            f"Error reading template file. Ensure it has sheets named 'Assets' and 'TML'. Error: {str(e)}"
        ) from e

    for file_key in file_handler.output_files.keys():
        shutil.copy(temp_template, file_handler.output_files[file_key])

    processed_files: List[str] = []
    workflow_summary: Dict[int, int] = {}

    for workflow_id in workflow_ids:
        if workflow_id not in WORKFLOW_MAP:
            logger.warning(f"[tml_batch] Invalid workflow ID {workflow_id}, skipping")
            workflow_summary[workflow_id] = 0
            continue

        process_func, file_key = WORKFLOW_MAP[workflow_id]
        output_file = file_handler.output_files[file_key]

        try:
            logger.info(f"[tml_batch] Processing workflow {workflow_id}...")
            records_count, result_file = process_func(source, loader_assets, loader_tml, output_file)
            workflow_summary[workflow_id] = records_count
            if result_file and records_count > 0:
                processed_files.append(result_file)
                logger.info(f"[tml_batch] Workflow {workflow_id}: Added {records_count} records")
            else:
                logger.info(f"[tml_batch] Workflow {workflow_id}: No records to add, skipping file creation")
        except Exception as e:
            log_error(logger, f"tml_batch workflow {workflow_id}", e)
            workflow_summary[workflow_id] = 0

    if not processed_files:
        raise TMLBatchError(
            "No workflows were successfully processed. All workflows returned 0 records."
        )

    zip_path = temp_dir / "TML_Output.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in processed_files:
            if os.path.exists(file_path):
                zipf.write(file_path, os.path.basename(file_path))

    combined_path = temp_dir / "TML_Combined_Output.xlsx"
    DataProcessor.create_combined_output(
        processed_files=processed_files,
        output_file=str(combined_path),
        template_assets=loader_assets,
        template_tml=loader_tml,
        asset_sheet_name="Assets",
        tml_sheet_name="TML",
    )

    zip_token = store_token_fn(str(zip_path))
    combined_token = store_token_fn(str(combined_path))

    logger.info(
        f"[tml_batch] Completed: {len(processed_files)} workflows, workflow_summary={workflow_summary}"
    )

    return TMLProcessResponse(
        success=True,
        message="TML data processed successfully",
        zip_token=zip_token,
        combined_token=combined_token,
        workflows_processed=len(processed_files),
        workflow_summary=workflow_summary,
        timestamp=datetime.now().isoformat(),
    )
