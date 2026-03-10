# 📄 Inspection Report Loader

## Location

- **Frontend**: `frontend/pages/8_Inspection_Report_Loader.py`
- **Backend**: `backend/tml/inspection_report_parser.py`, `backend/tml/inspection_dataloader.py`
- **API**: `POST /api/tml/inspection-report/read`, `POST /api/tml/inspection-report`
- **Test fixtures**: `tests/fixtures/inspection_report_52-021K.pdf`, `inspection_report_57-008U_1.52_1.29_4.09.pdf`

## Purpose

Upload UT inspection report PDFs. Two actions at the same level:

1. **Read Reports**: Parse PDFs and show summary (Circuit, CML, Min Reading, Date). No source Excel or dataloader.
2. **Generate Dataloader**: Create APM Measurements Excel. Source Excel optional; when missing, Equipment ID = "Need Add Equipment ID" (incomplete dataloader—edit in Excel before APM upload).

## Inputs

- **PDFs** (required): One or more UT inspection report PDFs (e.g. Acuren format)
- **Source Excel** (optional, for Generate Dataloader): Sheet `Source_Data` with `Circuit ID` and `Equipment ID`

## Output

- `Inspection_Report_Dataloader.xlsx` with Measurements sheet
- Summary table in the UI for verification

---

## Acuren Table Parsing (Primary Logic)

For Acuren-style reports with SECTION/DIAM table on the results page:

| Circuit  | CML   | Reading |
|----------|-------|---------|
| 52-021K  | 1.01-1| 0.285   |
| 52-021K  | 1.01-2| 0.299   |
| 52-021K  | 1.05-1| 0.456   |
| 52-021K  | 1.05-2| 0.450   |
| 52-021K  | 1.05-3| 0.393   |
| 52-021K  | 1.05-4| 0.405   |

### Parser Logic

1. **Circuit base**: Extract "52-021K" from "52-021K 1-2" (strip breakdown drawing "1-2", "2-3", "1,3-3")
2. **CML bases**: From header "CML 1.01 & 1.05" or filename "1.29, 1.37" / "CML 1.52,1.29&4.09" / "52-001G 1-1 2.32 UT-..." / "57-034C 4-7 2.37UT-..." (no space before UT)
3. **Table**: pdfplumber with `vertical_strategy='text', horizontal_strategy='text'` (required for fragmented Acuren layout)
4. **Diameter → CML**: 8" section → CML 1.01, 6" section → CML 1.05; single CML accepts any diameter
5. **Row number**: Cell immediately before diameter (8" or 6") in SECTION column = sub-CML suffix (zones 1–9)
6. **Sub-CML ID**: `{cml_base}-{row_num}` (e.g. 1.01-1, 1.05-3, 2.32-7). Zone "4" can appear as "4"" (combined with 4" diameter).
7. **Reading**: First thickness value (column A) per row; handles fragmented "0 . 2 8 5" → 0.285
8. **Dedupe**: Same CML twice (e.g. from overlapping table regions) → keep min reading. No value filter.
9. **Single-zone CML**: Aggregate fallback outputs "11.05-1" (not "11.05"). Single-CML tables may lack diameter column; zone+reading sufficient.
10. **Permissive fallback**: For single CML with few results, try zone+reading extraction (handles "Zone 1", "Loc 1" etc).

### Format B: Generic Zone Table (3+ CMLs)

For multi-section reports (e.g. 57-008U with CML 1.52, 1.29, 4.09):

- CIRCUIT CML ZONE DIAM. columns; CML section headers (e.g. "CML 1.52")
- Diameter → CML: 16"→1.52, 30"→1.29, 8"/6"→4.09 (heuristic)
- Multiple readings per zone (NORTH SOUTH etc) → use **minimum**
- Zone 1–9 = sub-CML suffix (e.g. 1.52-1, 1.29-4, 2.32-7)

### Page Filter (UT REPORT vs UT Grid)

Reports with both summary and detailed UT Grid readings: parser prefers pages with **"UT REPORT - TEE"** or **"UT REPORT - ELBOW"** (or PIPE, REDUCER, CAP, WELD, STRAIGHT). Skips pages with **"UT Grid"** or **"GRID Reading"** (detailed readings). If no summary page found, processes all pages (backward compatible).

### Fallback

If table parsing returns no rows, falls back to aggregate logic (min reading per CML). OCR used when pdfplumber extracts little or suspicious values.

### LLM Vision (OCR-like)

When `INSPECTION_REPORT_LLM_VISION=1` and `AI_BUILDER_TOKEN` are set, the parser can use an LLM as an OCR-like step:

1. **PDF pages → LLM**: One vision call per page; LLM transcribes all text (plain text, not JSON).
2. **Text → existing parser**: Same `_extract_numeric_readings`, `_extract_date_from_text`, `_extract_cml_ids_from_text`, zone assignment, etc.
3. **Output**: `ExtractedReading[]` with `extraction_method="llm_vision"`.

