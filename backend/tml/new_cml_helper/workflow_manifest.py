"""Workflow metadata for New CML Helper (aligned with backend/tml/workflows)."""

WORKFLOW_DEFINITIONS = [
    {"id": 1, "name": "Sub-CML Status (deactivated)", "extra_columns": ["AER_Status_CML"], "filter": "AER_Status_CML contains 'To be de-active'"},
    {"id": 2, "name": "AER Flag", "extra_columns": ["AER_Status_CML"], "filter": "AER_Status_CML contains 'Yes'"},
    {"id": 3, "name": "Code Year T-Min Formula", "extra_columns": ["Code Year (T-Min Formula)"], "filter": "value != 'N/A'"},
    {"id": 4, "name": "Design Code", "extra_columns": ["CorrValue_Design_Code"], "filter": "non-null and != 0"},
    {"id": 5, "name": "Material Specification", "extra_columns": ["CorrValue_Material"], "filter": "non-null and != 0"},
    {"id": 6, "name": "Material Grade", "extra_columns": ["CorrValue_Grade"], "filter": "non-null and != 0"},
    {"id": 7, "name": "Design Temperature", "extra_columns": ["CorrValue_T"], "filter": "non-null and != 0"},
    {"id": 8, "name": "Piping Formula", "extra_columns": ["Piping Formula"], "filter": "value != 'E'"},
    {"id": 9, "name": "Outside Diameter", "extra_columns": ["CorrValue_OD"], "filter": "non-null and != 0"},
    {"id": 10, "name": "NPS", "extra_columns": ["CorrValue_NPS"], "filter": "non-null and != 0"},
    {"id": 11, "name": "Schedule", "extra_columns": ["CorrValue_Schedule"], "filter": "non-null and != 0"},
    {"id": 12, "name": "Design Pressure", "extra_columns": ["CorrValue_P"], "filter": "non-null and != 0"},
    {"id": 13, "name": "Temperature Coefficient", "extra_columns": ["Temperature Coefficient"], "filter": "per workflow"},
    {"id": 14, "name": "Tnom", "extra_columns": ["CorrValue_Tnom"], "filter": "non-null and != 0"},
    {"id": 15, "name": "Tmin", "extra_columns": ["CorrValue_Tmin"], "filter": "non-null and != 0"},
    {"id": 16, "name": "Override Allowable Stress", "extra_columns": ["Override Allowable Stress"], "filter": "per workflow"},
    {"id": 17, "name": "Allowable Stress", "extra_columns": ["AER_SMYS"], "filter": "non-null and != 0"},
    {"id": 18, "name": "Design Factor", "extra_columns": ["Design Factor"], "filter": "per workflow"},
    {"id": 19, "name": "Joint Factor", "extra_columns": ["Joint Factor"], "filter": "per workflow"},
    {"id": 20, "name": "Location Factor", "extra_columns": ["CorrValue_LocFactor"], "filter": "non-null and != 0"},
]


def workflow_manifest_text() -> str:
    lines = []
    for w in WORKFLOW_DEFINITIONS:
        lines.append(
            f"{w['id']:02d}. {w['name']} — requires columns: "
            + ", ".join(["Equipment ID", "CML Group ID", "sub-CML ID"] + w["extra_columns"])
            + f" — row filter: {w['filter']}"
        )
    return "\n".join(lines)


def extra_columns_for_workflows(workflow_ids: list) -> set:
    cols = set()
    for w in WORKFLOW_DEFINITIONS:
        if w["id"] in workflow_ids:
            cols.update(w["extra_columns"])
    return cols


def all_workflow_canonical_columns() -> set:
    cols: set = set()
    for w in WORKFLOW_DEFINITIONS:
        cols.update(w["extra_columns"])
    return cols
