"""Summarize ingested workbooks for LLM consumption."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.tml.new_cml_helper.schema import NewCMLFileProfile, NewCMLSheetProfile


MAX_SAMPLE_ROWS = 6
MAX_COLUMNS_LISTED = 60


def build_file_profiles(ingested: Dict[str, Dict[str, Any]]) -> List[NewCMLFileProfile]:
    profiles: List[NewCMLFileProfile] = []
    for filename, payload in ingested.items():
        if payload.get("error") and payload.get("type") == "unsupported":
            profiles.append(
                NewCMLFileProfile(filename=filename, file_type="unsupported", error=payload.get("error"))
            )
            continue
        if payload.get("type") == "error":
            profiles.append(
                NewCMLFileProfile(filename=filename, file_type="error", error=payload.get("error"))
            )
            continue

        sheets_out: List[NewCMLSheetProfile] = []
        sheets = payload.get("sheets") or {}
        for sheet_name, df in sheets.items():
            cols = [str(c) for c in df.columns.tolist()[:MAX_COLUMNS_LISTED]]
            sample = df.head(MAX_SAMPLE_ROWS).fillna("").astype(str).to_dict(orient="records")
            sheets_out.append(
                NewCMLSheetProfile(name=sheet_name, columns=cols, row_count=len(df), sample_rows=sample)
            )

        profiles.append(
            NewCMLFileProfile(filename=filename, file_type=str(payload.get("type")), sheets=sheets_out)
        )
    return profiles


def profiles_to_llm_payload(profiles: List[NewCMLFileProfile]) -> str:
    """Compact JSON-ish description for the model."""
    import json

    blob = []
    for fp in profiles:
        entry: Dict[str, Any] = {"filename": fp.filename, "file_type": fp.file_type}
        if fp.error:
            entry["error"] = fp.error
        else:
            entry["sheets"] = [
                {"name": s.name, "row_count": s.row_count, "columns": s.columns}
                for s in fp.sheets
            ]
            for i, sh in enumerate(fp.sheets):
                entry["sheets"][i]["sample_rows"] = sh.sample_rows[:4]
        blob.append(entry)
    return json.dumps(blob, indent=2)


def infer_default_primary(profiles: List[NewCMLFileProfile]) -> tuple[str, str]:
    """Pick first usable excel/csv file and default sheet."""
    for fp in profiles:
        if fp.error or fp.file_type not in ("excel", "csv"):
            continue
        if not fp.sheets:
            continue
        for s in fp.sheets:
            if s.name == "Source_Data":
                return fp.filename, "Source_Data"
        return fp.filename, fp.sheets[0].name
    return "", ""
