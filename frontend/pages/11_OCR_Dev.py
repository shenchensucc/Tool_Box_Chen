"""
OCR Development — direct parser test (no API, no subprocess).

Upload a PDF and see exactly what the parser extracts, which path it took,
and what readings it found. Use this to debug OCR issues without the API layer.

OCR Dev uses OCR-only parsing (no pdfplumber) and lets you pick the structured
OCR engine for speed/accuracy comparisons.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import apply_custom_styling, display_sidebar_navigation, get_layout_main, set_page_config

set_page_config("OCR Dev", "🔬")
apply_custom_styling()
display_sidebar_navigation()

main = get_layout_main()

STRUCTURED_KEY = "INSPECTION_REPORT_STRUCTURED_OCR_ENGINE"
LEGACY_KEY = "INSPECTION_REPORT_OCR_ENGINE"


@contextmanager
def _ocr_dev_engine_env(structured: str, legacy_tesseract_only: bool):
    """Temporarily set OCR engine env vars for the parse call."""
    saved_s = os.environ.get(STRUCTURED_KEY)
    saved_l = os.environ.get(LEGACY_KEY)
    os.environ[STRUCTURED_KEY] = structured
    if legacy_tesseract_only:
        os.environ[LEGACY_KEY] = "tesseract"
    else:
        os.environ.pop(LEGACY_KEY, None)
    try:
        yield
    finally:
        if saved_s is None:
            os.environ.pop(STRUCTURED_KEY, None)
        else:
            os.environ[STRUCTURED_KEY] = saved_s
        if saved_l is None:
            os.environ.pop(LEGACY_KEY, None)
        else:
            os.environ[LEGACY_KEY] = saved_l


with main:
    st.title("🔬 OCR Dev — Direct Parser Test")
    st.caption(
        "Calls the parser in-process (no API). **pdfplumber is disabled** here so you can "
        "benchmark Surya / EasyOCR / Tesseract. Circuit/CML context still comes from the filename when needed."
    )

    engine_label = st.segmented_control(
        "Structured + full-page OCR engine",
        options=["Auto", "Surya", "EasyOCR", "Tesseract"],
        default="Auto",
        help=(
            "Maps to INSPECTION_REPORT_STRUCTURED_OCR_ENGINE (Surya → EasyOCR → Tesseract in Auto). "
            "Full-page legacy fallback uses EasyOCR then Tesseract unless you pick Tesseract "
            "(then both structured and legacy prefer Tesseract). "
            "Surya mode skips EasyOCR on the legacy path so timing reflects Surya + Tesseract fallback only."
        ),
        key="ocr_dev_engine_pick",
    )

    structured_map = {
        "Auto": "auto",
        "Surya": "surya",
        "EasyOCR": "easyocr",
        "Tesseract": "tesseract",
    }
    structured_val = structured_map[engine_label]
    # When testing Surya speed, avoid running EasyOCR on the full-page fallback path.
    legacy_tess_only = engine_label in ("Surya", "Tesseract")

    uploaded = st.file_uploader("Upload inspection report PDF", type=["pdf"])

    if uploaded:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(uploaded.getvalue())
            tmp_path = Path(f.name)

        ocr_text_preview: dict[str, str] = {}
        try:
            from backend.tml.inspection_report_parser import (
                ocr_dev_collect_ocr_text_preview,
                parse_inspection_report_pdf,
                _classify_pdf_for_ocr,
                _is_tesseract_available,
                _get_easyocr_reader,
                _get_surya_models,
            )

            col1, col2, col3 = st.columns(3)
            col1.metric("Tesseract", "✅" if _is_tesseract_available() else "❌")
            col2.metric("Surya", "✅" if _get_surya_models() is not None else "❌")
            col3.metric("EasyOCR", "✅" if _get_easyocr_reader() is not None else "❌")

            with _ocr_dev_engine_env(structured_val, legacy_tess_only):
                is_image_heavy, candidate_pages = _classify_pdf_for_ocr(tmp_path, "", max_pages=6)
                st.info(
                    f"**PDF type:** {'image-heavy' if is_image_heavy else 'text-based'}  |  "
                    f"**OCR candidate pages:** {candidate_pages}  |  "
                    f"**Env:** `{STRUCTURED_KEY}={structured_val}`"
                    + (f", `{LEGACY_KEY}=tesseract`" if legacy_tess_only else "")
                )

                with st.spinner("Parsing (OCR-only, no pdfplumber)…"):
                    t_parse = time.perf_counter()
                    results = parse_inspection_report_pdf(
                        tmp_path,
                        uploaded.name,
                        skip_pdfplumber=True,
                    )
                    elapsed = time.perf_counter() - t_parse

                with st.spinner("Collecting OCR source text for preview (extra OCR passes)…"):
                    try:
                        ocr_text_preview = ocr_dev_collect_ocr_text_preview(
                            tmp_path,
                            include_legacy_tesseract=True,
                            include_legacy_easyocr=not legacy_tess_only,
                            include_structured_snippets=True,
                        )
                    except Exception as pe:
                        ocr_text_preview = {
                            "legacy_tesseract": f"(preview error: {pe})",
                            "legacy_easyocr": "",
                            "structured": "",
                        }

        except Exception as exc:
            import traceback

            st.error(f"Parser error: {exc}")
            st.code(traceback.format_exc())
            results = []
            elapsed = 0.0
        finally:
            tmp_path.unlink(missing_ok=True)

        st.success(
            f"Parse time **{elapsed:.1f}s** — {len(results)} reading(s) found (engine: **{engine_label}**). "
            "Time is `parse_inspection_report_pdf` only (OCR + heuristics; pdfplumber skipped)."
        )

        if results:
            rows = [
                {
                    "Circuit": r.circuit_id,
                    "CML": r.cml_id,
                    "Min Reading": r.min_reading,
                    "Date": r.measurement_date,
                    "Method": r.extraction_method,
                    "Page": r.source_page,
                }
                for r in results
            ]
            df = pd.DataFrame(rows)
            st.dataframe(df, width="stretch", hide_index=True)

            methods = df["Method"].value_counts().to_dict()
            st.caption(
                "**Method** is `ocr_structured:<engine>` for table OCR (surya / easyocr / tesseract), "
                "or `ocr` for full-page legacy OCR. Counts: "
                f"{methods}"
            )
        else:
            st.warning("No readings extracted. Check that the PDF contains UT thickness data.")

        if ocr_text_preview:
            _MAX_PREVIEW_CHARS = 120_000

            def _clip(s: str) -> str:
                if len(s) <= _MAX_PREVIEW_CHARS:
                    return s
                return s[:_MAX_PREVIEW_CHARS] + "\n\n… **truncated** (showing first 120,000 characters) …"

            with st.expander("OCR source text (debug)", expanded=False):
                st.caption(
                    "Raw text from OCR engines (separate from the parse above — this **re-runs** full-page "
                    "and structured OCR so you can inspect what was read). Uses the same env vars as the "
                    "engine selector. **Structured** follows `INSPECTION_REPORT_STRUCTURED_OCR_ENGINE` "
                    "(Surya → EasyOCR → Tesseract in Auto)."
                )
                if legacy_tess_only:
                    st.caption(
                        "Legacy EasyOCR preview is **skipped** in Surya/Tesseract mode to save time; "
                        "choose **Auto** or **EasyOCR** to include it."
                    )
                tab_te, tab_ez, tab_st = st.tabs(
                    ["Legacy: Tesseract (full page)", "Legacy: EasyOCR (full page)", "Structured (table OCR)"]
                )
                with tab_te:
                    st.text_area(
                        "tesseract_txt",
                        value=_clip(ocr_text_preview.get("legacy_tesseract", "")),
                        height=360,
                        label_visibility="collapsed",
                        key="ocr_dev_preview_tesseract",
                    )
                with tab_ez:
                    st.text_area(
                        "easyocr_txt",
                        value=_clip(ocr_text_preview.get("legacy_easyocr", "")),
                        height=360,
                        label_visibility="collapsed",
                        key="ocr_dev_preview_easyocr",
                    )
                with tab_st:
                    st.text_area(
                        "structured_txt",
                        value=_clip(ocr_text_preview.get("structured", "")),
                        height=360,
                        label_visibility="collapsed",
                        key="ocr_dev_preview_structured",
                    )
