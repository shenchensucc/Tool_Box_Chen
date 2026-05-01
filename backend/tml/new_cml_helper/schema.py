"""Pydantic models for New CML Helper API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NewCMLQuestion(BaseModel):
    id: str
    prompt: str
    field_key: Optional[str] = Field(None, description="Canonical column or constant key")


class AssistantPlan(BaseModel):
    summary: str = ""
    primary_file_name: str = ""
    primary_sheet_name: str = ""
    column_mapping: Dict[str, str] = Field(default_factory=dict, description="Source header -> canonical")
    recommended_workflows: List[int] = Field(default_factory=list)
    constants_suggested: Dict[str, str] = Field(
        default_factory=dict,
        description="Canonical column -> default constant if missing in sheet",
    )
    missing_canonical_columns: List[str] = Field(default_factory=list)
    questions: List[NewCMLQuestion] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class NewCMLSheetProfile(BaseModel):
    name: str
    columns: List[str]
    row_count: int
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)


class NewCMLFileProfile(BaseModel):
    filename: str
    file_type: str
    sheets: List[NewCMLSheetProfile] = Field(default_factory=list)
    error: Optional[str] = None


class NewCMLAnalyzeResponse(BaseModel):
    success: bool = True
    message: str = ""
    files: List[NewCMLFileProfile] = Field(default_factory=list)
    plan: AssistantPlan
    model_used: str = ""
    llm_error: Optional[str] = None


class NewCMLRefineRequest(BaseModel):
    plan: AssistantPlan
    answers: Dict[str, str] = Field(default_factory=dict, description="question id or field_key -> value")


class NewCMLRefineResponse(BaseModel):
    success: bool = True
    plan: AssistantPlan
    validation_errors: List[str] = Field(default_factory=list)


class AssembleSpec(BaseModel):
    primary_file_name: str
    primary_sheet_name: str
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    constants: Dict[str, str] = Field(default_factory=dict)
