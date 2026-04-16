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


class FeatureMapResponse(BaseModel):
    """Response for pasted ILI data → visualization only (no assessment)"""

    success: bool = True
    total_rows: int = 0
    column_mapping: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Standard key -> actual column name (e.g. distance, depth, feature_id)",
    )
    features: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="One dict per row: x, y, depth, length, width, orientation_deg, hover_text, source",
    )
    scatter_data: Optional[Dict[str, Any]] = None
    sources: List[str] = Field(
        default_factory=list,
        description="Unique ILI source/vendor values in the data (for filtering)",
    )
    gwd_numbers: List[int] = Field(
        default_factory=list,
        description="Sorted GWD numbers in the data (for zoom/filter selection)",
    )
    joint_summary_parsed: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Parsed Joint Summary rows (for dig package verification)",
    )
    feature_summary_raw: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw Feature summary: columns, sheet, header_row, sample rows (for data tracing)",
    )
    error: Optional[str] = None


class TMLProcessResponse(BaseModel):
    """Response from processing TML data"""

    success: bool
    message: str
    zip_token: str = Field(..., description="Token to download ZIP file with separate outputs")
    combined_token: str = Field(..., description="Token to download combined Excel file")
    workflows_processed: int
    workflow_summary: Dict[int, int] = Field(..., description="Workflow ID -> records count mapping")
    timestamp: str


class DeactivateCMLResponse(BaseModel):
    """Response from De-active CML tool"""

    success: bool
    message: str
    download_token: str = Field(..., description="Token to download output file")
    records_count: int = Field(..., description="Number of CMLs deactivated")
    output_filename: str = Field(..., description="Output file name (e.g. source_deactive.xlsx)")
    sheet_used: Optional[str] = Field(None, description="Excel sheet name that was read (for debugging)")


class InspectionReportResponse(BaseModel):
    """Response from Inspection Report Loader tool"""

    success: bool
    message: str
    download_token: Optional[str] = Field(None, description="Token to download dataloader Excel")
    output_filename: str = Field(default="Inspection_Report_Dataloader.xlsx")
    records_count: int = Field(default=0, description="Number of measurement records in dataloader")
    summary: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Summary table: Circuit, CML, Min Reading, Date, Status",
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Warning notes shown below the success message (e.g. unmatched Equipment ID / CML Group ID counts)",
    )
    error: Optional[str] = None


class GenerateFromTableRequest(BaseModel):
    """Request body for /api/tml/inspection-report/generate-from-table"""

    rows: List[Dict[str, Any]]
    cmms_system: str = "P1R-100"


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