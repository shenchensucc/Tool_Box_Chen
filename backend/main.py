import os
import tempfile
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook

from backend.models import (
    ColumnStats,
    HealthResponse,
    HistogramData,
    PreviewResponse,
    ProcessResponse,
)

app = FastAPI(title="Chen's Engineer Toolbox API", version="0.1.0")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB


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


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(ok=True)


@app.post("/api/ili/preview", response_model=PreviewResponse)
async def preview_excel(file: UploadFile = File(...)):
    """
    Preview an Excel file and return sheet names, columns, and row counts
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")

    validate_file_size(file)

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

        return PreviewResponse(
            filename=file.filename,
            sheet_names=sheet_names,
            columns=columns,
            row_counts=row_counts,
        )

    except Exception as e:
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
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")

    validate_file_size(file)

    temp_path = save_temp_file(file)

    try:
        # Read the specified sheet
        df = pd.read_excel(temp_path, sheet_name=sheet_name)

        if df.empty:
            raise HTTPException(status_code=400, detail="Sheet is empty")

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
        raise HTTPException(status_code=400, detail=f"Error processing Excel file: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path.exists():
            os.unlink(temp_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True) 