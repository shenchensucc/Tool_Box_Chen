# Dig package generation — reference alignment (PNG Integrity)

## Reference folder layout (user machine)

`Reference dig package/` (example: `C:\Users\cshen\Documents\Reference dig package`):

| Subfolder | Role |
|-----------|------|
| `1-Input dig list` | MDL-style **Dig Notification Log** (e.g. `ID216_Dig Notification Log_...xlsx`) |
| `2-Input ILI` | Vendor ILI workbooks (Anomalies / tally) — **populate this** for end-to-end generator tests |
| `3-Exported dig package` | **Target output** — PNG-exported dig packages (e.g. `ID6000_..._DP_R0.xlsx`) |

## What we matched in code (2026-03)

**Issue:** The generator required `Dig ID` values to contain **`GW`**, so numeric Integrity IDs (**6000**, **6001**, …) were ignored. PNG uses numeric **Dig ID** and full **`Dig Name`** for filenames.

**Changes in `backend/pipeline/dig_package.py`:**

1. **`is_valid_dig_id`** — Accepts 4–6 digit numeric IDs (Integrity) **or** legacy IDs containing `GW`.
2. **MDL column map** — `dig_id` maps to **Dig ID** only; new **`dig_name`** maps to **Dig Name** (not mixed with dig_id).
3. **Sheet priority** — Prefer **`Dig Notification Log`** when present.
4. **`Target Girth Weld (TGW)`** — Added as an alias for target girth weld column matching.
5. **Output filenames** — `{package_output_stem}_DP_R{rev}.xlsx` where stem prefers **Dig Name** (e.g. `ID6000_R1R2_MP3_NPS10_GW3180_ML`), else numeric/string Dig ID.
6. **Named range `tmp_DigID_`** — Filled with **Dig Name** when available (matches PNG “Dig Name” field on the form).
7. **MDL row filter** — `_mdl_rows_for_dig_id` so **6000** matches **6000.0** in Excel.

## What is *not* duplicated automatically

Reference exports use a **fixed layout** on sheet **`Dig Package`**: title block, **Joint Summary** matrix (GWD columns × Rosen/TDW rows), **Feature summary** tables, optional **Sheet1** narrow joint summary.

Our generator still fills a **user-supplied template** via **named ranges** (`tmp_feaIDs_row`, etc.). To match PNG **pixel-perfect**, supply the same Excel template PNG uses (or extend `populate_*` to write that grid layout).

## Debugging / iteration log

| Date | Finding | Action |
|------|-----------|--------|
| 2026-03-26 | `STRUCTURE_REPORT.md` shows `2-Input ILI` empty in scan | Add ILI xlsx files for pipeline tests; script only inventories what exists |
| 2026-03-26 | Reference MDL uses numeric Dig ID without GW | `is_valid_dig_id` + `dig_name` / `package_output_stem` |
| 2026-03-26 | Output names like `ID6000_..._DP_R0.xlsx` | Filename stem from Dig Name |

## Scripts

- `scripts/inspect_reference_dig_package.py` — dumps sheet names and first rows to `reference_dig_package/STRUCTURE_REPORT.md` (run locally; default base path is the user’s `Reference dig package` folder).
