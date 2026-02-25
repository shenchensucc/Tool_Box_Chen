import asyncio
import os
import shutil
from pathlib import Path

# Load .env from project root (secrets stay out of git)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
    if not _env_path.exists():
        load_dotenv()  # Fallback: load from current working directory
except ImportError:
    pass
import tempfile
import zipfile
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
from backend.logging_config import get_logger, log_params, log_error

logger = get_logger("backend.main")
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from openpyxl import load_workbook

from backend.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ColumnStats,
    DeactivateCMLResponse,
    FeatureMapResponse,
    HealthResponse,
    HistogramData,
    InspectionReportResponse,
    PreviewResponse,
    ProcessResponse,
    TMLProcessResponse,
)
from backend.tml.deactivate_cml import process_deactivate_cml
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
from backend.pipeline.ili_reader import (
    identify_ili_columns,
    parse_pasted_ili_text,
    read_ili_data,
)
from backend.pipeline.report_generator import generate_word_report
from backend.pipeline.dig_package import generate_dig_packages
from backend.docs_loader import get_relevant_context
from backend.llm_config import get_chat_base_url, get_api_key, DEFAULT_MODEL
from backend.tools.web_search import web_search
from backend.tools.schemas import WEB_SEARCH_SCHEMA

app = FastAPI(title="Chen's Engineer Toolbox API", version="0.1.0")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_404_middleware(request, call_next):
    """Log 404 responses with path and method for debugging."""
    response = await call_next(request)
    if response.status_code == 404:
        logger.warning(f"[404] {request.method} {request.url.path} — Route not found. Restart backend if you added new endpoints.")
    return response

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


