"""Apply mappings and constants to produce Source_Data dataframe."""

from __future__ import annotations

import io
from typing import Dict, List

import pandas as pd

from backend.tml.new_cml_helper.schema import AssembleSpec, AssistantPlan
from backend.tml.new_cml_helper.workflow_manifest import extra_columns_for_workflows

SPINE_COLUMNS = ["Equipment ID", "CML Group ID", "sub-CML ID", "AER_Status_CML"]


def load_primary_sheet(uploads: Dict[str, bytes], spec: AssembleSpec) -> pd.DataFrame:
    if spec.primary_file_name not in uploads:
        raise ValueError(f"File not found in upload set: {spec.primary_file_name}")

    raw = uploads[spec.primary_file_name]
    lower = spec.primary_file_name.lower()

    if lower.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding_errors="replace")
        return df

    xl = pd.ExcelFile(io.BytesIO(raw))
    if spec.primary_sheet_name not in xl.sheet_names:
        raise ValueError(
            f"Sheet '{spec.primary_sheet_name}' not in {spec.primary_file_name}. "
            f"Available: {xl.sheet_names}"
        )
    return pd.read_excel(xl, sheet_name=spec.primary_sheet_name, dtype=str)


def assemble_source_data(uploads: Dict[str, bytes], spec: AssembleSpec, workflow_ids: List[int]) -> pd.DataFrame:
    df = load_primary_sheet(uploads, spec)

    rename_map = {src: canon for src, canon in spec.column_mapping.items() if src in df.columns}
    df = df.rename(columns=rename_map)

    extras = extra_columns_for_workflows(workflow_ids)
    needed = set(SPINE_COLUMNS) | extras
    constants = dict(spec.constants)

    for col in sorted(needed):
        if col not in df.columns:
            df[col] = constants.get(col, "")

    if "Equipment ID" in df.columns:
        df["Equipment ID"] = df["Equipment ID"].astype(str).replace({"nan": "", "None": ""})

    return df


def spec_from_plan(plan: AssistantPlan) -> AssembleSpec:
    const = dict(plan.constants_suggested)
    return AssembleSpec(
        primary_file_name=plan.primary_file_name,
        primary_sheet_name=plan.primary_sheet_name,
        column_mapping=dict(plan.column_mapping),
        constants=const,
    )


def dataframe_to_source_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Source_Data", index=False)
    buf.seek(0)
    return buf.read()
