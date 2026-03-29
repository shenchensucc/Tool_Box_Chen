"""
Inspection Report to APM Dataloader

Maps extracted PDF data (Circuit, CML, readings, date) to Equipment ID using source Excel,
and generates APM TM Data Loader compatible Excel (Measurements sheet).
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook

from .excel_reader import _find_canonical_column
from .inspection_report_parser import ExtractedReading


# Source Excel: Circuit ID -> Equipment ID mapping
# Column aliases for source file
CIRCUIT_ALIASES = ["Circuit ID", "Circuit", "Circuit #", "CircuitID", "Circuit Number"]
EQUIPMENT_ALIASES = ["Equipment ID", "Equipment", "Equip ID", "EquipmentID"]


def _normalize_circuit(s: str) -> str:
    """Normalize circuit ID for matching (strip, collapse spaces)."""
    return " ".join(str(s).strip().split()) if pd.notna(s) else ""


def build_circuit_to_equipment_map(source_path: str, sheet_name: str = "Source_Data") -> Dict[str, str]:
    """
    Read source Excel and build Circuit ID -> Equipment ID mapping.

    Args:
        source_path: Path to source Excel
        sheet_name: Sheet containing the mapping

    Returns:
        Dict mapping circuit_id -> equipment_id
    """
    df = pd.read_excel(source_path, sheet_name=sheet_name, dtype=str)
    circuit_col = _find_canonical_column(df.columns.tolist(), "Circuit ID") or next(
        (c for c in df.columns if any(a.lower() in str(c).lower() for a in ["circuit"])), None
    )
    equip_col = _find_canonical_column(df.columns.tolist(), "Equipment ID") or next(
        (c for c in df.columns if any(a.lower() in str(c).lower() for a in ["equipment", "equip"])), None
    )

    if not circuit_col or not equip_col:
        raise ValueError(
            f"Source file must have Circuit ID and Equipment ID columns. Found: {df.columns.tolist()}"
        )

    mapping = {}
    for _, row in df.iterrows():
        circ = _normalize_circuit(row.get(circuit_col, ""))
        equip = str(row.get(equip_col, "")).strip()
        if circ and equip:
            mapping[circ] = equip
    return mapping


PLACEHOLDER_EQUIPMENT_ID = "Need Add Equipment ID"


def generate_measurements_dataloader(
    readings: List[ExtractedReading],
    circuit_to_equipment: Optional[Dict[str, str]] = None,
    output_path: str = "",
    template_path: Optional[str] = None,
    cmms_system: str = "P1R-100",
    use_placeholder_when_missing: bool = True,
) -> Tuple[int, List[Dict]]:
    """
    Generate APM Measurements dataloader Excel from extracted readings.

    Args:
        readings: List of ExtractedReading from PDFs
        circuit_to_equipment: Circuit ID -> Equipment ID mapping (optional). When None or circuit not found,
            uses PLACEHOLDER_EQUIPMENT_ID if use_placeholder_when_missing else skips the row.
        output_path: Path for output Excel (empty = summary only, no file)
        template_path: Optional TM_Loader template (for structure)
        cmms_system: CMMS System value (default P1R-100)
        use_placeholder_when_missing: When True, use "Need Add Equipment ID" for missing Equipment ID

    Returns:
        (records_count, summary_rows for frontend display)
    """
    summary_rows = []
    rows = []
    circuit_to_equipment = circuit_to_equipment or {}

    for r in readings:
        equip_id = None
        if circuit_to_equipment:
            equip_id = circuit_to_equipment.get(r.circuit_id)
            if not equip_id:
                for circ, eid in circuit_to_equipment.items():
                    if _normalize_circuit(circ) == _normalize_circuit(r.circuit_id):
                        equip_id = eid
                        break
                    if r.circuit_id.startswith(circ) or circ.startswith(r.circuit_id):
                        equip_id = eid
                        break

        if not equip_id:
            if use_placeholder_when_missing:
                equip_id = PLACEHOLDER_EQUIPMENT_ID
                status = "Incomplete - add Equipment ID in Excel"
            else:
                summary_rows.append({
                    "Circuit": r.circuit_id,
                    "CML": r.cml_id,
                    "Min Reading": r.min_reading,
                    "Date": r.measurement_date,
                    "Equipment ID": "(not found in source)",
                    "Status": "Skipped - no Equipment ID",
                })
                continue
        else:
            status = "OK"

        # APM Measurements: Equipment ID, CMMS System, TML Group ID, TML ID, Readings, Measurement Date
        tml_group_id = r.circuit_id
        tml_id = r.cml_id
        measurement_date = r.measurement_date
        if measurement_date and len(measurement_date) == 10:  # YYYY-MM-DD
            measurement_date = f"{measurement_date} 00:00:00"

        rows.append({
            "Equipment ID": equip_id,
            "CMMS System": cmms_system,
            "TML Group ID": tml_group_id,
            "TML ID": tml_id,
            "Readings": str(r.min_reading),
            "Measurement Date": measurement_date or "",
        })

        summary_rows.append({
            "Circuit": r.circuit_id,
            "CML": r.cml_id,
            "Min Reading": r.min_reading,
            "Date": r.measurement_date,
            "Equipment ID": equip_id,
            "Status": status,
        })

    if not rows:
        return 0, summary_rows

    if output_path:
        df = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if template_path and os.path.exists(template_path):
            import shutil
            shutil.copy(template_path, output_path)
            with pd.ExcelWriter(output_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Measurements", index=False)
        else:
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Measurements", index=False)

        wb = load_workbook(output_path)
        if "Measurements" in wb.sheetnames:
            sheet = wb["Measurements"]
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width = 20
        wb.save(output_path)

    return len(rows), summary_rows


def generate_measurements_dataloader_from_rows(
    rows: List[Dict],
    output_path: str = "",
    cmms_system: str = "P1R-100",
) -> Tuple[int, List[Dict]]:
    """
    Generate APM Measurements dataloader from pre-parsed / user-edited table rows.

    Each row should have: Circuit, CML, Min Reading, Date, Equipment ID.
    Rows missing Circuit or CML are skipped.
    """
    dl_rows: List[Dict] = []
    summary_rows: List[Dict] = []

    for row in rows:
        circuit = str(row.get("Circuit") or "").strip()
        cml = str(row.get("CML") or "").strip()
        if not circuit or not cml:
            continue

        min_reading = row.get("Min Reading")
        if min_reading is None:
            min_reading = ""
        date_val = str(row.get("Date") or "").strip()
        equip_id = str(row.get("Equipment ID") or "").strip() or PLACEHOLDER_EQUIPMENT_ID

        measurement_date = date_val
        if measurement_date and len(measurement_date) == 10:
            measurement_date = f"{measurement_date} 00:00:00"

        dl_rows.append({
            "Equipment ID": equip_id,
            "CMMS System": cmms_system,
            "TML Group ID": circuit,
            "TML ID": cml,
            "Readings": str(min_reading),
            "Measurement Date": measurement_date or "",
        })
        status = "OK" if equip_id != PLACEHOLDER_EQUIPMENT_ID else "Incomplete - add Equipment ID in Excel"
        summary_rows.append({
            "Circuit": circuit,
            "CML": cml,
            "Min Reading": min_reading,
            "Date": date_val,
            "Equipment ID": equip_id,
            "Status": status,
        })

    if not dl_rows:
        return 0, summary_rows

    if output_path:
        df = pd.DataFrame(dl_rows)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Measurements", index=False)
        wb = load_workbook(output_path)
        if "Measurements" in wb.sheetnames:
            sheet = wb["Measurements"]
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width = 20
        wb.save(output_path)

    return len(dl_rows), summary_rows
