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

### OCR Tuning

| Env var | Effect |
|---------|--------|
| `INSPECTION_REPORT_AZURE_DI_ONLY=1` | Skip pdfplumber table/text readings; use Azure DI tokens only |
| `INSPECTION_REPORT_IMAGE_FIRST=1` | Run Azure DI before pdfplumber table parsing |
| `INSPECTION_REPORT_OCR_MIN_CONF=0.6` | Minimum Azure DI token confidence (default 0.6) |

---

## General Extraction

- **Primary**: pdfplumber for text and table extraction
- **OCR**: Azure Document Intelligence when pdfplumber extracts little or suspicious values
- Date from header (e.g. "DATE: February 23, 2026") or filename `_02.23.2026.pdf`
- Circuit from "Circuit: 52-010B 2-3" → base "52-010B"
- CML IDs from header, ITEM(S) EXAMINED, or filename

---

## OCR — Azure Document Intelligence

Azure DI (`prebuilt-layout` model) is the sole OCR engine. The PDF is sent to Azure DI from the backend thread pool (`asyncio.to_thread`) in 2-page batches to comply with the F0 free tier. All pages are processed regardless of document length.

- **Busy rejection**: If a parse is already in-flight, new requests return **HTTP 503**
- **Retry logic**: 429 rate-limit errors are retried up to 3 times with exponential back-off
- **Config**: `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY` in `.env`

---

## Error Handling & Debugging

- **Frontend**: On non-200 response, expandable "Error details" shows URL, status, response body, and 404 tip (restart backend)
- **Backend**: Logs full traceback on exception; returns `{type}: {message}` in detail
- **HTTP 503**: Returned when a parse is already running; user should wait and retry
- **Startup**: Logs inspection-report routes at startup so you can verify endpoints are registered

---

## UI

- **Read Reports** and **Generate Dataloader** buttons: same size, same primary style, `use_container_width=True`
- Source Excel in expander (optional)

---

## OCR (image-based reports)

Azure Document Intelligence handles all image-based extraction. The parser triggers Azure DI when pdfplumber returns no readings, little text, or suspicious 0.0-only readings.

### Image-based results tables

Some reports (e.g. 52-010B) have the results table embedded as an image. The parser:

1. **Sends the full PDF to Azure DI** — all pages processed, no page limit
2. **Extracts structured rows** from Azure DI word tokens via `_extract_structured_rows_from_easyocr_tokens`
3. **Supplements with pdfplumber** to fill any zones Azure DI missed

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
