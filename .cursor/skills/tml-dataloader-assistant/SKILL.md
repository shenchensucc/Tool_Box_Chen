---
name: tml-dataloader-assistant
description: >-
  Helps prepare inputs for the TML Data Loader when users upload multiple files (Excel,
  exports, drawings metadata). Maps messy columns to canonical Source_Data headers,
  infers which workflows (01–20) apply, lists missing metadata, and produces a
  user-review plan before generating loaders. Use when the user mentions TML Data Loader,
  TM_Loader, Source_Data, CML/TML batch updates, building a dataloader, or uploads many
  spreadsheets for facility/TML workflows — not for UT inspection report PDF parsing.
---

# TML Data Loader Assistant

This skill directs structured analysis **only for the TML Data Loader path** (`frontend/pages/2_TML_Data_Loader.py`, `POST /api/tml/process`). Do **not** route UT inspection report PDF flows here unless the user explicitly ties them to Source_Data preparation.

## Ground truth from code

**Templates**: Download from UI — Source_Data template + TM_Loader (`Assets`, `TML` sheets).

**Source Excel**:

- Sheet name must be **`Source_Data`** (backend reads this sheet only).
- **Global row gate** (`backend/main.py`): every workflow receives rows where **`AER_Status_CML`** contains **`Yes`** (substring match). Rows without `Yes` never enter workflows. Empty after filter → API error.
- **Identity spine** (must exist as columns for workflows to run): **`Equipment ID`**, **`CML Group ID`**, **`sub-CML ID`** — plus **`AER_Status_CML`** for the gate above.

**Flexible headers**: Canonical names and aliases live in `backend/tml/excel_reader.py` (`COLUMN_ALIASES`). Prefer suggesting renames/mappings that match those aliases before inventing new ones.

## Workflow catalog (IDs match UI checkboxes)

Each workflow needs the spine columns **and** its extra column(s). Filters below apply **after** the global `Yes` filter.

| ID | Workflow | Extra source column(s) | Row filter (high level) |
|----|----------|-------------------------|---------------------------|
| 01 | Sub-CML Status (deactivated) | `AER_Status_CML` | Cell contains **`To be de-active`** |
| 02 | AER Flag | `AER_Status_CML` | Cell contains **`Yes`** |
| 03 | Code Year T-Min Formula | `Code Year (T-Min Formula)` | Value ≠ **`N/A`** (then forced to N/A in output) |
| 04 | Design Code | `CorrValue_Design_Code` | Non-null and ≠ 0 |
| 05 | Material Specification | `CorrValue_Material` | Non-null and ≠ 0 |
| 06 | Material Grade | `CorrValue_Grade` | Non-null and ≠ 0 |
| 07 | Design Temperature | `CorrValue_T` | Non-null and ≠ 0 |
| 08 | Piping Formula | `Piping Formula` | Value ≠ **`E`** (output set to E) |
| 09 | Outside Diameter | `CorrValue_OD` | Non-null and ≠ 0 |
| 10 | NPS | `CorrValue_NPS` | Non-null and ≠ 0 |
| 11 | Schedule | `CorrValue_Schedule` | Non-null and ≠ 0 |
| 12 | Design Pressure | `CorrValue_P` | Non-null and ≠ 0 |
| 13 | Temperature Coefficient | `Temperature Coefficient` | Per workflow file |
| 14 | Tnom | `CorrValue_Tnom` | Non-null and ≠ 0 |
| 15 | Tmin | `CorrValue_Tmin` | Non-null and ≠ 0 |
| 16 | Override Allowable Stress | `Override Allowable Stress` | Per workflow file |
| 17 | Allowable Stress | `AER_SMYS` | Filtered vs all-rows variant (see `_17_allowable_stress.py`) |
| 18 | Design Factor | `Design Factor` | Per workflow file |
| 19 | Joint Factor | `Joint Factor` | Per workflow file |
| 20 | Location Factor | `CorrValue_LocFactor` | Non-null and ≠ 0 |

For filters marked “Per workflow file”, read `backend/tml/workflows/_NN_*.py` before asserting exact rules.

## Agent workflow when user uploads many inputs

1. **Inventory**: List each file, sheet names (for Excel), and column headers + 2–3 sample rows per candidate sheet.
2. **Target**: Build one logical **`Source_Data`** projection — which sheet/file contributes Equipment/CML IDs vs parameter columns.
3. **Map**: Propose `user_column → canonical_column` using `COLUMN_ALIASES`; flag unknown headers for user rename.
4. **Gate**: Ensure planned rows will include **`Yes`** in `AER_Status_CML` where the user intends processing; warn if workflow 01 needs **`To be de-active`** in the same cells (substring logic — cells must contain required fragments).
5. **Workflows**: Recommend workflow IDs whose extra columns are present and populated; omit workflows whose columns are absent unless user will add them.
6. **Template**: Confirm user has **`TM_Loader.xlsx`** with **`Assets`** + **`TML`** aligned with facility CMMS conventions.
7. **Confirmation artifact**: Present a short **review block** for the user (markdown table): proposed mappings, chosen workflows, missing columns, ambiguous rows — **stop before claiming files were generated** unless the user confirmed.

Suggested review template:

```markdown
## TML Data Loader plan (confirm before Run)

### Files used
- ...

### Column mapping → Source_Data
| Your column | Canonical |
|-------------|-----------|

### Rows
- Will pass global Yes filter: ~N rows (explain).

### Workflows recommended
- IDs: ...

### Missing / manual
- ...

### User actions
- [ ] Approve mapping
- [ ] Approve workflow list
- [ ] Upload TM_Loader template + merged Source_Data
```

## Boundaries

- **Execution**: Generating outputs is via existing UI/API (`/api/tml/process`). The skill plans and validates; it does not replace backend workflow logic.
- **Inspection reports**: Parser/dataloader for UT PDFs is separate (`inspection_report_*`). Only reference it if the user wants to **derive tabular columns** from extracted data into Source_Data shape.

## Maintenance

When workflows or filters change, update this table from `backend/tml/workflows/` and `backend/main.py` (global `AER_Status_CML` filter).
