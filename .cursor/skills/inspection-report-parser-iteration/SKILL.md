---
name: inspection-report-parser-iteration
description: Iterate on the inspection report PDF parser using ground truth. Use when improving parser accuracy, fixing extraction bugs, or adding support for new report formats.
---

# Inspection Report Parser Iteration

## Quick Start

1. **Validate** current state: `python dev_tools/validate_ground_truth.py`
2. **Review** ground truth in `dev_tools/ground_truth_data/*.json` for failure patterns
3. **Edit** `backend/tml/inspection_report_parser.py`
4. **Re-validate** until all pass (or skip if PDF missing)

## Workflow

```
Load PDF → Dev Tool (mark wrong/add missing) → Save ground truth
                    ↓
Validate → Parser changes → Validate (repeat)
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/tml/inspection_report_parser.py` | Parser logic (pdfplumber, OCR fallback) |
| `dev_tools/inspection_report_ground_truth.py` | Streamlit UI to create ground truth |
| `dev_tools/validate_ground_truth.py` | Validate parser vs ground truth |
| `dev_tools/ground_truth_data/*.json` | Expected readings per PDF |

## Ground Truth Format

- **readings**: Parser output. `is_correct: true` = accept; `false` = use `corrected_reading` or `expected_reading`
- **additions**: Rows parser missed (manual add)
- **source_file**: PDF filename (must exist in `ground_truth_data/` or `tests/fixtures/`)

Validation uses `is_correct` readings + additions as expected. Tolerance: 0.01 for readings.

## Common Fixes

1. **Wrong CML format** (e.g. "11.05" vs "11.05-1"): Single-CML aggregate fallback adds `-1`; table parsers use `{base}-{zone}`. Check which code path runs.
2. **Phone number false positive** (0.79 from 780.790): Dedupe keeps min; if correct reading exists, it wins. Else add context-aware filter in `_extract_numeric_readings`.
3. **Filename CML** (e.g. "2.37UT" no space): Regex `([\d.]+)\s*UT` allows zero spaces.
4. **Missing zones**: Table structure may differ; try permissive parser or generic zone table.
5. **Image-based results** (e.g. 52-010B): Azure DI triggers when readings are all 0.0 or pdfplumber finds little text. Ensure `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_KEY` are set in `.env`.

## Validation Commands

```bash
python dev_tools/validate_ground_truth.py
python dev_tools/validate_ground_truth.py --fixtures-only
```

## Azure DI tuning

Set in `.env` when debugging OCR:

- `INSPECTION_REPORT_AZURE_DI_ONLY=1` — skip pdfplumber table/text readings; Azure DI tokens only
- `INSPECTION_REPORT_IMAGE_FIRST=1` — run Azure DI before pdfplumber table parsing
- `INSPECTION_REPORT_OCR_MIN_CONF=0.6` — minimum token confidence (default 0.6)

## Checklist

- [ ] Run validation before and after changes
- [ ] Place PDFs in `dev_tools/ground_truth_data/` or `tests/fixtures/` for ground truth to run
- [ ] Update `backend/tml/inspection_fixtures.py` when adding new fixture tests
