from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response"""

    ok: bool = True


class PreviewResponse(BaseModel):
    """Excel file preview response"""

    filename: str
    sheet_names: List[str]
    columns: Dict[str, List[str]]  # sheet_name -> column_names
    row_counts: Dict[str, int]  # sheet_name -> row_count


class ProcessOptions(BaseModel):
    """Options for processing ILI data"""

    sheet_name: str = Field(..., description="Name of the sheet to process")
    distance_column: Optional[str] = Field(None, description="Column name for distance data")
    depth_column: Optional[str] = Field(None, description="Column name for depth data")
    metal_loss_column: Optional[str] = Field(
        None, description="Column name for metal loss data"
    )


class ColumnStats(BaseModel):
    """Statistics for a numeric column"""

    count: int
    mean: float
    std: float
    min: float
    max: float
    q25: float
    q50: float
    q75: float


class HistogramData(BaseModel):
    """Histogram data for plotting"""

    column_name: str
    values: List[float]
    bin_edges: List[float]
    counts: List[int]


class ProcessResponse(BaseModel):
    """Response from processing ILI data"""

    filename: str
    sheet_name: str
    total_rows: int
    stats: Dict[str, ColumnStats]  # column_name -> stats
    histograms: List[HistogramData]
    scatter_data: Optional[Dict[str, Any]] = None  # x/y data for distance plots


class TMLProcessResponse(BaseModel):
    """Response from processing TML data"""

    success: bool
    message: str
    zip_token: str = Field(..., description="Token to download ZIP file with separate outputs")
    combined_token: str = Field(..., description="Token to download combined Excel file")
    workflows_processed: int
    workflow_summary: Dict[int, int] = Field(..., description="Workflow ID -> records count mapping")
    timestamp: str


class ChatMessage(BaseModel):
    """Chat message for /api/chat"""

    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    """Request body for /api/chat"""

    messages: List[ChatMessage]
    model: str = "grok-4-fast"
    tools: Optional[List[Dict[str, Any]]] = None  # OpenAI tool definitions
    tool_choice: Optional[str] = None  # "auto" | "none" | {"type": "function", "function": {"name": "..."}}


class ChatResponse(BaseModel):
    """Response from /api/chat"""

    content: str
    model: str
    tool_calls: Optional[List[Dict[str, Any]]] = None