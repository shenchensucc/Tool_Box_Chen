# 📄 Inspection Report Loader

## Location

- **Frontend**: `frontend/pages/8_Inspection_Report_Loader.py`
- **Backend**: `backend/tml/inspection_report_parser.py`, `backend/tml/inspection_dataloader.py`
- **API**: `POST /api/tml/inspection-report/read`, `POST /api/tml/inspection-report`
- **Test fixtures**: `tests/fixtures/inspection_report_52-021K.pdf`, `inspection_report_52-010B_1.29_1.37.pdf`, `inspection_report_57-008U_1.52_1.29_4.09.pdf`

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
2. **CML bases**: From header "CML 1.01 & 1.05" or filename "1.29, 1.37" / "CML 1.52,1.29&4.09"
3. **Table**: pdfplumber with `vertical_strategy='text', horizontal_strategy='text'` (required for fragmented Acuren layout)
4. **Diameter → CML**: 8" section → CML 1.01, 6" section → CML 1.05
5. **Row number**: Cell immediately before diameter (8" or 6") in SECTION column = sub-CML suffix
6. **Sub-CML ID**: `{cml_base}-{row_num}` (e.g. 1.01-1, 1.05-3)
7. **Reading**: First thickness value (column A) per row; handles fragmented "0 . 2 8 5" → 0.285

### Format B: Generic Zone Table (3+ CMLs)

For multi-section reports (e.g. 57-008U with CML 1.52, 1.29, 4.09):

- CIRCUIT CML ZONE DIAM. columns; CML section headers (e.g. "CML 1.52")
- Diameter → CML: 16"→1.52, 30"→1.29, 8"/6"→4.09 (heuristic)
- Multiple readings per zone (NORTH SOUTH etc) → use **minimum**
- Zone 1–4 = sub-CML suffix (e.g. 1.52-1, 1.29-4)

### Fallback

If table parsing returns no rows, falls back to aggregate logic (min reading per CML). OCR used when pdfplumber extracts little or suspicious values.

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

Python (pdfplumber + pytesseract) is used for deterministic, fast, offline extraction. LLM APIs could interpret ambiguous layouts but add cost and variability. For standardized reports, Python is recommended.

**Note:** For OCR fallback to work, Tesseract must be installed on the system (pytesseract is a wrapper). On Windows: download from https://github.com/UB-Mannheim/tesseract/wiki.

---

## Test Data & Verification

### Fixtures

| Fixture | Circuit | CMLs | Notes |
|---------|---------|------|-------|
| inspection_report_52-021K.pdf | 52-021K | 1.01, 1.05 | Format A (8"/6") |
| inspection_report_52-010B_1.29_1.37.pdf | 52-010B | 1.29, 1.37 | May need OCR if table is image |
| inspection_report_57-008U_1.52_1.29_4.09.pdf | 57-008U | 1.52, 1.29, 4.09 | Format B (16"/30"/8"/6") |

Run verification:

```bash
python -c "
from pathlib import Path
from backend.tml.inspection_report_parser import parse_inspection_report_pdf
for fn in ['inspection_report_52-021K.pdf', 'inspection_report_57-008U_1.52_1.29_4.09.pdf']:
    r = parse_inspection_report_pdf(Path('tests/fixtures')/fn, fn)
    print(fn, len(r), 'rows')
    for x in r[:3]: print(f'  {x.circuit_id} {x.cml_id} {x.min_reading}')
"
```

Expected: 52-021K → 6 rows; 57-008U → 9 rows with readings 0.296–0.382.
