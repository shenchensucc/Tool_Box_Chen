# 📄 Inspection Report Loader

## Location

- **Frontend**: `frontend/pages/8_Inspection_Report_Loader.py`
- **Backend**: `backend/tml/inspection_report_parser.py`, `backend/tml/inspection_dataloader.py`
- **API**: `POST /api/tml/inspection-report/read`, `POST /api/tml/inspection-report`
- **Test fixture**: `tests/fixtures/inspection_report_52-021K.pdf`

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

1. **Circuit base**: Extract "52-021K" from "52-021K 1-2" (strip line/section suffix)
2. **CML bases**: From header "CML 1.01 & 1.05" → [1.01, 1.05]
3. **Table**: pdfplumber with `vertical_strategy='text', horizontal_strategy='text'` (required for fragmented Acuren layout)
4. **Diameter → CML**: 8" section → CML 1.01, 6" section → CML 1.05
5. **Row number**: Cell immediately before diameter (8" or 6") in SECTION column = sub-CML suffix
6. **Sub-CML ID**: `{cml_base}-{row_num}` (e.g. 1.01-1, 1.05-3)
7. **Reading**: First thickness value (column A) per row; handles fragmented "0 . 2 8 5" → 0.285

### Fallback

If Acuren table parsing returns no rows, falls back to aggregate logic (min reading per CML).

---

## General Extraction

- **Primary**: pdfplumber for text and table extraction
- **Fallback**: pytesseract OCR when pdfplumber extracts little
- Date from header (e.g. "DATE: February 23, 2026")
- Circuit from "Circuit: 52-021K 1-2"
- CML IDs from "CML 1.01 & 1.05" or "CML:1.37, 1.29"

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

Python (pdfplumber + pytesseract) is used for deterministic, fast, offline extraction. LLM APIs could interpret ambiguous layouts but add cost and variability. For standardized reports, Python is recommended.

**Note:** For OCR fallback to work, Tesseract must be installed on the system (pytesseract is a wrapper). On Windows: download from https://github.com/UB-Mannheim/tesseract/wiki.

---

## Test Data & Verification

- **Fixture**: `tests/fixtures/inspection_report_52-021K.pdf`

Run verification:

```bash
python -c "
from pathlib import Path
from backend.tml.inspection_report_parser import parse_inspection_report_pdf
p = Path('tests/fixtures/inspection_report_52-021K.pdf')
r = parse_inspection_report_pdf(p, 'inspection_report_52-021K.pdf')
for x in r:
    print(f'{x.circuit_id}, {x.cml_id}, {x.min_reading}')
"
```

Expected: 6 rows with Circuit 52-021K, CML 1.01-1 through 1.05-4, readings as in table above.
