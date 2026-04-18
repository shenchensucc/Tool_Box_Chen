# Chen's Engineer Toolbox — Development Guide

## How to run locally

```bash
# Terminal 1 — FastAPI backend (port 8000)
uvicorn backend.main:app --reload

# Terminal 2 — Streamlit frontend (port 8501)
streamlit run frontend/Home.py
```

## OCR engine

Azure Document Intelligence only. No local OCR (Surya/EasyOCR/Tesseract removed).
- Tier: S0 ($1.50/1,000 pages) as of 2026-04-18
- Credentials in `.env`: `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` + `AZURE_DOCUMENT_INTELLIGENCE_KEY`
- Resource: `https://facility-report.cognitiveservices.azure.com/`
- OCR runs via `asyncio.to_thread` — never `ProcessPoolExecutor`

## Syncing shared modules with NDELoader

`D:/GitHub/NDELoader` is a commercial spinoff of this project. These 3 files are kept in sync (independent copies, no symlink):
- `backend/tml/inspection_report_parser.py`
- `backend/tml/inspection_dataloader.py`
- `backend/tml/excel_reader.py`

**When NDELoader improves these files**, copy back here:
```bash
cp D:/GitHub/NDELoader/backend/tml/inspection_report_parser.py backend/tml/inspection_report_parser.py
cp D:/GitHub/NDELoader/backend/tml/inspection_dataloader.py backend/tml/inspection_dataloader.py
cp D:/GitHub/NDELoader/backend/tml/excel_reader.py backend/tml/excel_reader.py
```

**When Tool_Box_Chen improves these files**, copy to NDELoader:
```bash
cp backend/tml/inspection_report_parser.py D:/GitHub/NDELoader/backend/tml/inspection_report_parser.py
cp backend/tml/inspection_dataloader.py D:/GitHub/NDELoader/backend/tml/inspection_dataloader.py
cp backend/tml/excel_reader.py D:/GitHub/NDELoader/backend/tml/excel_reader.py
```

## Skill routing

When the user's request matches an available skill, invoke it using the Skill tool first.

Key routing rules:
- Bugs, errors, "why is this broken" → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Architecture review → invoke plan-eng-review
- Save progress, resume → invoke checkpoint