LLM is used as fallback when OCR fails or returns suspicious results. For comparison/testing, set `INSPECTION_REPORT_LLM_ONLY=1` to skip OCR and use LLM directly.

### OCR Tuning

| Env var | Effect |
|---------|--------|
| `INSPECTION_REPORT_OCR_ENGINE=tesseract` | Use Tesseract only (skip EasyOCR; faster) |
| `INSPECTION_REPORT_OCR_HIGH_DPI=1` | 400 DPI for both EasyOCR and Tesseract (better decimal digits) |
| `INSPECTION_REPORT_OCR_PREPROCESS=1` | Contrast + sharpen before OCR |

---

## General Extraction

- **Primary**: pdfplumber for text and table extraction
- **Fallback**: pytesseract OCR when pdfplumber extracts little or suspicious (e.g. 0.79 from phone 780.790)
- Date from header (e.g. "DATE: February 23, 2026") or filename `_02.23.2026.pdf`
- Circuit from "Circuit: 52-010B 2-3" → base "52-010B"
- CML IDs from header, ITEM(S) EXAMINED, or filename

---

## Error Handling & Debugging

- **Frontend**: On non-200 response, expandable "Error details" shows URL, status, response body, and 404 tip (restart backend)
- **Backend**: Logs full traceback on exception; returns `{type}: {message}` in detail
- **Startup**: Logs inspection-report routes at startup so you can verify endpoints are registered

---

## UI

- **Read Reports** and **Generate Dataloader** buttons: same size, same primary style, `use_container_width=True`
- Source Excel in expander (optional)

---

## OCR vs LLM

Python (pdfplumber + OCR) is used for deterministic, fast extraction. An optional **LLM Vision API** path can validate or replace OCR when enabled.

### Image-based results tables

Some reports (e.g. 52-010B) have "Readings, Grids & Photos on attached pages" — the results table is embedded as an image. The parser:

1. **Triggers OCR** when pdfplumber returns no readings, little text, or suspicious 0.0-only readings
2. **Builds zone-level output** from OCR-extracted numbers (e.g. 6 readings + 2 CMLs → 1.29-1..3, 1.37-1..3)

**OCR engines (tried in order):**

| Engine | Install | Notes |
|--------|---------|------|
| **EasyOCR** (primary) | `pip install easyocr` | Often better on tables; no external binary |
| **Tesseract** (fallback) | `winget install UB-Mannheim.TesseractOCR` | 300 DPI, PSM 6/11 for tables |

EasyOCR runs first when 4+ readings expected; Tesseract used otherwise. Both prefer summary table pages (UT REPORT - Connections/Elbow) over grid pages.

**LLM Vision API (optional):** Set `INSPECTION_REPORT_LLM_VISION=1` and `AI_BUILDER_TOKEN` to use vision models (e.g. kimi-k2.5) via AI Builders Space API. PDF pages are sent as images; the model extracts readings from summary tables. Use as validation or fallback when OCR underperforms.

- **Same token as Chat with Chen:** `AI_BUILDER_TOKEN` in `.env` (see `.env.example`).
- **When it runs:** LLM Vision is only invoked when pdfplumber/OCR return no readings, or when all readings are 0.0 (suspicious) and fewer than 4. For PDFs that extract successfully via text/OCR, the LLM path is skipped.
- **Speed:** Use `INSPECTION_REPORT_VISION_MODEL=gemini-3-flash-preview` (default, ~20s) for faster photo-like response. `kimi-k2.5` is slower but may extract better. `INSPECTION_REPORT_LLM_MAX_PAGES=3` and `INSPECTION_REPORT_LLM_DPI=150` reduce payload for speed.
- **To test:** Run `python dev_tools/test_llm_vision_quick.py` (requires PDF in `ground_truth_data/`).

**Deployment:** The Dockerfile installs `tesseract-ocr` via apt. On Linux, Tesseract is in PATH (`/usr/bin/tesseract`). On Windows dev, the parser uses `C:/Program Files/Tesseract-OCR/tesseract.exe` when present.

---

## Test Data & Verification

### Fixtures

| Fixture | Circuit | CMLs |
|---------|---------|------|
| inspection_report_52-021K.pdf | 52-021K | 1.01, 1.05 |
| inspection_report_57-008U_1.52_1.29_4.09.pdf | 57-008U | 1.52, 1.29, 4.09 |

Verify: `python dev_tools/validate_ground_truth.py`

---

## Dev Tool: Ground Truth

A local development tool (`dev_tools/inspection_report_ground_truth.py`) uses the same parser logic for developer iteration:

- Mark wrong readings and enter corrections
- Add missing readings in an editable table (frontend-only until Save)
- Export to JSON for training/ground-truth datasets
- Parse results cached; only Save writes to disk

Run: `streamlit run dev_tools/inspection_report_ground_truth.py --server.runOnSave true`

### Validation

`python dev_tools/validate_ground_truth.py` — fixtures + ground truth (PDFs in `ground_truth_data/` or `tests/fixtures/`).