def validate_pdf_file(file: UploadFile) -> None:
    """Validate PDF file type and size"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF (.pdf)")
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


@app.on_event("startup")
async def startup_log_routes():
    """Log key routes at startup to verify endpoints are registered."""
    ili_routes = [r for r in app.routes if hasattr(r, "path") and "ili" in r.path]
    insp_routes = [r for r in app.routes if hasattr(r, "path") and "inspection-report" in r.path]
    logger.info(f"[startup] ILI routes: {[(r.path, getattr(r, 'methods', '')) for r in ili_routes]}")
    logger.info(f"[startup] Inspection report routes: {[(r.path, getattr(r, 'methods', '')) for r in insp_routes]}")


@app.get("/")
async def root():
    """Redirect root to API docs"""
    return RedirectResponse(url="/docs", status_code=302)


@app.get("/api/search")
async def api_web_search(q: str, max_results: int = 6):
    """
    Web search endpoint using AI Builders Space MCP (Tavily).
    Query parameter: q (search query)
    """
    from backend.tools.web_search import web_search
    result = web_search(query=q, max_results=max_results)
    return {"query": q, "result": result}


@app.get("/api/chat/models")
async def list_chat_models():
    """List available LLM models for Chat with Chen."""
    from backend.llm_config import LLM_OPTIONS
    return {"models": LLM_OPTIONS, "default": DEFAULT_MODEL}


MAX_AGENT_TURNS = 3


def _to_dict(obj):
    """Convert OpenAI response object to dict for API."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj) if obj else {}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_completion(request: ChatRequest):
    """
    Chat completion with full agentic loop: tool calls (web_search) executed
    and fed back to the LLM, up to MAX_AGENT_TURNS times.
    """
    import json

    log_params(logger, "chat", {"model": request.model, "msg_count": len(request.messages)})
    logger.info("[Agent] Starting chat completion")

    api_key = get_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI_BUILDER_TOKEN not configured. Copy .env.example to .env and set your token.",
        )

    # Build messages
    messages: List[dict] = [
        {"role": m.role, "content": m.content}
        for m in request.messages
    ]

    # Inject tool docs context for tool-related questions (last user message)
    last_user = next((m for m in reversed(request.messages) if m.role == "user"), None)
    if last_user and last_user.content:
        ctx = get_relevant_context(last_user.content)
        if ctx:
            system_ctx = (
                "You are 'Chen', a helpful assistant for Chen's Engineer Toolbox. "
                "You have access to the following tool documentation. Use it to answer questions about the tools.\n\n"
                f"{ctx}"
            )
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = system_ctx + "\n\n" + messages[0]["content"]
            else:
                messages.insert(0, {"role": "system", "content": system_ctx})

    tools = request.tools or [WEB_SEARCH_SCHEMA]
    tool_choice = request.tool_choice or "auto"

    from openai import OpenAI
    client = OpenAI(
        base_url=get_chat_base_url(),
        api_key=api_key,
    )

    msg = None
    turn = 0
    last_tool_calls: List = []

    while turn < MAX_AGENT_TURNS:
        turn += 1
        logger.info(f"[Agent] Turn {turn}/{MAX_AGENT_TURNS}")

        try:
            response = client.chat.completions.create(
                model=request.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=2048,
            )
        except Exception as e:
            log_error(logger, "chat", e)
            raise HTTPException(status_code=502, detail=str(e))

        choice = response.choices[0] if response.choices else None
        if not choice:
            raise HTTPException(status_code=502, detail="No completion returned")

        msg = choice.message
        last_tool_calls = getattr(msg, "tool_calls", None) or []

        if not last_tool_calls:
            content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "") or ""
            logger.info(f"[Agent] Final Answer: '{content[:200]}{'...' if len(content) > 200 else ''}'")
            break

        # Execute tool calls
        assistant_msg = _to_dict(msg)
        messages.append(assistant_msg)

        for tc in last_tool_calls:
            fn = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
            if not fn:
                continue
            name = fn.name if hasattr(fn, "name") else fn.get("name")
            args_str = fn.arguments if hasattr(fn, "arguments") else fn.get("arguments", "{}")
            logger.info(f"[Agent] Decided to call tool: '{name}'")

            result = ""
            if name == "web_search":
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    query = args.get("query", "")
                    result = web_search(query)
                except Exception as e:
                    result = f"Error: {str(e)}"
            else:
                result = f"Unknown tool: {name}"

            tc_id = tc.id if hasattr(tc, "id") else tc.get("id", "call_0")
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })
            preview = result[:150] + "..." if len(result) > 150 else result
            logger.info(f"[System] Tool Output: '{preview}'")

    content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "") or ""
    if not content and turn >= MAX_AGENT_TURNS and last_tool_calls:
        content = "(Max turns reached; could not complete tool chain.)"
        logger.warning("[Agent] Max turns reached with pending tool calls")
    return ChatResponse(
        content=content or "(No response)",
        model=request.model,
        tool_calls=None,
    )


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


