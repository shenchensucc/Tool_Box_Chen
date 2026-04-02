# Dig Package Template KPI Checklist
> **Purpose:** Verify every cell populated by `dig_package.py` in the 2026 Dig Package Template (via `dig_package_layout.json` anchors, not Excel defined names).
> Use this as a development progress tracker and test oracle.
>
> **How to use:**
> 1. Run `python tools/generate_dig_package_inspection.py` or `python tools/dig_package_kpi/agent_loop.py --template path/to/template.xlsx` to verify anchors; optional `python tools/inspect_template.py` for named-range dumps.
> 2. Work through each section; mark each KPI as ✅ PASS / ❌ FAIL / ⚠️ SKIP.
> 3. A "PASS" means: code sets the value AND the output Excel shows the correct value.
>
> **Automated progress (dev):** Run `python tools/dig_package_kpi/check_kpi.py` for **% complete** (code present and/or pytest “runs OK”). Use `check_kpi.py mark <id> pass|fail|skip` for manual verification (e.g. Excel output). Run `check_kpi.py sync-doc` to refresh the **Progress Dashboard** below. Optional UI: `streamlit run tools/dig_package_kpi/dashboard.py`.
>
> **Legend:**
> - **Named Range** — Legacy Excel defined name (optional); population uses **layout manifest** fields (`dig_display`, `pipe_od`, …) unless you restore name-based wiring.
> - **MDL Source Key** — The key in `MDL_COLUMN_KEYWORDS` passed to `_get_mdl_value(…)`.
> - **Fallback** — What gets written when the MDL column is missing or blank.
> - **Test method** — Unit test in `tests/test_dig_package.py` or manual check.

---

## A. Description / Header Table
> Named ranges written by `populate_single_value_fields()`.
> All fields live on the **cover sheet** of the template.
>
> **Real MDL column names confirmed from `ID216_Dig Notification Log_…xlsx`.**

| # | KPI Item | Named Range | MDL Column (actual) | Fallback | Status |
|---|----------|-------------|---------------------|----------|--------|
| A-1 | Dig Name (displayed in header) | `tmp_DigID_` | `Dig Name` → `Dig ID` | Dig ID string | ☐ |
| A-2 | Revision Number | `tmp_revNum` | `Dig Package Revision` → user input | `"0"` | ☐ |
| A-3 | Issue Date | `tmp_dddIss` | *(formula `=TODAY()`)* | Today's date | ☐ |
| A-4 | Pipeline Name | `tmp_pipNme` | `Pipeline Name` | `"-"` | ☐ |
| A-5 | Number of Excavations | `tmp_numExv` | *(counted from MDL rows per Dig ID)* | `1` | ☐ |

**Verify for A-series:**
- [ ] Dig Name uses `Dig Name` column (e.g. `ID6000_R1R2_MP3_NPS10_GW3180_ML`), falls back to `Dig ID` when blank.
- [ ] Revision reads `Dig Package Revision` from MDL (e.g. `0`); falls back to user-supplied revision when MDL column absent.
- [ ] Issue Date cell contains the formula `=TODAY()`, not a hard-coded date.
- [ ] Pipeline Name shows the actual pipeline segment (e.g. `"R1 to R2 (MP 0 to 67)"`).
- [ ] Number of Excavations is a positive integer ≥ 1.

---

## B. Pipe Information Table
> Named ranges written by `populate_single_value_fields()`.
>
> **Real MDL column names confirmed.**

