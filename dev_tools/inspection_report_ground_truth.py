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
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root for backend imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env for optional parser env overrides (e.g. OCR tuning)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.tml.inspection_report_parser import parse_inspection_report_pdf, ExtractedReading

# Ground truth data directory (relative to project root)
GROUND_TRUTH_DIR = ROOT / "dev_tools" / "ground_truth_data"
GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _temporary_env(overrides: dict[str, str | None]):
    """Temporarily set or clear environment variables."""
    old_values = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, old_value in old_values.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def _parse_pdf_for_ground_truth(tmp_path: Path, source_filename: str) -> list[ExtractedReading]:
    """Run parser with reproducible Tesseract-first OCR for dev comparison."""
    overrides = {"INSPECTION_REPORT_OCR_ENGINE": "tesseract"}
    with _temporary_env(overrides):
        return parse_inspection_report_pdf(tmp_path, source_filename)


def _results_to_dataframe(results: list[ExtractedReading]) -> pd.DataFrame:
    """Display helper for parser outputs."""
    rows = [reading_to_row(r, i) for i, r in enumerate(results)]
    if not rows:
        return pd.DataFrame(columns=["circuit_id", "cml_id", "min_reading", "measurement_date", "extraction_method"])
    df = pd.DataFrame(rows)
    cols = ["circuit_id", "cml_id", "min_reading", "measurement_date", "extraction_method"]
    return df[cols]


def _extract_pdf_text(pdf_bytes: bytes) -> dict:
    """Extract text from each PDF page for export context."""
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


def _validate_one_gt(gt_path: Path, search_dirs: list[Path]) -> tuple[bool | None, str, int, int]:
    """Validate parser against a single ground truth JSON. Returns (ok, msg, passed, total)."""
    try:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"Bad JSON: {e}", 0, 0

    source_file = gt.get("source_file", "")
    if not source_file:
        return None, "No source_file", 0, 0

    pdf_path = None
    for d in search_dirs:
        p = d / source_file
        if p.exists():
            pdf_path = p
            break
    if not pdf_path:
        return None, "PDF not found", 0, 0

    # Build expected map (is_correct readings + additions)
    expected = {}
    for r in gt.get("readings", []):
        if r.get("is_correct"):
            key = (r["circuit_id"], r["cml_id"])
            expected[key] = r.get("expected_reading") or r["min_reading"]
    for a in gt.get("additions", []):
        key = (a["circuit_id"], a["cml_id"])
        expected[key] = a["min_reading"]
    if not expected:
        return None, "No expected readings", 0, 0

    try:
        results = parse_inspection_report_pdf(pdf_path, source_file)
    except Exception as e:
        return False, f"Parser error: {e}", 0, len(expected)

    got = {(r.circuit_id, r.cml_id): r.min_reading for r in results}
    errors = []
    passed = 0
    for (circ, cml), exp_read in expected.items():
        if (circ, cml) not in got:
            errors.append(f"Missing {cml}")
        elif abs(got[(circ, cml)] - exp_read) > 0.01:
            errors.append(f"{cml}: got {got[(circ, cml)]:.3f} ≠ {exp_read:.3f}")
        else:
            passed += 1

    if errors:
        return False, "; ".join(errors[:3]) + ("…" if len(errors) > 3 else ""), passed, len(expected)
    return True, f"{len(expected)} readings", passed, len(expected)