def _build_feature_map_from_df(
    df: pd.DataFrame,
    ili_cols: Dict[str, Optional[str]],
) -> tuple:
    """
    Build features, scatter_data, and sources from a DataFrame with identified ILI columns.
    Returns (features, scatter_data, sources).
    """
    dist_col = ili_cols.get("distance")
    depth_col = ili_cols.get("depth") or ili_cols.get("metal_loss")
    length_col = ili_cols.get("length")
    width_col = ili_cols.get("width")
    fid_col = ili_cols.get("feature_id")
    ftype_col = ili_cols.get("feature_type")
    fdesc_col = ili_cols.get("feature_desc")
    orient_col = ili_cols.get("orientation")
    joint_col = ili_cols.get("joint_number")
    source_col = ili_cols.get("source")
    gwd_col = next(
        (c for c in df.columns if "gwd" in str(c).lower() or ("u/s" in str(c).lower() and "ili" in str(c).lower() and "number" in str(c).lower())),
        joint_col,
    )
    seam_orient_col = next((c for c in df.columns if "seam" in str(c).lower() and "orientation" in str(c).lower()), None)

    for col in [c for c in [dist_col, depth_col, length_col, width_col] if c and c in df.columns]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    features = []
    for idx, row in df.iterrows():
        try:
            x_val = pd.to_numeric(row.get(dist_col), errors="coerce")
            if pd.isna(x_val):
                continue
        except (TypeError, ValueError):
            continue

        depth_val = 0.0
        if depth_col and depth_col in df.columns:
            try:
                dv = float(pd.to_numeric(row.get(depth_col), errors="coerce"))
                if dv is not None and not (isinstance(dv, float) and pd.isna(dv)):
                    depth_val = dv
            except (TypeError, ValueError):
                pass

        length_val = 0.0
        if length_col and length_col in df.columns:
            try:
                ln = float(pd.to_numeric(row.get(length_col), errors="coerce"))
                if ln and not (isinstance(ln, float) and pd.isna(ln)):
                    length_val = ln
            except (TypeError, ValueError):
                pass

        width_val = 0.0
        if width_col and width_col in df.columns:
            try:
                wd = float(pd.to_numeric(row.get(width_col), errors="coerce"))
                if wd and not (isinstance(wd, float) and pd.isna(wd)):
                    width_val = wd
            except (TypeError, ValueError):
                pass

        orient_val = row.get(orient_col) if orient_col and orient_col in df.columns else None
        orientation_deg = _parse_orientation_to_degrees(orient_val)
        orientation_hours = _parse_orientation_to_hours(orient_val)

        feature_type = str(row.get(ftype_col, "")).strip() if ftype_col and ftype_col in df.columns else ""
        gwd_number = None
        if (gwd_col and gwd_col in df.columns) or (joint_col and joint_col in df.columns):
            val = row.get(gwd_col or joint_col)
            if pd.notna(val):
                try:
                    gwd_number = int(float(val))
                except (ValueError, TypeError):
                    gwd_number = str(val).strip()
        seam_orient_val = row.get(seam_orient_col) if seam_orient_col and seam_orient_col in df.columns else None
        seam_orient_hours = _parse_orientation_to_hours(seam_orient_val)

        source_val = str(row.get(source_col, "")).strip() if source_col and source_col in df.columns and pd.notna(row.get(source_col)) else ""

        parts = []
        if fid_col and fid_col in df.columns:
            parts.append(f"<b>Feature ID:</b> {row.get(fid_col, '')}")
        if ftype_col and ftype_col in df.columns:
            parts.append(f"<b>Type:</b> {row.get(ftype_col, '')}")
        if fdesc_col and fdesc_col in df.columns:
            parts.append(f"<b>Description:</b> {row.get(fdesc_col, '')}")
        if depth_col and depth_col in df.columns:
            parts.append(f"<b>Depth:</b> {row.get(depth_col, '')}")
        if length_col and length_col in df.columns:
            parts.append(f"<b>Length (mm):</b> {row.get(length_col, '')}")
        if width_col and width_col in df.columns:
            parts.append(f"<b>Width (mm):</b> {row.get(width_col, '')}")
        if orient_col and orient_col in df.columns:
            parts.append(f"<b>Orientation:</b> {row.get(orient_col, '')}")
        if source_val:
            parts.append(f"<b>Source:</b> {source_val}")
        parts.append(f"<b>Chainage (m):</b> {x_val}")
        hover_text = "<br>".join(parts)

        feat = {
            "x": float(x_val),
            "y": float(depth_val),
            "depth": float(depth_val),
            "length": float(length_val),
            "width": float(width_val),
            "orientation_deg": orientation_deg,
            "orientation_hours": float(orientation_hours) if orientation_hours is not None else 6.0,
            "feature_type": feature_type,
            "gwd_number": gwd_number,
            "seam_orient_hours": float(seam_orient_hours) if seam_orient_hours is not None else None,
            "hover_text": hover_text,
            "feature_id": str(row.get(fid_col, idx)) if fid_col and fid_col in df.columns else str(idx),
            "source": source_val,
        }
        features.append(feat)

    scatter_data = None
    girth_welds = []
    seam_welds = []
    if features and dist_col:
        x_vals = [f["x"] for f in features]
        orient_vals = [f.get("orientation_hours", 6.0) for f in features]
        scatter_data = {
            "x_column": dist_col,
            "x_values": x_vals,
            "y_data": {"depth": [f["y"] for f in features], "metal_loss": [f["y"] for f in features]},
            "orientation_hours": orient_vals,
        }
        gwd_sorted = sorted(
            [f for f in features if "girth" in (f.get("feature_type") or "").lower() or "gwd" in (f.get("feature_type") or "").lower()],
            key=lambda x: x["x"],
        )
        for f in gwd_sorted:
            lbl = f"GWD {f['gwd_number']}" if f.get("gwd_number") is not None else ""
            girth_welds.append({"chainage": f["x"], "gwd_number": f.get("gwd_number"), "label": lbl, "source": f.get("source", "")})
        idx_next = {gwd_sorted[i]["x"]: gwd_sorted[i + 1]["x"] for i in range(len(gwd_sorted) - 1)}
        for f in gwd_sorted:
            if f.get("seam_orient_hours") is not None:
                end = idx_next.get(f["x"])
                seam_welds.append({
                    "chainage_start": f["x"],
                    "chainage_end": end,
                    "orientation_hours": f["seam_orient_hours"],
                    "orientation_label": _format_orientation_hours(f["seam_orient_hours"]),
                    "source": f.get("source", ""),
                })
        for f in features:
            ft = (f.get("feature_type") or "").lower()
            if "seam" in ft and "girth" not in ft and "gwd" not in ft:
                seam_welds.append({
                    "chainage_start": None,
                    "chainage_end": None,
                    "orientation_hours": f.get("orientation_hours", 6.0),
                    "orientation_label": _format_orientation_hours(f.get("orientation_hours", 6.0)),
                    "source": f.get("source", ""),
                })
        if scatter_data:
            scatter_data["girth_welds"] = girth_welds
            scatter_data["seam_welds"] = seam_welds

    sources = sorted({str(f.get("source", "")).strip() for f in features if f.get("source")})
    return features, scatter_data, sources


