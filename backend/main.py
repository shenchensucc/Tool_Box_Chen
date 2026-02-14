import asyncio
import os
import shutil
import tempfile
import zipfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
from backend.logging_config import get_logger, log_params, log_error

logger = get_logger("backend.main")
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from openpyxl import load_workbook

from backend.models import (
    ColumnStats,
    HealthResponse,
    HistogramData,
    PreviewResponse,
    ProcessResponse,
    TMLProcessResponse,
)
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
from backend.pipeline.metal_loss import assess_metal_loss_feature, mass_assess_metal_loss
from backend.pipeline.ili_reader import read_ili_data, identify_ili_columns
from backend.pipeline.report_generator import generate_word_report
from backend.pipeline.dig_package import generate_dig_packages

app = FastAPI(title="Chen's Engineer Toolbox API", version="0.1.0")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB

# Temporary file storage for TML processing (token -> file_path)
# In production, use Redis or similar
TML_FILE_STORAGE: Dict[str, str] = {}


def validate_excel_file(file: UploadFile) -> None:
    """Validate Excel file type and size"""
    # Validate file type
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Validate file size
    validate_file_size(file)


def validate_file_size(file: UploadFile) -> None:
    """Validate uploaded file size"""
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to start

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024} MB"
        )


def save_temp_file(upload_file: UploadFile) -> Path:
    """Save uploaded file to temporary location"""
    suffix = Path(upload_file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = upload_file.file.read()
        tmp.write(content)
        return Path(tmp.name)


def calculate_stats(series: pd.Series) -> ColumnStats:
    """Calculate statistics for a numeric series"""
    desc = series.describe()
    return ColumnStats(
        count=int(desc["count"]),
        mean=float(desc["mean"]),
        std=float(desc["std"]),
        min=float(desc["min"]),
        max=float(desc["max"]),
        q25=float(desc["25%"]),
        q50=float(desc["50%"]),
        q75=float(desc["75%"]),
    )


def create_histogram(series: pd.Series, column_name: str, bins: int = 30) -> HistogramData:
    """Create histogram data for a numeric series"""
    # Remove NaN values
    clean_series = series.dropna()

    if len(clean_series) == 0:
        return HistogramData(
            column_name=column_name, values=[], bin_edges=[], counts=[]
        )

    counts, bin_edges = np.histogram(clean_series, bins=bins)

    return HistogramData(
        column_name=column_name,
        values=clean_series.tolist(),
        bin_edges=bin_edges.tolist(),
        counts=counts.tolist(),
    )


@app.get("/")
async def root():
    """Redirect root to API docs"""
    return RedirectResponse(url="/docs", status_code=302)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(ok=True)


@app.get("/api/tml/download-template/{template_type}")
async def download_template(template_type: str):
    """
    Download blank template files for TML Data Loader
    
    Args:
        template_type: Type of template to download ("source" or "tm_loader")
    
    Returns:
        Excel template file
    """
    # Define template file paths
    template_dir = Path(__file__).parent / "static" / "templates" / "tml"
    
    templates = {
        "source": {
            "path": template_dir / "Source_Data_Template.xlsx",
            "filename": "Source_Data_Template.xlsx"
        },
        "tm_loader": {
            "path": template_dir / "TM_Loader_Template.xlsx",
            "filename": "TM_Loader_Template.xlsx"
        }
    }
    
    if template_type not in templates:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid template type. Must be 'source' or 'tm_loader'"
        )
    
    template_info = templates[template_type]
    template_path = template_info["path"]
    
    if not template_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Template file not found. Please ensure {template_info['filename']} exists in backend/static/templates/tml/"
        )
    
    return FileResponse(
        path=str(template_path),
        filename=template_info["filename"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={template_info['filename']}"}
    )


@app.post("/api/ili/preview", response_model=PreviewResponse)
async def preview_excel(file: UploadFile = File(...)):
    """
    Preview an Excel file and return sheet names, columns, and row counts
    """
    log_params(logger, "ili/preview", {"filename": file.filename, "content_type": file.content_type})
    validate_excel_file(file)

    temp_path = save_temp_file(file)

    try:
        # Use openpyxl for validation and preview
        wb = load_workbook(temp_path, read_only=True, data_only=True)
        sheet_names = wb.sheetnames

        columns: Dict[str, List[str]] = {}
        row_counts: Dict[str, int] = {}

        for sheet_name in sheet_names:
            df = pd.read_excel(temp_path, sheet_name=sheet_name)
            columns[sheet_name] = df.columns.tolist()
            row_counts[sheet_name] = len(df)

        wb.close()

        logger.info(f"[ili/preview] Processed: {len(sheet_names)} sheets, row_counts={row_counts}")
        return PreviewResponse(
            filename=file.filename,
            sheet_names=sheet_names,
            columns=columns,
            row_counts=row_counts,
        )

    except Exception as e:
        log_error(logger, "ili/preview", e)
        raise HTTPException(status_code=400, detail=f"Error reading Excel file: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            os.unlink(temp_path)


@app.post("/api/ili/process", response_model=ProcessResponse)
async def process_ili_data(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    distance_column: str = Form(None),
    depth_column: str = Form(None),
    metal_loss_column: str = Form(None),
):
    """
    Process ILI data from Excel file and return statistics and plot data
    """
    log_params(logger, "ili/process", {
        "filename": file.filename,
        "sheet_name": sheet_name,
        "distance_column": distance_column,
        "depth_column": depth_column,
        "metal_loss_column": metal_loss_column,
    })
    validate_excel_file(file)

    temp_path = save_temp_file(file)

    try:
        # Read the specified sheet
        df = pd.read_excel(temp_path, sheet_name=sheet_name)

        if df.empty:
            raise HTTPException(status_code=400, detail="Sheet is empty")

        # Auto-identify columns if not provided
        ili_cols = identify_ili_columns(df)
        if not distance_column:
            distance_column = ili_cols.get("distance")
        if not depth_column:
            depth_column = ili_cols.get("depth")
        if not metal_loss_column:
            # Try "depth" as fallback for metal loss if explicit metal loss column not found
            metal_loss_column = ili_cols.get("depth")

        # Collect columns to analyze
        columns_to_analyze = []
        if distance_column and distance_column in df.columns:
            columns_to_analyze.append(distance_column)
        if depth_column and depth_column in df.columns:
            columns_to_analyze.append(depth_column)
        if metal_loss_column and metal_loss_column in df.columns:
            columns_to_analyze.append(metal_loss_column)

        # If no columns specified, use all numeric columns
        if not columns_to_analyze:
            columns_to_analyze = df.select_dtypes(include=[np.number]).columns.tolist()

        # Calculate statistics
        stats: Dict[str, ColumnStats] = {}
        histograms: List[HistogramData] = []

        for col in columns_to_analyze:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                series = df[col].dropna()
                if len(series) > 0:
                    stats[col] = calculate_stats(series)
                    histograms.append(create_histogram(series, col))

        # Prepare scatter data if distance column is available
        scatter_data = None
        if distance_column and distance_column in df.columns:
            scatter_data = {"x_column": distance_column, "x_values": df[distance_column].tolist()}

            # Add y-axis data for depth and metal loss
            y_data = {}
            if depth_column and depth_column in df.columns:
                y_data["depth"] = df[depth_column].tolist()
            if metal_loss_column and metal_loss_column in df.columns:
                y_data["metal_loss"] = df[metal_loss_column].tolist()

            scatter_data["y_data"] = y_data

        logger.info(
            f"[ili/process] Processed: sheet={sheet_name}, total_rows={len(df)}, "
            f"stats_columns={list(stats.keys())}, histograms={len(histograms)}"
        )
        return ProcessResponse(
            filename=file.filename,
            sheet_name=sheet_name,
            total_rows=len(df),
            stats=stats,
            histograms=histograms,
            scatter_data=scatter_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "ili/process", e)
        raise HTTPException(status_code=400, detail=f"Error processing Excel file: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            os.unlink(temp_path)


@app.post("/api/tml/process", response_model=TMLProcessResponse)
async def process_tml_data(
    source_file: UploadFile = File(...),
    template_file: UploadFile = File(...),
    workflows: str = Form(...),
):
    """
    Process TML data with selected workflows and generate both ZIP and combined outputs
    
    Args:
        source_file: Source Excel file
        template_file: Template Excel file (TM_Loader.xlsx)
        workflows: Comma-separated list of workflow IDs (1-20)
    
    Returns:
        JSON with tokens to download ZIP file and combined file separately
    """
    log_params(logger, "tml/process", {
        "source_filename": source_file.filename,
        "template_filename": template_file.filename,
        "workflows_raw": workflows,
    })
    # Validate file types and sizes
    validate_excel_file(source_file)
    validate_excel_file(template_file)
    
    # Parse workflow IDs
    try:
        workflow_ids = [int(w.strip()) for w in workflows.split(",") if w.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workflow IDs format")
    
    if not workflow_ids:
        raise HTTPException(status_code=400, detail="No workflows selected")
    
    # Create temporary directory for processing (persistent across requests)
    temp_dir = tempfile.mkdtemp()
    temp_source = None
    temp_template = None
    temp_output_dir = None
    zip_path = None
    combined_path = None
    
    try:
        # Save uploaded files
        temp_source = save_temp_file(source_file)
        temp_template = save_temp_file(template_file)
        temp_output_dir = Path(temp_dir) / "output"
        temp_output_dir.mkdir(exist_ok=True)
        
        # Initialize file handler
        file_handler = FileHandler(
            source_path=str(temp_source),
            template_path=str(temp_template),
            output_dir=str(temp_output_dir)
        )
        
        # Read source data and filter
        try:
            source = file_handler.read_excel("source", "Source_Data")
            logger.info(f"[tml/process] Source data shape: {source.shape}")
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Error reading source file. Ensure it has a sheet named 'Source_Data'. Error: {str(e)}"
            )
        
        # Check for required column
        if "AER_Status_CML" not in source.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Source file missing required column 'AER_Status_CML'. Found columns: {', '.join(source.columns.tolist())}"
            )
        
        # Filter source data for AER_Status_CML with value "Yes"
        source = source[source["AER_Status_CML"].str.contains("Yes", na=False)].copy()
        logger.info(f"[tml/process] Filtered source data shape: {source.shape}")
        
        if source.empty:
            raise HTTPException(
                status_code=400,
                detail="No records found with AER_Status_CML containing 'Yes'. Please check your source data."
            )
        
        # Read template data
        try:
            loader_Assets = file_handler.read_excel("template", "Assets")
            loader_TML = file_handler.read_excel("template", "TML")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error reading template file. Ensure it has sheets named 'Assets' and 'TML'. Error: {str(e)}"
            )
        
        # Copy template file to output directory as base for all workflows
        for file_key in file_handler.output_files.keys():
            shutil.copy(temp_template, file_handler.output_files[file_key])
        
        # Define workflow mapping
        workflow_map = {
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
        
        # Process selected workflows
        processed_files = []
        workflow_summary = {}
        
        for workflow_id in workflow_ids:
            if workflow_id not in workflow_map:
                logger.warning(f"[tml/process] Invalid workflow ID {workflow_id}, skipping")
                workflow_summary[workflow_id] = 0
                continue
            
            process_func, file_key = workflow_map[workflow_id]
            output_file = file_handler.output_files[file_key]
            
            try:
                logger.info(f"[tml/process] Processing workflow {workflow_id}...")
                records_count, result_file = process_func(source, loader_Assets, loader_TML, output_file)
                workflow_summary[workflow_id] = records_count
                
                # Only add to processed_files if records were actually added
                if result_file and records_count > 0:
                    processed_files.append(result_file)
                    logger.info(f"[tml/process] Workflow {workflow_id}: Added {records_count} records")
                else:
                    logger.info(f"[tml/process] Workflow {workflow_id}: No records to add, skipping file creation")
            except Exception as e:
                log_error(logger, f"tml/process workflow {workflow_id}", e)
                workflow_summary[workflow_id] = 0
                # Continue with other workflows even if one fails
        
        if not processed_files:
            raise HTTPException(status_code=400, detail="No workflows were successfully processed. All workflows returned 0 records.")
        
        # Create ZIP file with all processed outputs
        zip_path = Path(temp_dir) / "TML_Output.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in processed_files:
                if os.path.exists(file_path):
                    zipf.write(file_path, os.path.basename(file_path))
        
        # Create combined output file
        from backend.tml.data_processor import DataProcessor
        combined_path = Path(temp_dir) / "TML_Combined_Output.xlsx"
        DataProcessor.create_combined_output(
            processed_files=processed_files,
            output_file=str(combined_path),
            template_assets=loader_Assets,
            template_tml=loader_TML,
            asset_sheet_name="Assets",
            tml_sheet_name="TML"
        )
        
        # Generate unique tokens for both files
        zip_token = str(uuid.uuid4())
        combined_token = str(uuid.uuid4())
        
        # Store file paths with tokens
        TML_FILE_STORAGE[zip_token] = str(zip_path)
        TML_FILE_STORAGE[combined_token] = str(combined_path)
        
        logger.info(
            f"[tml/process] Completed: {len(processed_files)} workflows, "
            f"workflow_summary={workflow_summary}"
        )
        # Return tokens and metadata
        return TMLProcessResponse(
            success=True,
            message="TML data processed successfully",
            zip_token=zip_token,
            combined_token=combined_token,
            workflows_processed=len(processed_files),
            workflow_summary=workflow_summary,
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "tml/process", e)
        raise HTTPException(status_code=500, detail=f"Error processing TML data: {str(e)}")


@app.get("/api/tml/download/{file_token}")
async def download_tml_file(file_token: str):
    """
    Download TML output file using a file token
    
    Args:
        file_token: Unique token for the file (returned from /api/tml/process)
    
    Returns:
        ZIP or Excel file based on the token
    """
    if file_token not in TML_FILE_STORAGE:
        raise HTTPException(
            status_code=404,
            detail="File not found. The file may have expired or the token is invalid."
        )
    
    file_path = TML_FILE_STORAGE[file_token]
    
    if not os.path.exists(file_path):
        # Clean up the token if file doesn't exist
        del TML_FILE_STORAGE[file_token]
        raise HTTPException(
            status_code=404,
            detail="File not found on server."
        )
    
    # Determine file type and set appropriate media type
    file_name = os.path.basename(file_path)
    if file_path.endswith('.zip'):
        media_type = "application/zip"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )


@app.post("/api/pipeline/metal-loss/assess")
async def assess_metal_loss(
    do: float = Form(...),
    tp: float = Form(...),
    YS: float = Form(...),
    TS: float = Form(...),
    dimp_org_percent: float = Form(...),
    Limp_org: float = Form(...),
    date_ILI: str = Form(...),
    ILI_dimp_tolerance: float = Form(...),
    ILI_Limp_tolerance: float = Form(...),
    CR_low: float = Form(...),
    CR_ave: float = Form(...),
    CR_high: float = Form(...),
    month_CR: int = Form(...),
    feature_ID: str = Form(""),
    vendor_ILI: str = Form(""),
    CR_Limp: float = Form(0.0)
):
    """
    Assess metal loss feature and return calculated results.
    
    Returns:
        JSON with assessment results including depth/pressure arrays
    """
    log_params(logger, "metal-loss/assess", {
        "do": do, "tp": tp, "YS": YS, "TS": TS,
        "dimp_org_percent": dimp_org_percent, "Limp_org": Limp_org,
        "date_ILI": date_ILI, "ILI_dimp_tolerance": ILI_dimp_tolerance,
        "ILI_Limp_tolerance": ILI_Limp_tolerance,
        "CR_low": CR_low, "CR_ave": CR_ave, "CR_high": CR_high,
        "month_CR": month_CR, "feature_ID": feature_ID,
        "vendor_ILI": vendor_ILI, "CR_Limp": CR_Limp,
    })
    try:
        results = assess_metal_loss_feature(
            do=do,
            tp=tp,
            YS=YS,
            TS=TS,
            dimp_org_percent=dimp_org_percent,
            Limp_org=Limp_org,
            date_ILI=date_ILI,
            ILI_dimp_tolerance=ILI_dimp_tolerance,
            ILI_Limp_tolerance=ILI_Limp_tolerance,
            CR_low=CR_low,
            CR_ave=CR_ave,
            CR_high=CR_high,
            month_CR=month_CR,
            feature_ID=feature_ID,
            vendor_ILI=vendor_ILI,
            CR_Limp=CR_Limp
        )
        logger.info(f"[metal-loss/assess] Success for feature_ID={feature_ID}")
        return results
    except Exception as e:
        log_error(logger, "metal-loss/assess", e)
        raise HTTPException(status_code=400, detail=f"Error in assessment: {str(e)}")


@app.post("/api/pipeline/metal-loss/mass-assess")
async def mass_assess_metal_loss_endpoint(
    file: UploadFile = File(...),
    do: float = Form(...),
    tp: float = Form(...),
    YS: float = Form(...),
    TS: float = Form(...),
    depth_tolerance: float = Form(...),
    length_tolerance: float = Form(...),
    depth_cr: float = Form(4.0),
    length_cr: float = Form(25.0),
    start_year: int = Form(...)
):
    """
    Mass assess metal loss features from an Excel file.
    """
    log_params(logger, "metal-loss/mass-assess", {
        "filename": file.filename,
        "do": do, "tp": tp, "YS": YS, "TS": TS,
        "depth_tolerance": depth_tolerance, "length_tolerance": length_tolerance,
        "depth_cr": depth_cr, "length_cr": length_cr, "start_year": start_year,
    })
    validate_excel_file(file)
    temp_input = save_temp_file(file)
    
    try:
        # Read Excel using the centralized ILI reader
        df = read_ili_data(temp_input)
        logger.info(f"[metal-loss/mass-assess] Read {len(df)} rows from Excel")
        
        # Process
        df_result = mass_assess_metal_loss(
            df=df,
            do=do,
            tp=tp,
            YS=YS,
            TS=TS,
            depth_tolerance=depth_tolerance,
            length_tolerance=length_tolerance,
            depth_cr=depth_cr,
            length_cr=length_cr,
            start_year=start_year
        )
        
        logger.info(f"[metal-loss/mass-assess] Processed {len(df_result)} rows, output columns={list(df_result.columns)}")
        # Save to temporary Excel file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            df_result.to_excel(tmp.name, index=False)
            tmp_path = tmp.name
            
        return FileResponse(
            path=tmp_path,
            filename=f"Mass_Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d')}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=Mass_Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d')}.xlsx"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error in mass assessment: {str(e)}")
    finally:
        if temp_input.exists():
            os.unlink(temp_input)


@app.post("/api/pipeline/metal-loss/export-word")
async def export_word_report(
    assessment_results: str = Form(...),
    depth_growth_chart: UploadFile = File(...),
    sop_decay_chart: UploadFile = File(...),
    sop_cutoff_chart: UploadFile = File(...)
):
    """
    Generate and download Word document report.
    
    Parameters:
        assessment_results: JSON string of assessment results
        depth_growth_chart: PNG image of depth growth chart
        sop_decay_chart: PNG image of SOP decay chart
        sop_cutoff_chart: PNG image of SOP cutoff chart
    
    Returns:
        Word document (.docx) file
    """
    log_params(logger, "metal-loss/export-word", {
        "assessment_results_len": len(assessment_results) if assessment_results else 0,
        "depth_growth_chart": depth_growth_chart.filename,
        "sop_decay_chart": sop_decay_chart.filename,
        "sop_cutoff_chart": sop_cutoff_chart.filename,
    })
    try:
        import json
        
        # Parse assessment results
        results = json.loads(assessment_results)
        
        # Read chart images
        chart_images = {
            'depth_growth': await depth_growth_chart.read(),
            'sop_decay': await sop_decay_chart.read(),
            'sop_cutoff': await sop_cutoff_chart.read()
        }
        
        # Generate Word document (run in thread pool to avoid blocking async event loop)
        doc_bytes = await asyncio.to_thread(generate_word_report, results, chart_images)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            tmp.write(doc_bytes)
            tmp_path = tmp.name
        
        logger.info("[metal-loss/export-word] Word report generated successfully")
        # Return file
        return FileResponse(
            path=tmp_path,
            filename=f"Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"}
        )
    
    except json.JSONDecodeError as e:
        log_error(logger, "metal-loss/export-word (JSON decode)", e)
        raise HTTPException(status_code=400, detail="Invalid assessment results JSON")
    except Exception as e:
        log_error(logger, "metal-loss/export-word", e)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@app.post("/api/pipeline/dig-package/generate")
async def generate_dig_package_endpoint(
    mdl_file: UploadFile = File(...),
    ili_files: List[UploadFile] = File(...),
    template_file: UploadFile = File(...),
    revision: str = Form("0"),
    ili_formats: str = Form(""),
):
    """
    Generate dig packages from MDL, multiple ILI data files, and template files.
    """
    log_params(logger, "dig-package/generate", {
        "mdl_filename": mdl_file.filename,
        "ili_count": len(ili_files),
        "ili_filenames": [f.filename for f in ili_files],
        "template_filename": template_file.filename,
        "revision": revision,
        "ili_formats": ili_formats,
    })
    try:
        # Validate file sizes
        validate_file_size(mdl_file)
        for ili_file in ili_files:
            validate_file_size(ili_file)
        validate_file_size(template_file)

        # Read contents
        mdl_content = await mdl_file.read()
        template_content = await template_file.read()
        
        ili_contents = []
        for ili_file in ili_files:
            ili_contents.append(await ili_file.read())
            
        # Parse formats
        formats_list = ili_formats.split(",") if ili_formats else ["Rosen-MFLA"] * len(ili_files)
        logger.info(f"[dig-package/generate] Parsed: {len(ili_contents)} ILI files, formats={formats_list}")

        # Generate dig packages
        from backend.pipeline.dig_package import generate_dig_packages
        
        zip_buffer = generate_dig_packages(
            mdl_content=mdl_content,
            ili_contents=ili_contents,
            template_content=template_content,
            revision=revision,
            ili_formats=formats_list
        )
        
        logger.info("[dig-package/generate] Dig packages generated successfully")
        # Create temporary file for ZIP
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            tmp.write(zip_buffer.getvalue())
            tmp_path = tmp.name
        
        # Return ZIP file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return FileResponse(
            path=tmp_path,
            filename=f"Dig_Packages_R{revision}_{timestamp}.zip",
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=Dig_Packages_R{revision}_{timestamp}.zip"}
        )

    except Exception as e:
        log_error(logger, "dig-package/generate", e)
        raise HTTPException(status_code=500, detail=f"Error generating dig packages: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True) 