| # | KPI Item | Named Range | MDL Column (actual) | Sample Value | Status |
|---|----------|-------------|---------------------|--------------|--------|
| B-1 | Pipe NPS (maps to OD field) | `tmp_pipeOD` | `Pipe NPS` | `10` (NPS 10") | ☐ |
| B-2 | Pipe NWT (mm) | `tmp_pipeNWT` | `Pipe NWT (mm)` | `5.16` | ☐ |
| B-3 | MOP (psi) | `tmp_mop` | `MOP (psi)` | `1414` | ☐ |
| B-4 | SEP (psi) | `tmp_sep` | `SEP (psi)` | `Refer to FWN` | ☐ |
| B-5 | Pipe Year (Installation Year) | `tmp_tarGWsPipYer` | *(not in MDL)* | `"-"` always | ☐ |
| B-6 | Pipe Grade | `tmp_tarGWsPipGrd` | `Pipe Grade` | `359` | ☐ |

**Verify for B-series:**
- [ ] Pipe NPS value (`10`, `12`, `8`) is written as-is from MDL — template label should read "NPS" not "OD (mm)".
- [ ] SEP writes `"Refer to FWN"` string correctly (non-numeric passthrough).
- [ ] Pipe Year always writes `"-"` since this MDL has no pipe year column.
- [ ] All cells show `"-"` when MDL column is unmapped — no blank/None/crash.
- [ ] Mixed NPS values (8, 10, 12) are handled correctly per dig — different digs have different specs.

---

## D-loc. Location Table
> Named ranges written by `populate_single_value_fields()`.

| # | KPI Item | Named Range | MDL Column (actual) | Sample Value | Status |
|---|----------|-------------|---------------------|--------------|--------|
| D1 | Latitude (decimal degrees) | `tmp_Lat` | `TGW Lat (deg)` | `54.2641592` | ☐ |
| D2 | Longitude (decimal degrees) | `tmp_Lon` | `TGW Long (deg)` | `-122.6660258` | ☐ |
| D3 | Milepost | `tmp_mp_` | `Milepost` | `3`, `60.5`, `248` | ☐ |

**Verify for D-loc series:**
- [ ] Latitude / Longitude are decimal degree values (6 decimal places from MDL).
- [ ] Milepost accepts integer (`3`) and decimal (`60.5`) values.
- [ ] Negative longitudes (all values are negative — western hemisphere) are preserved correctly.

---

## D-ili. ILI Run Information
> Named ranges written by `populate_single_value_fields()`.
>
> **Note:** MDL has MULTI-VALUE cells here — multiple ILI sources per dig.
> The template fields only hold a single value. Code writes the raw cell content
> (newline-joined string) as-is. If the template expects a single value, this needs
> further design input.

| # | KPI Item | Named Range | MDL Column (actual) | Sample Value | Status |
|---|----------|-------------|---------------------|--------------|--------|
| D4 | ILI Run Name | `tmp_ILI_Run_Name` | `Originating ILI` | `"Rosen-MFL-A\nRosen-MFL-A\nTDW"` | ☐ |
| D5 | ILI Run Date (accuracy field) | `tmp_ILI_Run_Name_Acc` | `ILI Time` | `"08/14/2022\n08/14/2022\n02/14/2025"` | ☐ |

**Verify for D-ili series:**
- [ ] Multi-vendor digs (e.g. Rosen + TDW) — what should the template show? Raw multi-line string or just the primary source?
- [ ] ILI Time date values (e.g. `08/14/2022`) pass through correctly as strings.
- [ ] Vendors present in this program: Rosen-MFL-A, Rosen-MFL-C, Rosen-EMAT, TDW, BH-EMAT, BH-MFL-A(M4M).

---

## E. Assessment Reference Points (AGM)
> Named ranges written by `populate_single_value_fields()`.
>
> **Note:** `Upstream AGM` / `Downstream AGM` columns do NOT exist in this MDL.
> Both cells will always show `"-"` until a different MDL format is used.

| # | KPI Item | Named Range | MDL Column (actual) | Status |
|---|----------|-------------|---------------------|--------|
| E-1 | Upstream AGM | `US_AGM` | *(not in MDL — always `"-"`)* | ☐ |
| E-2 | Downstream AGM | `DS_AGM` | *(not in MDL — always `"-"`)* | ☐ |

**Verify for E-series:**
- [ ] Both cells show `"-"` and do not crash when columns are absent.
- [ ] Named ranges `US_AGM` and `DS_AGM` exist in the template (run `inspect_template.py`).

---

## F. Excavation Assessment Summary
> Written by `populate_excavation_summary()` relative to anchor cell `tmp_numExv_num`.
> **Row offset** from the anchor cell.
>
> **Real MDL column names confirmed.**

| # | KPI Item | Anchor | Row Offset | MDL Column (actual) | Sample Value | Status |
|---|----------|--------|------------|---------------------|--------------|--------|
| F-1 | Excavation label | `tmp_numExv_num` | +0 | *(computed: `"Excavation #N"`)* | `"Excavation #1"` | ☐ |
| F-2 | Total Assessment Length | `tmp_numExv_num` | +1 | `Total Assessment Length (m)` | `9.304`, `1.286` | ☐ |
| F-3 | Start Assessment to TGW | `tmp_numExv_num` | +2 | `Start Assessment to TGW (m)` | `-0.500`, `12.104` | ☐ |
| F-4 | End Assessment to TGW | `tmp_numExv_num` | +3 | `End Assessment to TGW (m)` | `8.804`, `13.390` | ☐ |

**Verify for F-series:**
- [ ] Start Assessment is negative when TGW is within the assessment window (e.g. `-0.500`).
- [ ] Values are floats, not strings — no `"Refer to FWN"` in these columns.
- [ ] Row offsets +0/+1/+2/+3 match actual template layout (verify with `inspect_template.py`).

---

## G. Exposure Summary
> Written by `populate_excavation_summary()` relative to anchor cell `tmp_numExp_num`.
>
> **Note:** `Exposure Length`, `Start Exposure`, `End Exposure` columns do NOT exist in this MDL.
> All four cells will always show `"-"` until the MDL includes exposure data.

| # | KPI Item | Anchor | Row Offset | MDL Column (actual) | Status |
|---|----------|--------|------------|---------------------|--------|
| G-1 | Excavation label | `tmp_numExp_num` | +0 | *(computed)* | ☐ |
| G-2 | Exposure Length | `tmp_numExp_num` | +1 | *(not in MDL — always `"-"`)* | ☐ |
| G-3 | Start Exposure to TGW | `tmp_numExp_num` | +2 | *(not in MDL — always `"-"`)* | ☐ |
| G-4 | End Exposure to TGW | `tmp_numExp_num` | +3 | *(not in MDL — always `"-"`)* | ☐ |

**Verify for G-series:**
- [ ] All cells show `"-"` and do not crash when columns are absent.
- [ ] Anchor named range `tmp_numExp_num` exists in template.

---

## H. Feature Table (ILI Data)
> Written by `populate_feature_table()` starting at `tmp_feaIDs_row` + 2 rows.
> Each ILI row gets one Excel row. Target features are highlighted.
> **Column layout (1-indexed):**

| # | KPI Item | Column # | ILI Source Key | Target Feature Format | Status |
|---|----------|----------|----------------|-----------------------|--------|
| H-1 | Feature ID | 1 | `feature_id` | Bold red, grey fill | ☐ |
| H-2 | Excavation Number | 2 | *(from `excavation_num` arg)* | Bold red, grey fill | ☐ |
| H-3 | Feature Type | 3 | `feature_type` | Bold red, grey fill | ☐ |
| H-4 | Feature Description | 4 | `feature_desc` | Bold red, grey fill | ☐ |
| H-5 | Depth (%) | 5 | `depth` | Bold red, grey fill | ☐ |
| H-6 | Length (mm) | 6 | `length` | Bold red, grey fill | ☐ |
| H-7 | Width (mm) | 7 | `width` | Bold red, grey fill | ☐ |
| H-8 | Orientation (hh:mm) | 8 | `orientation` | Bold red, grey fill | ☐ |
| H-9 | ILI Chainage (m) | 9 | `distance` | Bold red, grey fill | ☐ |
| H-10 | Distance from TGW (m) | 10 | *(calculated: chainage − TGW chainage)* | Bold red, grey fill | ☐ |

**Verify for H-series:**
- [ ] Feature table starts exactly **2 rows below** `tmp_feaIDs_row` anchor cell.
- [ ] Rows are inserted (not overwriting template rows) — `ws.insert_rows(current_row)` is called per row.
- [ ] Target features (matched by ID or dimensions) show: bold font, red color `FF0000`, grey fill `D3D3D3`.
- [ ] Non-target features show: no bold, no color, no fill.
- [ ] Distance from TGW = chainage − TGW chainage (positive = downstream, negative = upstream).
- [ ] When TGW chainage is unknown, Distance from TGW column shows `"-"`.
- [ ] ILI values that are negative are clamped to `0.0` (see `get_ili_value` logic).
- [ ] When ILI column is unmapped, cell shows `"-"` (not blank/None/error).
- [ ] Depth (%) is a fraction (0.0–100.0), not a decimal (0.0–1.0).
- [ ] When multiple ILI sources are used, a header row `"--- ILI DATA SOURCE: {vendor} ---"` is inserted between them.
- [ ] Multi-source header row is bold blue, merged across columns 1–10.

### H-edge: Feature Filtering (GW window)
> `filter_ili_by_gw_count()` — only rows within ±3 GWDs of TGW enter the feature table.

| # | KPI Item | Status |
|---|----------|--------|
| H-11 | Features outside the 3-GWD window are excluded from output | ☐ |
| H-12 | When fewer than 3 GWDs exist on one side, all available GWDs are included (clamping) | ☐ |
| H-13 | When no girth-weld rows exist in ILI, fallback uses ±30 m window | ☐ |
| H-14 | GWD boundary rows themselves are included (0.5 m buffer applied) | ☐ |

---

## I. Output File Naming
> File names are derived from `package_output_stem()`.

| # | KPI Item | Logic | Status |
|---|----------|-------|--------|
| I-1 | Excel filename uses Dig Name when present | e.g. `ID6000_R1R2_Pipeline_ML.xlsx` | ☐ |
| I-2 | Falls back to Dig ID when Dig Name blank | e.g. `6000.xlsx` | ☐ |
| I-3 | Special characters stripped from filename | `<>:"/\|?*` replaced with `_` | ☐ |
| I-4 | PDF generated alongside Excel (Windows only) | Same stem, `.pdf` extension | ☐ |
| I-5 | Both files bundled in ZIP under their stem names | `ID6000_R1R2_….xlsx` + `.pdf` | ☐ |

---

## J. Summary JSON (in ZIP)
> Written as `generation_summary.json` at the ZIP root.
> Consumed by the Streamlit frontend to render the results table.

| # | KPI Item | JSON Key | Status |
|---|----------|----------|--------|
| J-1 | Total digs processed | `total_digs` | ☐ |
| J-2 | Successful digs | `successful_digs` | ☐ |
| J-3 | Failed digs | `failed_digs` | ☐ |
| J-4 | List of per-dig results | `results` | ☐ |
| J-5 | Per-dig: Dig ID (string) | `results[i].dig_id` | ☐ |
| J-6 | Per-dig: Dig Name | `results[i].dig_name` | ☐ |
| J-7 | Per-dig: status (`success` / `error`) | `results[i].status` | ☐ |
| J-8 | Per-dig: error message on failure | `results[i].error` | ☐ |
| J-9 | Per-dig: features matched count | `results[i].features_matched` | ☐ |
| J-10 | Per-dig: ILI files that failed to parse | `results[i].ili_files_failed` | ☐ |

---

## K. Named Range Health (Template Integrity)
> Run `python tools/inspect_template.py` and verify these ranges exist.

| # | Named Range | Expected | Status |
|---|-------------|----------|--------|
| K-1 | `tmp_DigID_` | Present, single cell | ☐ |
| K-2 | `tmp_revNum` | Present, single cell | ☐ |
| K-3 | `tmp_dddIss` | Present, single cell | ☐ |
| K-4 | `tmp_pipNme` | Present, single cell | ☐ |
| K-5 | `tmp_numExv` | Present, single cell | ☐ |
| K-6 | `tmp_pipeOD` | Present, single cell | ☐ |
| K-7 | `tmp_pipeNWT` | Present, single cell | ☐ |
| K-8 | `tmp_mop` | Present, single cell | ☐ |
| K-9 | `tmp_sep` | Present, single cell | ☐ |
| K-10 | `tmp_tarGWsPipYer` | Present, single cell | ☐ |
| K-11 | `tmp_tarGWsPipGrd` | Present, single cell | ☐ |
| K-12 | `tmp_Lat` | Present, single cell | ☐ |
| K-13 | `tmp_Lon` | Present, single cell | ☐ |
| K-14 | `tmp_mp_` | Present, single cell | ☐ |
| K-15 | `tmp_ILI_Run_Name` | Present, single cell | ☐ |
| K-16 | `tmp_ILI_Run_Name_Acc` | Present, single cell | ☐ |
| K-17 | `US_AGM` | Present, single cell | ☐ |
| K-18 | `DS_AGM` | Present, single cell | ☐ |
| K-19 | `tmp_numExv_num` | Present, single cell (assessment anchor) | ☐ |
| K-20 | `tmp_numExp_num` | Present, single cell (exposure anchor) | ☐ |
| K-21 | `tmp_feaIDs_row` | Present, single cell (feature table anchor) | ☐ |

**Total: 21 named ranges required.**
> If any are missing, `get_cell_from_named_range()` returns `None` silently — that KPI goes unpopulated with no error. This is the most common silent failure mode.

---

---

## C. Joint Summary Table
> **STATUS: ❌ NOT IMPLEMENTED — populate_joint_summary() does not exist.**
>
> `dig_package_reader.py` reads and parses a Joint Summary from generated output packages
> (for the Visual Tool). But `dig_package.py` **never writes** this section.
> Every KPI below is a gap that must be implemented.
>
> The Joint Summary is a matrix: rows = metrics (Longseam Orientation, Joint Length, Pipe Properties),
> columns = Girth Weld numbers from the ILI dataset.
> See `docs/DIG_PACKAGE_EXCEL_READING.md` §3 for the expected layout.

| # | KPI Item | Named Range (TBD) | Source | Status |
|---|----------|-------------------|--------|--------|
| C-1 | GWD column headers (girth weld numbers) | `tmp_js_gwd_cols` (?) | ILI girth weld list | ❌ NOT IMPLEMENTED |
| C-2 | Longseam Orientation per GWD per ILI source | *(matrix cells)* | ILI `orientation` for GW rows | ❌ NOT IMPLEMENTED |
| C-3 | Joint Length (m) per GWD | *(matrix cells)* | ILI chainage delta between GWDs | ❌ NOT IMPLEMENTED |
| C-4 | Target GWD column marker | `tmp_js_target` (?) | TGW from MDL | ❌ NOT IMPLEMENTED |
| C-5 | Pipe Year per joint | *(matrix cells)* | MDL `pipe_year` or ILI source | ❌ NOT IMPLEMENTED |
| C-6 | Pipe Grade per joint | *(matrix cells)* | MDL `pipe_grade` or ILI source | ❌ NOT IMPLEMENTED |
| C-7 | ILI Source label rows | *(row labels)* | Vendor format strings | ❌ NOT IMPLEMENTED |

> **Next step:** Run `python tools/inspect_template.py` to find the actual named ranges
> for this section, then implement `populate_joint_summary()` in `dig_package.py`.

---

## UNKNOWN / TO BE CONFIRMED FROM TEMPLATE
> These are cells that **may exist in the template** but are not currently written by code.
> Run `inspect_template.py` and check any non-empty cells not covered above.

| # | Area | Question | Status |
|---|------|----------|--------|
| ? | Cover sheet | Are there additional header cells (Company logo, document title) not using named ranges? | ☐ |
| ? | Pipe table | Does the template have a "Seam Type" or "Coating Type" row the code skips? | ☐ |
| ? | Joint Summary | Does the output template include a Joint Summary tab that needs populating? | ☐ |
| ? | Feature table | Does the template have columns beyond 10 (e.g. col 11 = "Comments")? | ☐ |
| ? | Revision history | Does the template have a revision history table separate from `tmp_revNum`? | ☐ |
| ? | Footer / signature | Are there cells for reviewer/approver names that need populating? | ☐ |

---

## Progress Dashboard

<!-- KPI_PROGRESS_AUTO_START -->

> **Auto-generated** by `tools/dig_package_kpi/check_kpi.py sync-doc`. **Overall progress: 91.6%** (76 PASS, 7 open, 0 SKIP).

| Section | KPIs | PASS | SKIP | FAIL / PENDING | % |
|---------|-----:|-----:|-----:|----------------|--:|
| A. Description Table | 5 | 5 | 0 | 0 | 100% |
| B. Pipe Information | 6 | 6 | 0 | 0 | 100% |
| D-loc. Location | 3 | 3 | 0 | 0 | 100% |
| D-ili. ILI Run Info | 2 | 2 | 0 | 0 | 100% |
| E. AGM | 2 | 2 | 0 | 0 | 100% |
| F. Assessment Summary | 4 | 4 | 0 | 0 | 100% |
| G. Exposure Summary | 4 | 4 | 0 | 0 | 100% |
| H. Feature Table | 14 | 14 | 0 | 0 | 100% |
| I. File Naming | 5 | 5 | 0 | 0 | 100% |
| J. Summary JSON | 10 | 10 | 0 | 0 | 100% |
| K. Named Range Health | 21 | 21 | 0 | 0 | 100% |
| C. Joint Summary Table | 7 | 0 | 0 | 7 | 0% |
| **TOTAL** | **83** | **76** | **0** | **7** | **91.6%** |

<!-- KPI_PROGRESS_AUTO_END -->

---

## How to Run the Full Template Inspection

```bash
# From project root
uv run python tools/inspect_template.py
# → writes docs/TEMPLATE_NAMED_RANGES.md with every named range and cell address

# Then compare against this checklist to find any cells in the template
# that are NOT covered by the KPIs above.
```

Any non-empty cell in the template output that is NOT in this checklist is a candidate
for a new KPI item. Add it to the "UNKNOWN / TO BE CONFIRMED" section above until confirmed.