def _load_training_summary() -> list[dict]:
    """Load summary of all ground truth files (no PDF parsing)."""
    search_dirs = [GROUND_TRUTH_DIR, ROOT / "tests" / "fixtures"]
    summary = []
    for p in sorted(GROUND_TRUTH_DIR.glob("*_ground_truth.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            pdf_name = data.get("source_file", p.stem.replace("_ground_truth", "") + ".pdf")
            pdf_path = None
            for d in search_dirs:
                candidate = d / pdf_name
                if candidate.exists():
                    pdf_path = candidate
                    break
            has_pdf = pdf_path is not None
            n_readings = len(data.get("readings", []))
            n_additions = len(data.get("additions", []))
            summary.append({
                "name": p.stem.replace("_ground_truth", ""),
                "gt_path": p,
                "pdf_exists": has_pdf,
                "readings": n_readings,
                "additions": n_additions,
            })
        except Exception:
            summary.append({"name": p.stem, "gt_path": p, "pdf_exists": False, "readings": 0, "additions": 0})
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


def _render_pdf_pages(pdf_bytes: bytes) -> list[bytes]:
    """Render each PDF page to a PNG image using pymupdf."""
    try:
        import pymupdf
        import io
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            images.append(pix.tobytes(output="png"))
        doc.close()
        return images
    except Exception:
        return []


def _inline_validate(pdf_bytes: bytes, source_filename: str, rows: list[dict], additions: list[dict]) -> tuple[bool, str, int, int]:
    """Validate current parser output against the annotated ground truth in session state."""
    # Build expected from current annotations
    expected = {}
    for r in rows:
        if r.get("is_correct", True):
            key = (r["circuit_id"], r["cml_id"])
            corr = r.get("corrected_reading")
            try:
                expected[key] = float(corr) if corr is not None else r["min_reading"]
            except (TypeError, ValueError):
                expected[key] = r["min_reading"]
    for a in additions:
        cml = a.get("cml_id", "").strip()
        circ = a.get("circuit_id", "").strip()
        if cml and circ:
            try:
                expected[(circ, cml)] = float(a["min_reading"])
            except (TypeError, ValueError):
                pass

    if not expected:
        return None, "No expected readings defined", 0, 0

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        results = parse_inspection_report_pdf(tmp_path, source_filename)
    except Exception as e:
        return False, f"Parser error: {e}", 0, len(expected)
    finally:
        tmp_path.unlink(missing_ok=True)

    got = {(r.circuit_id, r.cml_id): r.min_reading for r in results}
    errors, passed = [], 0
    for (circ, cml), exp_read in expected.items():
        if (circ, cml) not in got:
            errors.append(f"Missing {cml}")
        elif abs(got[(circ, cml)] - exp_read) > 0.01:
            errors.append(f"{cml}: got {got[(circ, cml)]:.3f} ≠ {exp_read:.3f}")
        else:
            passed += 1

    if errors:
        return False, "; ".join(errors[:5]) + ("…" if len(errors) > 5 else ""), passed, len(expected)
    return True, f"All {len(expected)} readings correct", passed, len(expected)


def main():
    st.set_page_config("Inspection Report Ground Truth", "🔧", layout="wide")  # noqa: F401
    st.title("🔧 Inspection Report Ground Truth Dev Tool")
    st.caption(
        "Local tool for developers. Uses the same parser as the app. Mark wrong readings, add corrections, "
        "and export to training data for parser improvement."
    )

    search_dirs = [GROUND_TRUTH_DIR, ROOT / "tests" / "fixtures"]

    # --- Sidebar: Training Summary with live validation ---
    with st.sidebar:
        st.subheader("📋 Training Set")
        summary = _load_training_summary()

        run_validate = st.button("▶ Run All Validations", key="run_all_validate", use_container_width=True)

        if summary:
            # Store validation results in session state so they persist across reruns
            if "sidebar_validate_results" not in st.session_state:
                st.session_state.sidebar_validate_results = {}

            if run_validate:
                with st.spinner("Validating all ground truth files…"):
                    for s in summary:
                        if s["pdf_exists"]:
                            ok, msg, passed, total = _validate_one_gt(s["gt_path"], search_dirs)
                            st.session_state.sidebar_validate_results[s["name"]] = (ok, msg, passed, total)
                        else:
                            st.session_state.sidebar_validate_results[s["name"]] = (None, "no PDF", 0, 0)

            vr = st.session_state.sidebar_validate_results
            total_pass = sum(1 for v in vr.values() if v[0] is True)
            total_fail = sum(1 for v in vr.values() if v[0] is False)
            if vr:
                st.caption(f"**{total_pass} ✅ / {total_fail} ❌** of {len(vr)} validated")

            for s in summary:
                v = vr.get(s["name"])
                if v:
                    ok, msg, passed, total = v
                    if ok is True:
                        icon = "✅"
                        detail = f"{passed}/{total}"
                    elif ok is False:
                        icon = "❌"
                        detail = f"{passed}/{total} — {msg}"
                    else:
                        icon = "⚠️" if not s["pdf_exists"] else "—"
                        detail = msg
                else:
                    icon = "✅" if s["pdf_exists"] else "⚠️"
                    detail = f"{s['readings']}r {s['additions']}a"

                short = s["name"][:38] + ("…" if len(s["name"]) > 38 else "")
                st.caption(f"{icon} {short}")
                st.caption(f"   {detail}")
        else:
            st.info("No ground truth files yet.")

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

    # --- Parse (cache by filename; Reparse button clears cache) ---
    key_prefix = f"gt_{hash(source_filename) % 10**8}"
    parse_cache_key = f"{key_prefix}_parsed_results"
    pdf_text_cache_key = f"{key_prefix}_pdf_text"
    pages_cache_key = f"{key_prefix}_pages"

    col_parse_info, col_reparse = st.columns([4, 1])
    with col_reparse:
        if st.button("🔄 Reparse", key=f"{key_prefix}_reparse", help="Clear cache and re-run the parser"):
            for k in [parse_cache_key, pdf_text_cache_key, pages_cache_key,
                      f"{key_prefix}_rows", f"{key_prefix}_additions"]:
                st.session_state.pop(k, None)
            st.rerun()

    if parse_cache_key not in st.session_state:
        with st.spinner("Parsing PDF…"):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = Path(tmp.name)
            try:
                parsed_results = _parse_pdf_for_ground_truth(tmp_path, source_filename)
            finally:
                tmp_path.unlink(missing_ok=True)
            st.session_state[parse_cache_key] = parsed_results
        with st.spinner("Extracting PDF text…"):
            st.session_state[pdf_text_cache_key] = _extract_pdf_text(pdf_bytes)
        with st.spinner("Rendering PDF pages…"):
            st.session_state[pages_cache_key] = _render_pdf_pages(pdf_bytes)

    with col_parse_info:
        st.caption(f"Loaded: **{source_filename}**")

    results = st.session_state[parse_cache_key]
    pdf_text = st.session_state[pdf_text_cache_key]
    pdf_pages = st.session_state.get(pages_cache_key, [])

    # --- PDF page preview ---
    with st.expander("🖼 PDF Page Preview", expanded=False):
        if pdf_pages:
            cols_per_row = 2
            for i in range(0, len(pdf_pages), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx < len(pdf_pages):
                        col.image(pdf_pages[idx], caption=f"Page {idx + 1}", use_container_width=True)
        else:
            st.info("Could not render PDF pages (pymupdf required).")

    # --- Show extracted PDF text ---
    with st.expander("📄 Extracted text from PDF (what the parser sees)", expanded=False):
        for page_key, text in sorted(pdf_text.items()):
            st.markdown(f"**{page_key}**")
            st.text(text or "(empty)")
            st.divider()

    st.subheader("2. Parser output")
    st.caption(f"{len(results)} row(s) — ground-truth editing below uses this as the starting baseline.")
    st.dataframe(_results_to_dataframe(results), width="stretch", hide_index=True)

    st.subheader("3. Review Editable Readings")
    st.caption("Edit the table, then click **Apply readings edits** to save. (Workaround for Streamlit data_editor bug.)")
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
        width="stretch",
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

    # Workaround for Streamlit bug: updating session_state from data_editor output on every rerun
    # causes edits to revert (first edit lost, every second change reverted). Only apply on button click.
    if st.button("Apply readings edits", key=f"{key_prefix}_apply_readings") and edited_df is not None and not edited_df.empty:
        new_rows = []
        for i in range(len(edited_df)):
            r = edited_df.iloc[i]
            orig = rows[i] if i < len(rows) else {}
            new_rows.append({
                "row_idx": orig.get("row_idx", i),
                "circuit_id": r.get("circuit_id") if pd.notna(r.get("circuit_id")) else orig.get("circuit_id", ""),
                "cml_id": r.get("cml_id") if pd.notna(r.get("cml_id")) else orig.get("cml_id", ""),
                "min_reading": r.get("min_reading") if pd.notna(r.get("min_reading")) else orig.get("min_reading", 0),
                "measurement_date": r.get("measurement_date") if pd.notna(r.get("measurement_date")) else orig.get("measurement_date", ""),
                "source_file": orig.get("source_file", ""),
                "extraction_method": r.get("extraction_method") if pd.notna(r.get("extraction_method")) else orig.get("extraction_method", "pdfplumber"),
                "is_correct": bool(r.get("is_correct")) if pd.notna(r.get("is_correct")) else True,
                "corrected_reading": r.get("corrected_reading") if pd.notna(r.get("corrected_reading")) else None,
                "notes": r.get("notes") if pd.notna(r.get("notes")) else orig.get("notes", ""),
            })
        st.session_state[f"{key_prefix}_rows"] = new_rows
        st.rerun()

    # --- Additions ---
    st.markdown("**Add missing readings** (parser did not extract these)")
    st.caption("Add rows, edit, then click **Apply additions** to save.")
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
        width="stretch",
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

    # Same workaround: only apply additions when button clicked (avoids data_editor revert bug)
    if st.button("Apply additions", key=f"{key_prefix}_apply_additions") and edited_additions is not None and not edited_additions.empty:
        new_additions = []
        for _, r in edited_additions.iterrows():
            new_additions.append({
                "circuit_id": str(r.get("circuit_id", default_circuit)).strip() or default_circuit,
                "cml_id": str(r.get("cml_id", "")).strip(),
                "min_reading": float(r.get("min_reading", 0)) if r.get("min_reading") is not None else 0.0,
                "measurement_date": str(r.get("measurement_date", default_date)).strip() or default_date,
                "notes": str(r.get("notes", "Added manually")).strip() or "Added manually",
            })
        st.session_state[f"{key_prefix}_additions"] = new_additions
        st.rerun()

    # --- Inline validation ---
    st.subheader("4. Validate Against Current Annotations")
    st.caption("Check whether the parser now produces the readings you have marked as correct (including additions).")
    if st.button("▶ Validate this PDF now", key=f"{key_prefix}_inline_validate", type="primary"):
        with st.spinner("Re-parsing and checking…"):
            ok, msg, passed, total = _inline_validate(
                pdf_bytes, source_filename,
                st.session_state[f"{key_prefix}_rows"],
                st.session_state[f"{key_prefix}_additions"],
            )
        if ok is True:
            st.success(f"✅ PASS — {msg}")
        elif ok is False:
            st.error(f"❌ FAIL ({passed}/{total}) — {msg}")
        else:
            st.warning(f"⚠️ {msg}")

    # --- Export (form to reduce reruns) ---
    st.subheader("5. Export Ground Truth")
    st.caption("All edits are in-memory. Only **Save** writes to disk.")

    include_pdf_text = st.checkbox("Include PDF text in export (for debugging)", value=False, key="incl_pdf_txt")
    pdf_text_export = pdf_text if include_pdf_text else None
    export_data = export_ground_truth(
        st.session_state[f"{key_prefix}_rows"],
        st.session_state[f"{key_prefix}_additions"],
        source_filename,
        source_path,
        pdf_text=pdf_text_export,
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
            # Clear sidebar validation cache so it reflects the new file
            st.session_state.pop("sidebar_validate_results", None)
            st.success(f"Saved {out_name} and PDF ({source_filename})")
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