def _apply_gwd_filter(
    features: List[Dict],
    scatter_data: Optional[Dict],
    gwd_start: Optional[int],
    gwd_end: Optional[int],
    gwd_center: Optional[int],
) -> tuple:
    """
    Filter features by GWD range. Returns (filtered_features, filtered_scatter_data).
    - gwd_start, gwd_end: chainage between start and end GWD
    - gwd_center: ±3 adjacent GWDs (by sorted GWD list order)
    """
    if not scatter_data or not scatter_data.get("girth_welds"):
        return features, scatter_data

    def _gwd_match(a, b):
        try:
            return int(a) == int(b)
        except (TypeError, ValueError):
            return a == b

    girth_welds = scatter_data["girth_welds"]
    gwd_list = [(gw.get("gwd_number"), gw.get("chainage")) for gw in girth_welds if gw.get("gwd_number") is not None and gw.get("chainage") is not None]
    gwd_list.sort(key=lambda x: (x[1], str(x[0])))  # by chainage, then gwd_number

    chainage_min, chainage_max = None, None

    if gwd_center is not None:
        idx = next((i for i, (gn, _) in enumerate(gwd_list) if _gwd_match(gn, gwd_center)), None)
        if idx is not None:
            lo = max(0, idx - 3)
            hi = min(len(gwd_list) - 1, idx + 3)
            chainage_min = gwd_list[lo][1]
            chainage_max = gwd_list[hi][1]
    elif gwd_start is not None or gwd_end is not None:
        start_chainage = next((ch for gn, ch in gwd_list if _gwd_match(gn, gwd_start)), None) if gwd_start is not None else None
        end_chainage = next((ch for gn, ch in gwd_list if _gwd_match(gn, gwd_end)), None) if gwd_end is not None else None
        if start_chainage is not None:
            chainage_min = start_chainage
        if end_chainage is not None:
            chainage_max = end_chainage
        if chainage_min is None and chainage_max is not None:
            chainage_min = min(ch for _, ch in gwd_list)
        if chainage_max is None and chainage_min is not None:
            chainage_max = max(ch for _, ch in gwd_list)

    if chainage_min is None and chainage_max is None:
        return features, scatter_data

    filtered = [f for f in features if (chainage_min is None or f["x"] >= chainage_min) and (chainage_max is None or f["x"] <= chainage_max)]
    new_scatter = {
        "x_column": scatter_data["x_column"],
        "x_values": [f["x"] for f in filtered],
        "y_data": {"depth": [f["y"] for f in filtered], "metal_loss": [f["y"] for f in filtered]},
        "orientation_hours": [f.get("orientation_hours", 6.0) for f in filtered],
    }
    new_girth = [gw for gw in scatter_data.get("girth_welds", []) if (chainage_min is None or gw.get("chainage", 0) >= chainage_min) and (chainage_max is None or gw.get("chainage", float("inf")) <= chainage_max)]
    new_seam = [
        sw for sw in scatter_data.get("seam_welds", [])
        if sw.get("chainage_start") is None
        or ((chainage_min is None or sw.get("chainage_start", 0) >= chainage_min) and (chainage_max is None or sw.get("chainage_end", float("inf")) <= chainage_max))
    ]
    new_scatter["girth_welds"] = new_girth
    new_scatter["seam_welds"] = new_seam
    return filtered, new_scatter


