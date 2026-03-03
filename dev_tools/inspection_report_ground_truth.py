"""
Inspection Report Ground Truth Dev Tool

Local development tool for the facility report reading feature. Uses the exact same
parser logic as the app backend. Developers can:
- View extracted readings
- Mark which readings are wrong
- Add correct readings (missing from parser output)
- Export to training/ground-truth dataset for parser improvement

Run: streamlit run dev_tools/inspection_report_ground_truth.py
Or: python -m streamlit run dev_tools/inspection_report_ground_truth.py
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root for backend imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.tml.inspection_report_parser import parse_inspection_report_pdf, ExtractedReading

# Ground truth data directory (relative to project root)
GROUND_TRUTH_DIR = ROOT / "dev_tools" / "ground_truth_data"
GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)


def _extract_pdf_text(pdf_bytes: bytes) -> dict:
    """Extract text from each PDF page for export context."""
    import tempfile
    import pdfplumber

    pages_text = {}
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        with pdfplumber.open(tmp_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages_text[f"page_{i}"] = text[:5000]  # Limit per page
    finally:
        tmp_path.unlink(missing_ok=True)
    return pages_text


def _load_training_summary() -> list[dict]:
    """Load summary of all ground truth files (no PDF parsing)."""
    summary = []
    for p in sorted(GROUND_TRUTH_DIR.glob("*_ground_truth.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            pdf_name = data.get("source_file", p.stem.replace("_ground_truth", "") + ".pdf")
            pdf_path = GROUND_TRUTH_DIR / pdf_name
            has_pdf = pdf_path.exists()
            n_readings = len(data.get("readings", []))
            n_additions = len(data.get("additions", []))
            summary.append({
                "name": p.stem.replace("_ground_truth", ""),
                "pdf_exists": has_pdf,
                "readings": n_readings,
                "additions": n_additions,
            })
        except Exception:
            summary.append({"name": p.stem, "pdf_exists": False, "readings": 0, "additions": 0})
    return summary


def reading_to_row(r: ExtractedReading, row_idx: int) -> dict:
    """Convert ExtractedReading to a flat row for display/edit."""
    return {
        "row_idx": row_idx,
        "circuit_id": r.circuit_id,
        "cml_id": r.cml_id,
        "min_reading": r.min_reading,
        "measurement_date": r.measurement_date,
        "source_file": r.source_file,
        "extraction_method": r.extraction_method,
        "is_correct": True,
        "corrected_reading": None,
        "notes": "",
    }


def row_to_reading(row: dict) -> ExtractedReading:
    """Build ExtractedReading from row (for corrected/added rows)."""
    reading = row.get("corrected_reading")
    if reading is not None and str(reading).strip():
        try:
            min_reading = float(reading)
        except (ValueError, TypeError):
            min_reading = row["min_reading"]
    else:
        min_reading = row["min_reading"]
    return ExtractedReading(
        circuit_id=row["circuit_id"],
        cml_id=row["cml_id"],
        measurement_date=row["measurement_date"] or "",
        min_reading=min_reading,
        all_readings=[min_reading],
        source_file=row.get("source_file", ""),
        extraction_method=row.get("extraction_method", "manual"),
    )


def _json_safe(val):
    """Convert NaN/None for JSON serialization."""
    if val is None or (isinstance(val, float) and math.isnan(val)) or (hasattr(pd, "NA") and val is pd.NA):
        return None
    return val


def _find_reading_context(pdf_text: dict, reading_val: float, cml_id: str, window: int = 80) -> str | None:
    """Find where a reading appears in PDF text and return surrounding context."""
    needle = f"{reading_val:.3f}".rstrip("0").rstrip(".")
    for page_key, text in pdf_text.items():
        idx = text.find(needle)
        if idx >= 0:
            start = max(0, idx - window)
            end = min(len(text), idx + len(needle) + window)
            return f"[{page_key}] ...{text[start:end]}..."
    return None


def export_ground_truth(
    rows: list[dict],
    additions: list[dict],
    source_file: str,
    source_path: str,
    pdf_text: dict | None = None,
) -> dict:
    """Build ground truth JSON for export. Optionally include pdf_text and per-reading context."""
    readings_export = []
    for r in rows:
        corr = _json_safe(r.get("corrected_reading"))
        entry = {
            "circuit_id": r["circuit_id"],
            "cml_id": r["cml_id"],
            "min_reading": r["min_reading"],
            "measurement_date": r["measurement_date"],
            "source_file": r.get("source_file", source_file),
            "extraction_method": r.get("extraction_method", "pdfplumber"),
            "is_correct": r.get("is_correct", True),
            "corrected_reading": corr,
            "notes": r.get("notes", ""),
        }
        if corr is not None:
            try:
                entry["expected_reading"] = float(corr)
            except (ValueError, TypeError):
                pass
        if pdf_text:
            ctx = _find_reading_context(pdf_text, r["min_reading"], r["cml_id"])
            if ctx:
                entry["pdf_text_context"] = ctx
        readings_export.append(entry)

    out = {
        "source_file": source_file,
        "source_path": source_path,
        "extracted_at": datetime.now().isoformat(),
        "readings": readings_export,
        "additions": additions,
        "schema_version": "1.0",
    }
    if pdf_text:
        out["pdf_text"] = pdf_text  # Full page text for debugging
    return out


def main():
    st.set_page_config("Inspection Report Ground Truth", "🔧", layout="wide")  # noqa: F401
    st.title("🔧 Inspection Report Ground Truth Dev Tool")
    st.caption(
        "Local tool for developers. Uses the same parser as the app. Mark wrong readings, add corrections, "
        "and export to training data for parser improvement."
    )

    # --- Training Summary (sidebar) ---
    with st.sidebar:
        st.subheader("📋 Training Set Summary")
        summary = _load_training_summary()
        if summary:
            for s in summary:
                pdf_icon = "✅" if s["pdf_exists"] else "⚠️"
                short = s["name"][:50] + ("…" if len(s["name"]) > 50 else "")
                st.caption(f"{pdf_icon} {short}")
                st.caption(f"   {s['readings']} readings, {s['additions']} additions")
            st.divider()
        else:
            st.info("No ground truth files yet. Save one to get started.")

    # --- PDF input ---
    st.subheader("1. Load PDF")
    col_upload, col_path = st.columns(2)

    with col_upload:
        uploaded = st.file_uploader("Upload PDF", type=["pdf"], key="gt_pdf")

    with col_path:
        fixture_path = st.text_input(
            "Or path to fixture (relative to project root)",
            placeholder="dev_tools/ground_truth_data/52-001G 1-1 2.32 UT-ROBJOS-26-063_02.28.2026.pdf",
            key="gt_path",
        )

    pdf_bytes = None
    source_filename = ""
    source_path = ""

    if uploaded:
        pdf_bytes = uploaded.read()
        source_filename = uploaded.name
        source_path = f"(uploaded) {uploaded.name}"
    elif fixture_path:
        full_path = ROOT / fixture_path.strip()
        if full_path.exists():
            pdf_bytes = full_path.read_bytes()
            source_filename = full_path.name
            source_path = str(full_path)
        else:
            st.warning(f"Path not found: {full_path}")

    if not pdf_bytes:
        st.info("Upload a PDF or enter a fixture path to begin.")
        return

    # --- Parse (cache by filename) ---
    key_prefix = f"gt_{hash(source_filename) % 10**8}"
    cache_key = f"{key_prefix}_parsed_results"
    if cache_key not in st.session_state:
        with st.spinner("Parsing..."):
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = Path(tmp.name)
            try:
                results = parse_inspection_report_pdf(tmp_path, source_filename)
            finally:
                tmp_path.unlink(missing_ok=True)
            st.session_state[cache_key] = results
    results = st.session_state[cache_key]

    st.subheader("2. Review Extracted Readings")
    if not results:
        st.warning("No readings extracted. Parser returned empty. Check PDF format or try OCR fallback.")
        return

    # --- Session state ---
    if f"{key_prefix}_rows" not in st.session_state:
        st.session_state[f"{key_prefix}_rows"] = [reading_to_row(r, i) for i, r in enumerate(results)]
    if f"{key_prefix}_additions" not in st.session_state:
        st.session_state[f"{key_prefix}_additions"] = []

    rows = st.session_state[f"{key_prefix}_rows"]
    additions = st.session_state[f"{key_prefix}_additions"]

    # --- Data table ---
    df = pd.DataFrame(rows)
    display_cols = [
        "circuit_id",
        "cml_id",
        "min_reading",
        "measurement_date",
        "extraction_method",
        "is_correct",
        "corrected_reading",
        "notes",
    ]
    df_display = df[[c for c in display_cols if c in df.columns]].copy()

    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        column_config={
            "circuit_id": st.column_config.TextColumn("Circuit", width="medium"),
            "cml_id": st.column_config.TextColumn("CML", width="medium"),
            "min_reading": st.column_config.NumberColumn("Min Reading", format="%.3f", width="small"),
            "measurement_date": st.column_config.TextColumn("Date", width="small"),
            "extraction_method": st.column_config.TextColumn("Method", width="small"),
            "is_correct": st.column_config.CheckboxColumn("✓ Correct", width="small", help="Uncheck if wrong"),
            "corrected_reading": st.column_config.NumberColumn("Corrected", format="%.3f", width="small"),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
        },
        hide_index=True,
        key=f"{key_prefix}_editor",
    )

    if edited_df is not None and not edited_df.empty and len(edited_df) == len(rows):
        for i, row in enumerate(rows):
            for col in display_cols:
                if col in edited_df.columns:
                    val = edited_df.iloc[i][col]
                    if col == "is_correct":
                        row[col] = bool(val) if pd.notna(val) else True
                    elif pd.notna(val):
                        row[col] = val
                    elif col == "corrected_reading":
                        row[col] = None
        st.session_state[f"{key_prefix}_rows"] = rows

    # --- Additions ---
    st.markdown("**Add missing readings** (parser did not extract these)")
    default_circuit = rows[0]["circuit_id"] if rows else ""
    default_date = rows[0]["measurement_date"] if rows else ""
    if additions:
        additions_df = pd.DataFrame(additions)
    else:
        additions_df = pd.DataFrame([
            {"circuit_id": default_circuit, "cml_id": "", "min_reading": 0.0, "measurement_date": default_date, "notes": "Added manually"}
        ])
    edited_additions = st.data_editor(
        additions_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "circuit_id": st.column_config.TextColumn("Circuit", width="medium", default=default_circuit),
            "cml_id": st.column_config.TextColumn("CML", width="medium", required=True),
            "min_reading": st.column_config.NumberColumn("Min Reading", format="%.3f", width="small", default=0.0),
            "measurement_date": st.column_config.TextColumn("Date", width="small", default=default_date),
            "notes": st.column_config.TextColumn("Notes", width="medium", default="Added manually"),
        },
        hide_index=True,
        key=f"{key_prefix}_additions_editor",
    )

    if edited_additions is not None and not edited_additions.empty:
        new_additions = []
        for _, r in edited_additions.iterrows():
            cml = str(r.get("cml_id", "")).strip()
            reading = r.get("min_reading", 0)
            if cml and (reading is None or (isinstance(reading, (int, float)) and reading > 0)):
                new_additions.append({
                    "circuit_id": str(r.get("circuit_id", default_circuit)).strip() or default_circuit,
                    "cml_id": cml,
                    "min_reading": float(reading) if reading is not None else 0.0,
                    "measurement_date": str(r.get("measurement_date", default_date)).strip() or default_date,
                    "notes": str(r.get("notes", "Added manually")).strip() or "Added manually",
                })
        st.session_state[f"{key_prefix}_additions"] = new_additions

    # --- Export (form to reduce reruns) ---
    st.subheader("3. Export Ground Truth")
    st.caption("All edits are in-memory. Only **Save** writes to disk.")

    include_pdf_text = st.checkbox("Include PDF text in export (for debugging)", value=False, key="incl_pdf_txt")

    pdf_text = None
    if include_pdf_text:
        pdf_text_cache_key = f"{key_prefix}_pdf_text"
        if pdf_text_cache_key not in st.session_state:
            with st.spinner("Extracting PDF text..."):
                st.session_state[pdf_text_cache_key] = _extract_pdf_text(pdf_bytes)
        pdf_text = st.session_state[pdf_text_cache_key]
    export_data = export_ground_truth(
        st.session_state[f"{key_prefix}_rows"],
        st.session_state[f"{key_prefix}_additions"],
        source_filename,
        source_path,
        pdf_text=pdf_text,
    )
    json_str = json.dumps(export_data, indent=2)
    out_name = Path(source_filename).stem + "_ground_truth.json"

    col_save, col_dl = st.columns(2)
    with col_save:
        if st.button("💾 Save to dev_tools/ground_truth_data/", key="btn_save"):
            json_path = GROUND_TRUTH_DIR / out_name
            pdf_path = GROUND_TRUTH_DIR / source_filename
            json_path.write_text(json_str, encoding="utf-8")
            pdf_path.write_bytes(pdf_bytes)
            st.success(f"Saved {out_name} + PDF")
    with col_dl:
        st.download_button(
            "📥 Download JSON",
            data=json_str,
            file_name=out_name,
            mime="application/json",
            key="dl_gt",
        )

    st.divider()
    st.caption("Inspection Report Ground Truth Dev Tool | Not part of production app")


if __name__ == "__main__":
    main()
