"""
OCR Development — direct parser test (no API, no subprocess).

Upload a PDF and see exactly what the parser extracts, which path it took,
and what readings it found. Use this to debug OCR issues without the API layer.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import apply_custom_styling, display_sidebar_navigation, get_layout_main, set_page_config

set_page_config("OCR Dev", "🔬")
apply_custom_styling()
display_sidebar_navigation()

main = get_layout_main()

with main:
    st.title("🔬 OCR Dev — Direct Parser Test")
    st.caption("Calls the parser directly in-process. No API, no subprocess, no network.")

    uploaded = st.file_uploader("Upload inspection report PDF", type=["pdf"])

    if uploaded:
        with st.spinner("Parsing…"):
            t0 = time.perf_counter()

            # Write to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                f.write(uploaded.read())
                tmp_path = Path(f.name)

            try:
                # Import parser here so it runs in the Streamlit process
                from backend.tml.inspection_report_parser import (
                    parse_inspection_report_pdf,
                    _classify_pdf_for_ocr,
                    _is_tesseract_available,
                    _get_easyocr_reader,
                    _get_surya_models,
                )

                # Show engine availability
                col1, col2, col3 = st.columns(3)
                col1.metric("Tesseract", "✅" if _is_tesseract_available() else "❌")
                col2.metric("Surya", "✅" if _get_surya_models() is not None else "❌")
                col3.metric("EasyOCR", "✅" if _get_easyocr_reader() is not None else "❌")

                # Classify PDF
                is_image_heavy, candidate_pages = _classify_pdf_for_ocr(tmp_path, "", max_pages=6)
                st.info(
                    f"**PDF type:** {'image-heavy' if is_image_heavy else 'text-based'}  |  "
                    f"**OCR candidate pages:** {candidate_pages}"
                )

                # Parse
                results = parse_inspection_report_pdf(tmp_path, uploaded.name)
                elapsed = time.perf_counter() - t0

            except Exception as exc:
                import traceback
                st.error(f"Parser error: {exc}")
                st.code(traceback.format_exc())
                results = []
                elapsed = time.perf_counter() - t0
            finally:
                tmp_path.unlink(missing_ok=True)

        st.success(f"Done in {elapsed:.1f}s — {len(results)} reading(s) found")

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
            st.dataframe(df, use_container_width=True, hide_index=True)

            methods = df["Method"].value_counts().to_dict()
            st.caption(
                "**Method** is `ocr_structured:<engine>` for table OCR (surya / easyocr / tesseract). "
                f"Counts: {methods}"
            )
        else:
            st.warning("No readings extracted. Check that the PDF contains UT thickness data.")