def _parse_orientation_to_degrees(val) -> Optional[float]:
    """Parse orientation (clock '2:48' or degrees) to degrees from 12 o'clock."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            h = float(parts[0])
            m = float(parts[1]) if len(parts) > 1 else 0
            clock_pos = h + m / 60.0
            return (clock_pos / 12.0) * 360.0
        except (ValueError, IndexError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _format_orientation_hours(hours: float) -> str:
    """Format hours (e.g. 8.37) as hh:mm for display."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h:02d}:{m:02d}"


def _parse_orientation_to_hours(val) -> Optional[float]:
    """Parse orientation (clock '2:48' or '08:22') to hours 0-12 for Y-axis."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            h = float(parts[0])
            m = float(parts[1]) if len(parts) > 1 else 0
            return h + m / 60.0
        except (ValueError, IndexError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


@app.post("/api/ili/parse-paste", response_model=FeatureMapResponse)
async def parse_pasted_ili(pasted_text: str = Form(...)):
    """
    Parse pasted tabular ILI data (e.g. from Excel copy) and return features for
    interactive visualization. Uses ili_reader to auto-detect columns.
    Returns same structure as /api/ili/process (stats, histograms, scatter_data).
    """
    log_params(logger, "ili/parse-paste", {"text_length": len(pasted_text)})
    pasted_text = (pasted_text or "").strip()
    if not pasted_text:
        return FeatureMapResponse(success=False, error="No pasted data provided")

    try:
        df = parse_pasted_ili_text(pasted_text)
        if df.empty or len(df) == 0:
            return FeatureMapResponse(success=False, error="Could not parse pasted data into a table")

        ili_cols = identify_ili_columns(df)
        dist_col = ili_cols.get("distance")
        if not dist_col:
            return FeatureMapResponse(
                success=False,
                error="No distance/chainage column detected. Ensure your data has a column like 'ILI Chainage (m)' or 'Distance'.",
            )

        features, scatter_data, sources = _build_feature_map_from_df(df, ili_cols)

        gwd_numbers = sorted({int(f["gwd_number"]) for f in features if isinstance(f.get("gwd_number"), (int, float))})
        logger.info(f"[ili/parse-paste] Parsed {len(features)} features")
        return FeatureMapResponse(
            success=True,
            total_rows=len(features),
            column_mapping={k: v for k, v in ili_cols.items() if v},
            features=features,
            scatter_data=scatter_data,
            sources=sources,
            gwd_numbers=gwd_numbers,
        )
    except Exception as e:
        log_error(logger, "ili/parse-paste", e)
        return FeatureMapResponse(success=False, error=str(e))


@app.post("/api/ili/process-feature-map", response_model=FeatureMapResponse)
async def process_ili_feature_map(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    gwd_start: Optional[int] = Form(None),
    gwd_end: Optional[int] = Form(None),
    gwd_center: Optional[int] = Form(None),
):
    """
    Process ILI Excel file and return features for unwrapped pipe visualization.
    Uses auto-identified columns (no manual column selection).
    Optional GWD filter: gwd_start+gwd_end for range, or gwd_center for ±3 adjacent GWDs.
    """
    log_params(logger, "ili/process-feature-map", {
        "filename": file.filename,
        "sheet_name": sheet_name,
        "gwd_start": gwd_start,
        "gwd_end": gwd_end,
        "gwd_center": gwd_center,
    })
    validate_excel_file(file)
    temp_path = save_temp_file(file)

    try:
        df = pd.read_excel(temp_path, sheet_name=sheet_name)
        if df.empty:
            return FeatureMapResponse(success=False, error="Sheet is empty")

        ili_cols = identify_ili_columns(df)
        dist_col = ili_cols.get("distance")
        if not dist_col:
            return FeatureMapResponse(
                success=False,
                error="No distance/chainage column detected. Ensure your data has a column like 'ILI Chainage (m)' or 'Distance'.",
            )

        features, scatter_data, sources = _build_feature_map_from_df(df, ili_cols)
        gwd_numbers = sorted({int(f["gwd_number"]) for f in features if isinstance(f.get("gwd_number"), (int, float))})

        # Apply GWD filter if requested
        if gwd_start is not None or gwd_end is not None or gwd_center is not None:
            features, scatter_data = _apply_gwd_filter(
                features, scatter_data, gwd_start, gwd_end, gwd_center
            )

        logger.info(f"[ili/process-feature-map] Processed {len(features)} features from sheet '{sheet_name}'")
        return FeatureMapResponse(
            success=True,
            total_rows=len(features),
            column_mapping={k: v for k, v in ili_cols.items() if v},
            features=features,
            scatter_data=scatter_data,
            sources=sources,
            gwd_numbers=gwd_numbers,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "ili/process-feature-map", e)
        return FeatureMapResponse(success=False, error=f"{type(e).__name__}: {str(e)}")
    finally:
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


@app.post("/api/tml/deactivate-cml", response_model=DeactivateCMLResponse)
async def deactivate_cml(
    source_file: UploadFile = File(...),
    template_file: Optional[UploadFile] = File(default=None),
):
    """
    De-active CML: Generate a dataloader that deactivates all CMLs in the uploaded source sheet.
    
    - Source file: Required. Must have sheet "Source_Data" with Equipment ID, CML Group ID, sub-CML ID.
    - Template file: Optional. If not provided, uses default TM_Loader_Template.xlsx from system.
    
    Output: {source_filename}_deactive.xlsx with Status Indicator = "Inactive" for all CMLs.
    """
    tpl_name = (template_file.filename if template_file and template_file.filename else "default")
    logger.info(f"[tml/deactivate-cml] Request received: source={source_file.filename}, template={tpl_name}")
    log_params(logger, "tml/deactivate-cml", {"source_filename": source_file.filename})
    validate_excel_file(source_file)
    
    temp_dir = tempfile.mkdtemp()
    temp_source = None
    temp_template = None
    
    try:
        temp_source = save_temp_file(source_file)
        
        # Use uploaded template or default
        template_dir = Path(__file__).parent / "static" / "templates" / "tml"
        default_template = template_dir / "TM_Loader_Template.xlsx"
        
        if template_file is not None and template_file.filename:
            validate_excel_file(template_file)
            temp_template = save_temp_file(template_file)
        elif default_template.exists():
            temp_template = default_template
        else:
            raise HTTPException(
                status_code=400,
                detail="No template file provided and default TM_Loader_Template.xlsx not found in backend/static/templates/tml/"
            )
        
        # Output: {upload_filename}_deactive.xlsx
        source_stem = Path(source_file.filename).stem
        output_filename = f"{source_stem}_deactive.xlsx"
        output_path = Path(temp_dir) / output_filename
        
        records_count, result_path, sheet_used = process_deactivate_cml(
            source_path=str(temp_source),
            template_path=str(temp_template),
            output_path=str(output_path),
        )
        
        if records_count == 0 or result_path is None:
            raise HTTPException(
                status_code=400,
                detail="No records to process. Ensure source file has a sheet with Equipment ID, CML Group ID, sub-CML ID columns (or their aliases)."
            )
        
        # Store for download
        download_token = str(uuid.uuid4())
        TML_FILE_STORAGE[download_token] = str(result_path)
        
        logger.info(
            f"[tml/deactivate-cml] Deactivated {records_count} CMLs, sheet='{sheet_used}', output={output_filename}"
        )
        
        return DeactivateCMLResponse(
            success=True,
            message=f"Successfully deactivated {records_count} CML(s)",
            download_token=download_token,
            records_count=records_count,
            output_filename=output_filename,
            sheet_used=sheet_used,
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"[tml/deactivate-cml] ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.warning(f"[tml/deactivate-cml] FileNotFoundError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error(logger, "tml/deactivate-cml", e)
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[tml/deactivate-cml] Traceback: {tb}")
        raise HTTPException(
            status_code=500,
            detail=f"Error: {type(e).__name__}: {str(e)}. Check server logs for full traceback."
        )
    finally:
        if temp_source and os.path.exists(temp_source):
            try:
                os.unlink(temp_source)
            except OSError:
                pass


@app.post("/api/tml/inspection-report/read", response_model=InspectionReportResponse)
async def read_inspection_reports(
    pdf_files: List[UploadFile] = File(..., description="UT inspection report PDFs"),
):
    """
    Read and summarize UT inspection report PDFs. No source Excel or dataloader.
    Returns extracted Circuit, CML, Min Reading, Date for user verification.
    """
    logger.info(f"[inspection-report/read] Request received, pdf_count={len(pdf_files)}")
    log_params(logger, "tml/inspection-report/read", {"pdf_count": len(pdf_files)})
    for pf in pdf_files:
        validate_pdf_file(pf)

    temp_pdfs: List[Path] = []
    try:
        for pf in pdf_files:
            temp_pdfs.append(save_temp_file(pf))

        from backend.tml.inspection_report_parser import parse_inspection_report_pdfs
        from backend.tml.inspection_dataloader import generate_measurements_dataloader

        readings = parse_inspection_report_pdfs(temp_pdfs, [f.filename for f in pdf_files])
        if not readings:
            return InspectionReportResponse(
                success=False,
                message="No data extracted from PDFs. Check report format or try OCR.",
                error="No Circuit, CML, or readings found in uploaded PDFs.",
            )

        # Summary only - no file output, use placeholder for Equipment ID in summary
        records_count, summary = generate_measurements_dataloader(
            readings,
            circuit_to_equipment={},
            output_path="",
            use_placeholder_when_missing=True,
        )

        logger.info(f"[tml/inspection-report/read] Read {len(pdf_files)} PDFs, {len(summary)} CML(s)")

        return InspectionReportResponse(
            success=True,
            message=f"Read {len(pdf_files)} PDF(s), extracted **{len(summary)}** CML(s). Use Generate Dataloader to create Excel.",
            records_count=records_count,
            summary=summary,
        )
    except Exception as e:
        log_error(logger, "tml/inspection-report/read", e)
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[inspection-report/read] Traceback: {tb}")
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}. Check backend logs for full traceback.",
        )
    finally:
        for p in temp_pdfs:
            if p.exists():
                try:
                    os.unlink(p)
                except OSError:
                    pass


@app.post("/api/tml/inspection-report", response_model=InspectionReportResponse)
async def process_inspection_reports(
    pdf_files: List[UploadFile] = File(..., description="UT inspection report PDFs"),
    source_file: Optional[UploadFile] = File(default=None, description="Optional: Excel with Circuit ID and Equipment ID"),
    template_file: Optional[UploadFile] = File(default=None),
):
    """
    Parse PDFs and generate APM Measurements dataloader. Source Excel optional;
    when missing, Equipment ID = "Need Add Equipment ID" (incomplete dataloader).
    """
    log_params(logger, "tml/inspection-report", {
        "source_filename": source_file.filename if source_file else None,
        "pdf_count": len(pdf_files),
    })
    for pf in pdf_files:
        validate_pdf_file(pf)
    if source_file:
        validate_excel_file(source_file)

    temp_dir = tempfile.mkdtemp()
    temp_source = None
    temp_pdfs: List[Path] = []
    template_path = None

    try:
        if source_file:
            temp_source = save_temp_file(source_file)
        for pf in pdf_files:
            temp_pdfs.append(save_temp_file(pf))
        if template_file and template_file.filename:
            validate_excel_file(template_file)
            template_path = str(save_temp_file(template_file))

        from backend.tml.inspection_report_parser import parse_inspection_report_pdfs
        from backend.tml.inspection_dataloader import build_circuit_to_equipment_map, generate_measurements_dataloader

        readings = parse_inspection_report_pdfs(temp_pdfs, [f.filename for f in pdf_files])
        if not readings:
            return InspectionReportResponse(
                success=False,
                message="No data extracted from PDFs. Check report format or try OCR.",
                error="No Circuit, CML, or readings found in uploaded PDFs.",
            )

        circuit_to_equipment = {}
        if temp_source:
            circuit_to_equipment = build_circuit_to_equipment_map(str(temp_source))

        output_path = Path(temp_dir) / "Inspection_Report_Dataloader.xlsx"
        records_count, summary = generate_measurements_dataloader(
            readings,
            circuit_to_equipment,
            str(output_path),
            template_path=template_path,
            use_placeholder_when_missing=True,
        )

        if records_count == 0:
            return InspectionReportResponse(
                success=True,
                message="No records to write.",
                summary=summary,
                records_count=0,
            )

        download_token = str(uuid.uuid4())
        TML_FILE_STORAGE[download_token] = str(output_path)

        has_placeholder = any(s.get("Equipment ID") == "Need Add Equipment ID" for s in summary)
        msg = f"Processed {len(pdf_files)} PDF(s), {records_count} record(s)."
        if has_placeholder:
            msg += " Some Equipment IDs are placeholders—edit in Excel before upload to APM."

        logger.info(f"[tml/inspection-report] Processed {len(pdf_files)} PDFs, {records_count} records")

        return InspectionReportResponse(
            success=True,
            message=msg,
            download_token=download_token,
            output_filename="Inspection_Report_Dataloader.xlsx",
            records_count=records_count,
            summary=summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log_error(logger, "tml/inspection-report", e)
        import traceback
        logger.error(f"[inspection-report] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}. Check backend logs for full traceback.",
        )
    finally:
        if temp_source and os.path.exists(temp_source):
            try:
                os.unlink(temp_source)
            except OSError:
                pass
        for p in temp_pdfs:
            if p.exists():
                try:
                    os.unlink(p)
                except OSError:
                    pass


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
        logger.warning(f"[tml/download] Token not found: {file_token[:8]}... (storage has {len(TML_FILE_STORAGE)} entries)")
        raise HTTPException(
            status_code=404,
            detail=f"File not found. Token invalid or expired. (Debug: token prefix={file_token[:8]}..., storage size={len(TML_FILE_STORAGE)})"
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