"""System / user prompts for New CML Helper LLM."""

from backend.tml.new_cml_helper.workflow_manifest import workflow_manifest_text

PLAN_JSON_INSTRUCTIONS = """
Return a single JSON object with these keys (no markdown fences):
- summary: string, one short paragraph for the engineer
- primary_file_name: exact filename from the upload list that has the main TML row data
- primary_sheet_name: sheet name to use (use "CSV" for csv files)
- column_mapping: object mapping EXACT source column header string -> canonical column name
- recommended_workflows: array of integers 1-20 to run in TML Data Loader
- constants_suggested: canonical column -> string value to apply to EVERY row when that column is missing (e.g. {"AER_Status_CML":"Yes"})
- missing_canonical_columns: list of canonical names still unknown after mapping
- questions: array of {id, prompt, field_key?} for values you cannot infer; use stable ids like q_equip_prefix
- warnings: strings (e.g. global Yes filter on AER_Status_CML)

Canonical identity columns (must appear in output data, via mapping OR constant): Equipment ID, CML Group ID, sub-CML ID, AER_Status_CML.
Backend will DROP any row where AER_Status_CML does not contain substring "Yes" before workflows run.

Workflow reference:
"""

def build_system_prompt() -> str:
    return (
        "You assist with Chen's Engineer Toolbox TML Data Loader (new CML / batch updates).\n"
        "You NEVER fabricate numeric measurements; only map user columns and recommend workflows.\n\n"
        + PLAN_JSON_INSTRUCTIONS
        + workflow_manifest_text()
    )
