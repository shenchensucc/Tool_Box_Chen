# Dig Package Excel Reading — Data Flow

## Dig Package Visual Tool (app)

| Piece | Location |
|-------|----------|
| Streamlit page | `frontend/pages/3_Dig_Package_Visual_Tool.py` |
| UI + maps + workbook preview | `frontend/ili_visual_shared.py` — `render_dig_package_visual_tool`, `render_feature_map_fragment`, `_render_dig_package_source_preview`, `_build_feature_map_figure` (2D), `_build_3d_pipeline_figure` (3D) |
| API | `POST /api/ili/process-dig-package` → `build_feature_map_from_dig_package` in `backend/pipeline/dig_package_reader.py` |

The page title and sidebar already identify the tool; the body uses a short caption only (no duplicate heading).

---

## Overview

The dig package Excel has **two required table sections** plus an **optional NDE block**:

1. **Feature Summary** — ILI features (defects, girth welds, etc.)
2. **Joint Summary** — **Longseam orientation per GWD per ILI source**, optional **joint lengths** (metres), and metadata used to **match** Joint Summary GWDs to Feature Summary girth welds when needed
3. **NDE Limits** (optional) — **TGW-referenced NDE assessment strip**: start/end chainage (m) and optional length / target GWD label row. Often appears **between** Joint Summary and Feature Summary on the same sheet; it is **not** a normal header+data table — see §1b below.

**Key engineering insight:** Girth welds are circumferential (360°) — they carry no orientation.
The **longseam orientation** is the angle of the pipe’s longitudinal weld seam and comes from the **Joint Summary** section (not from defect “orientation” columns in the Feature Summary).

A dig package can have **multiple ILI data sources** (e.g. “2022 Rosen MFL-A” and “2025 TDW”).
Each source may report a slightly different longseam angle for the same joint.
**All sources’ longseam readings are shown simultaneously** in the visualisation when parsing succeeds.

**Division of labour**

| Question | Primary data |
|----------|----------------|
| Where are the **red GWD lines / span boundaries** on chainage (2D dig package)? | **Joint Summary** joint lengths + GWD order (**Step G**), when valid; otherwise **Feature Summary** girth-weld rows |
| What **clock hour** is the longseam for GWD *N* for vendor *V*? | **Joint Summary** matrix (after `_parse_joint_summary_matrix`) |
| Optional **joint length (m)** per GWD for labels / checks | **Joint Summary** “joint length” rows → `scatter_data["joint_lengths_by_gwd"]` |
| Where is the **NDE assessment zone** (grey band, m from TGW)? | **NDE Limits** block → `scatter_data["nde_region"]` (`x0`, `x1`, optional `length_m`, `target_gwd_number`) |

**3D ring positions** follow **`scatter_data["girth_welds"]`**: when Joint Summary **TGW layout (Step G)** runs, those chainages are synthetic from joint lengths (same list as 2D). If Step G is skipped, rings use **Feature Summary** girth-weld rows. Wrong **longseam** extraction misplaces coloured seam lines; wrong joint lengths (when Step G applies) move both 2D lines and 3D rings.

**NDE band** uses the **same chainage axis** as Feature Summary when distance is **Distance from TGW (m)**: `nde_region.x0` / `x1` are drawn directly as vertical boundaries and shading in 2D, and as a cylindrical sleeve + boundary rings in 3D (clipped to the visible joint window).

---

## 1. Excel Reading: `parse_dig_package_excel`

**File:** `backend/pipeline/dig_package_reader.py`

```
parse_dig_package_excel(file_content: bytes)
    → (feature_df, joint_df, metadata)
```

`metadata` includes **`nde_limits`** (parsed dict or `None`), **`nde_sheet`** when found, plus existing flags (`feature_section_found`, `joint_section_found`, etc.).

### How it works

1. Load workbook with `openpyxl` (`data_only=True`). Merged cells are handled when reading: empty cells inside a merge inherit the **top-left** cell value (`_get_effective_cell_value`).
2. Loop over all sheets until both table sections are found (or sheets are exhausted). **On every sheet**, until NDE is found once, run **`parse_nde_limits_section`** (§1b); the first successful parse is kept.
3. For each **Feature / Joint** section:
   - Find a **title row** whose text (first ~5 columns) matches the section keywords.
   - Find the **header row**: the first row *after* the title, within 20 rows, that has **≥3 non-empty** cells in columns 1–20 **and** ≥3 **distinct** non-empty values (this skips a wide merged title like “Joint Summary” repeated across the sheet).
   - Read **one header row** and all data rows below until a completely empty row (after data has started).
4. Column names are normalised (whitespace, NBSP) and forced **unique** (`_make_unique_headers`): duplicate titles become `30900`, `30900__2`, etc.
5. **Joint Summary only:** run `_reshape_joint_summary_dataframe` (see below), then return `joint_df`.

### Section detection

| Section         | Header keywords                                                        |
|-----------------|------------------------------------------------------------------------|
| Feature Summary | `"feature summary"`, `"feature summary table"`, `"ili feature summary"` |
| Joint Summary   | `"joint summary"`, `"joint summary table"`, `"girth weld summary"`    |

### 1b. NDE Limits block (`parse_nde_limits_section`)

**Not** parsed as a header row + data matrix. The reader finds a **title row** where some cell in the first few columns contains both **“nde”** and **“limit”** (e.g. **NDE Limits**), then scans following rows for **label / value** pairs: label text in the leading cell(s), first **numeric** cell to the right is the value (`_row_label_and_value`, `_parse_float_for_nde`).

**Rows used for the map (TGW-referenced strip)**

| Label pattern (normalised, contains…) | Maps to |
|---------------------------------------|---------|
| `nde assessment start` + `tgw` | `start_from_tgw_m` → **`nde_region.x0`** |
| `nde assessment end` + `tgw` | `end_from_tgw_m` → **`nde_region.x1`** |
| `nde assessment length` | Optional check vs `x1 − x0` (info log on mismatch); stored as `length_m` |

**Optional row:** label contains **`target`**, **`girth`**, **`weld`** and a numeric GWD in the value cell → `target_gwd_number` (metadata / `nde_region` / `feature_summary_raw`).

**Ignored for this strip:** rows whose label indicates **downstream-only** NDE (`from d/s`, `d/s gw`, etc.) — only the **TGW** start/end drive the shared 2D/3D band.

**Stop scanning** when a row label hits **feature summary** / **joint summary** keywords (avoids eating the next section).

**Output wiring** (`build_feature_map_from_dig_package`)

- If **both** TGW start and end are present: `scatter_data["nde_region"] = { "x0", "x1", "length_m"?, "target_gwd_number"? }` (with `x0 ≤ x1`).
- Copy for tracing: `feature_summary_raw["nde_limits"]` (same fields as parsed from Excel).

If start or end is missing, **no** `nde_region` is set (nothing drawn).

### Joint Summary reshape (`_reshape_joint_summary_dataframe`)

Runs **only** when the first two column headers match one of:

- Both start with **“Girth Weld No.”** (duplicate header pattern), or  
- Column 2 is **“Source”** / **“ILI Source”** (case-insensitive normalisation).

Then columns are renamed to **`Metric`** and **`Source`**. For each row, if the metric cell still contains a merged block like  
`Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)`, sources are taken from **parentheses** (or from following lines in a newline-merged label), and the **Source** column is filled so that **successive rows** with the same metric text map to Rosen, then TDW, etc.

If your template uses **“Metric”** in column A but column B is **not** “Source” / duplicate “Girth Weld No.”, **reshape does nothing** — the matrix parser still runs on the raw `joint_df`.

---

## 2. Feature Summary → Features and Girth Welds

**File:** `backend/pipeline/feature_map_builder.py` — `build_feature_map_from_df(feature_df, ili_cols)`

### Column mapping

| Standard key   | Example Excel headers                                       | Used for                          |
|----------------|-------------------------------------------------------------|-----------------------------------|
| `distance`     | "Distance from TGW (m)", "ILI Chainage (m)", "Chainage"     | x-axis (chainage)                 |
| `depth`        | "Depth (%)", "Feature Depth", "Max. Depth"                  | Feature depth                     |
| `length`       | "Length (mm)", "Feature Length"                             | Box length                        |
| `width`        | "Width (mm)", "Feature Width"                               | Box width                         |
| `feature_id`   | "Feature ID", "ID#", "Joint"                                | Feature ID                        |
| `feature_type` | "Feature Type", "Type"                                      | Girth Weld vs defect vs seam      |
| `orientation`  | "Orientation (hh:mm)", "Feature Orientation"                | Defect orientation (not longseam) |
| `joint_number` | "Joint", "GWD", "Joint Number"                              | GWD number for lookup             |
| `source`       | "ILI Source", "Source", "Vendor"                            | ILI source (e.g. MFL-A)           |

### Girth welds

Rows with `feature_type` containing `"girth"` or `"gwd"` are treated as girth welds.
Stored attributes: `chainage`, `gwd_number`, `label` (e.g. "GWD 3180"), `source`.

Girth welds have **no angular orientation** — they are drawn as red vertical lines (2D) or rings (3D).

---

## 3. Joint Summary → Matrix parse and `seam_welds`

**File:** `backend/pipeline/dig_package_reader.py` — `build_feature_map_from_dig_package` calls `_parse_joint_summary_matrix` when `joint_df` is present.

### Step A — Discover GWD columns (`gwd_to_cols`)

The parser builds `gwd_to_cols: { gwd_number → [column_index, …] }` (left-to-right order).

1. **From headers** (`_discover_gwd_columns_from_headers`):
   - Split header text on spaces; each token may yield a GWD if it is an integer in **(100, 99999)**.
   - Tokens may include pandas duplicate suffixes: **`30900__2` is treated as GWD 30900** (suffix stripped before parsing).
   - If no token works, the code tries a **4–5 digit** match anywhere in the header string (`_gwd_int_from_text`).
   - **Multiple columns for the same GWD** (e.g. `30900` and `30900__2`) produce **`[col_a, col_b]`** for that GWD.

2. **Fallback** if fewer than **two distinct GWD keys**: scan **data rows** top to bottom; for each row, treat cells that parse as integers in **(100, 99999)** as GWD labels for those column indices. Stops at the first row that yields at least two column assignments in total.

If still fewer than two GWDs → matrix parse **fails** (`None`); the code may fall back to **row-based** Joint Summary parsing if it finds a dedicated longseam column (see below).

### Step B — Target GWD from headers (`target_gwd_from_header`)

Used for **positional** alignment between Feature Summary girth welds and Joint Summary GWD order when feature rows lack GWD numbers.

- Header normalised to lowercase equals **`target`** or starts with **`target `** → try to read a GWD from that header text; else map the column index to whichever GWD list contains it.
- Else any header containing **`target`** and **`gwd`** → `_gwd_int_from_text` on that header.

If nothing matches, positional logic falls back to the **middle** GWD in sorted Joint Summary order.

### Step C — Row types

Each data row is classified using the **first non-empty** of column 0 and column 1 (and optional **Source** column for naming).

| Condition | Action |
|-----------|--------|
| Label contains **“girth weld”** or **“joint”** + **“no”** | Skip (header/noise). |
| Label contains **“joint length”** (column A or B) | For **every** column index in `gwd_to_cols[gwd]`, read a float; if **0.5 < m < 200**, append to `joint_lengths_raw[gwd]`. **No orientation** from this row. The value under **GWD *N*** is treated as the length of the joint **from weld *N* toward the next weld** (upstream column convention). |
| Otherwise | Candidate **longseam** row (see Step D). |

### Step D — Longseam values (stacked vs interleaved)

A cell counts as a valid longseam reading only if `parse_orientation_to_hours` returns a value **and** (`_orientation_cell_accepted`):

- the string form contains **`:`** (clock style), **or**
- the numeric value is in **[0, 12]**.

So plain **metres** (e.g. 13.84) or coordinates are **not** accepted as longseam.

**Interleaved layout** (one row, **two vendors side-by-side per GWD**)

Activated only if **all** of the following hold:

- Every GWD has the **same** number of data columns `W`, and `W > 1`.
- The row’s longseam block label (column 0 or 1) matches **`_is_longseam_block_label`** (long seam / longseam / seam orientation, but not joint length).
- `_extract_sources_from_block_label` returns exactly **`W`** source names (from parentheses or extra lines in the merged label).

Then for source index `si` in `0 … W-1`, the parser reads `row.iloc[gwd_to_cols[gwd][si]]` for each GWD and fills **`by_source[source_name][gwd]`** for that ILI.

**Stacked layout** (classic)

If interleaved mode does **not** apply:

- Only **`gwd_to_cols[gwd][0]`** (first column per GWD) is used for clock values on that row.
- **Source name** comes from, in order: explicit **Source** column; else first/second cell if not a block label; else **block label** with `_extract_sources_from_block_label` and a **row counter per label** (first row → first source, second row → second source, …).

### Step E — Row-based Joint Summary fallback

If `_parse_joint_summary_matrix` returns `None`, the code looks for columns whose names match distance/chainage, longseam orientation keywords, and optional GWD — **one row per joint** — and builds a chainage-keyed map. This path is separate from the matrix logic above.

### Step F — `seam_welds` and positional GWD

**File:** `build_feature_map_from_dig_package`

Girth welds are sorted by chainage. For each consecutive pair `(GWD_i, GWD_{i+1})` at chainages `(ch_start, ch_end)`:

- If the **left** girth weld has a numeric `gwd_number`, use it to look up longseam in each Joint Summary source map (`_get_seam_hours_for_gwd`, with **±15** GWD tolerance on mismatch).
- If `gwd_number` is missing, build a **positional** map: align the girth weld list to sorted Joint Summary GWDs by offset from the **target** girth weld (closest chainage to 0) and the **target GWD** from Step B (or middle of list).

For **each** Joint Summary source that has a value for that GWD, append one `seam_weld` dict:

```python
{
    "chainage_start": ch_start,
    "chainage_end":   ch_end,
    "orientation_hours": oh,
    "orientation_label": "11:50",
    "source": "2022 Rosen",
    "feature_source": "...",
}
```

`scatter_data` may also receive `joint_lengths_by_gwd` and `gwd_order` from the matrix result when present.

### Step G — TGW layout from Joint Summary (preferred when possible)

**File:** `build_feature_map_from_dig_package` — `_build_tgw_layout_from_joint_summary`

When the matrix parse succeeds (`use_gwd_lookup`) **and** `joint_lengths` has usable values, this path **replaces** Feature Summary girth welds for plotting with **four** welds on the **Distance from TGW** axis:

1. Sort Joint Summary GWD ids (`gwd_order`).
2. Choose **target index** `it`: `target_gwd_from_header` if present in `gwd_order`, else **`(len(gwd_order) - 1) // 2`** so four consecutive welds exist (e.g. for four GWD columns this is index **1**, not `len // 2`).
3. Require **four consecutive GWDs**: `g0 = order[it−1] … g3 = order[it+2]` (needs `it ≥ 1` and `it + 2 < len(order)`).
4. **Segment lengths** (metres) between neighbours: `_segment_joint_length_m(joint_lengths, g_left, g_right)` — prefers the **upstream** GWD’s column (same as longseam: value under `GWD_i` applies to span toward `GWD_{i+1}`), then the downstream column as fallback.
5. Chainages (target GWD at **0**):

   - `ch(g1) = 0`
   - `ch(g0) = 0 − L(g0,g1)`
   - `ch(g2) = 0 + L(g1,g2)`
   - `ch(g3) = ch(g2) + L(g2,g3)`

6. **`scatter_data["girth_welds"]`** is set to these four dicts (`joint_summary_layout: true`, labels, optional `longseam_label_primary`).
7. **`scatter_data["seam_welds"]`** is rebuilt for the **three** spans between consecutive chainages; longseam for span `(g_i → g_{i+1})` uses the **upstream** GWD `g_i` in each Joint Summary source map (same as Step F). Each record may include **`gwd_number`** for annotations.

8. **`scatter_data["joint_summary_tgw_layout"] = true`**. Feature boxes are unchanged (still from Feature Summary x positions).

If any segment length is missing or fewer than four GWDs are available, this step is skipped and **Step F** (Feature Summary girth welds) is used instead.

---

## 4. Visualisation Behaviour

**Implementation:** `frontend/ili_visual_shared.py` — `_build_feature_map_figure` (2D), `_build_3d_pipeline_figure` (3D).

### 2D Feature Map (orientation vs chainage)

| Visual element            | Data source                         | Notes |
|---------------------------|-------------------------------------|-------|
| Feature boxes (defects)   | Feature Summary                     | Unchanged — chainage from distance column |
| **NDE grey band**         | `scatter_data["nde_region"]`        | **`add_vrect`** between `x0` and `x1`, semi-transparent grey, **`layer="below"`** defect rectangles |
| **NDE boundary lines**    | same                                | **Dashed vertical lines** at `x0` and `x1` (dark grey), drawn **after** red GWD lines so boundaries stay visible |
| **NDE labels**            | same                                | **Annotation** “NDE Area” centred in the band (high on the clock axis); **distance text** `{x:.3f} m` beside each boundary (`xshift` + `xanchor` left/right); **Plotly legend** entry “NDE Area” via a NaN-point `Scatter` swatch (right margin `y≈0.80`) |
| Red vertical lines        | **Joint Summary TGW layout** if Step G runs; else Feature Summary girth welds | Four lines at `0` and cumulative joint lengths when Step G applies |
| Coloured horizontal lines | Joint Summary → `seam_welds`        | One line per ILI source per joint span; annotations include **GWD #** and clock + source when present |
| Source labels (legend)    | Feature Summary                     | Each ILI run labelled |

**X-axis default range:** if `nde_region` is present, the initial **x-axis range** is merged so both defect extents and **`[x0, x1]`** (with padding) are visible (`_merge_nde_into_x_range`).

**Longseam line colours:** blue = first Joint Summary source alphabetically, purple = second, … (multiple vendors compare on the same span).

**TGW layout girth welds** are always shown in 2D even when a single ILI source is filtered (`joint_summary_layout` bypasses source filter for those four lines).

### 3D Pipeline View (cylinder heatmap)

| Visual element     | Source                    | Notes                                                |
|--------------------|---------------------------|------------------------------------------------------|
| Cylinder surface   | Feature Summary features  | Depth % WT heatmap                                   |
| **NDE sleeve**     | `nde_region`              | **Translucent grey `Surface`** on a **slightly larger radius** (~`pipe_r_m × 1.028`), chainage clipped to overlap **`[view_x_min, view_x_max]`** with `[x0, x1]` |
| **NDE boundaries** | same                      | **Dashed circumferential rings** at `x0` and `x1` (when inside scene range), radius ~`× 1.032`, drawn **after** red GWD rings |
| **Legend**         | NDE surface trace         | One entry: **“NDE assessment zone (TGW)”**; boundary lines use `showlegend=False` but share `legendgroup="nde_zone"` |
| Red rings          | `girth_welds` in `scatter_data` (TGW from Joint Summary when Step G applies, else Feature Summary) | One ring per boundary in that list |
| Coloured lines     | `seam_welds`              | One line per (span, Joint Summary source)           |
| Clock labels       | Fixed                     | 12 o’clock = top of pipe                             |

**Joint window:** `max_joints + 1` consecutive **girth-weld** chainages are chosen around the weld closest to **0**. With TGW layout, those chainages already include Joint Summary–derived welds; otherwise they come from Feature Summary rows. The NDE sleeve only covers the **intersection** of `[x0, x1]` with that window; if there is no overlap, the sleeve is omitted (boundaries still draw if `x0`/`x1` fall inside the scene).

---

## 5. Joint lengths (summary)

Same rule as **Step C**: **“joint length”** row(s) → numeric cells per GWD column → **`joint_lengths_by_gwd[gwd]`** = **mean** per GWD in **(0.5, 200)** m. Segment use in TGW layout: **upstream GWD** of each span (see Step G).

---

## 6. Known limitations (current code)

1. **Single header row** — The reader does not merge a **second** header row (e.g. group “US / Target / DS” above a row of GWD numbers). If GWD IDs are not on the same row that `_find_header_row_after` picks, discovery may fail or mis-label columns.
2. **Interleaved mode is strict** — Every GWD must have the **same** column count `W`, and the merged longseam label must expose exactly **`W`** source names. Mixed widths (e.g. one GWD missing a vendor column) disable interleaved parsing for that table; the stacked path then uses **only the first column** per GWD.
3. **Reshape is pattern-gated** — Templates whose first two headers are not duplicate “Girth Weld No.” / “Source” will not get Metric/Source normalisation from reshape (matrix parse may still work).
4. **Positional GWD mapping** — If Feature Summary omits GWD numbers, seam association depends on **sorted Joint Summary GWD order** and target anchoring; any mismatch vs real pipe order will skew longseam placement.
5. **Ring / line count** — In **TGW layout (Step G)**, 2D uses exactly **four** red lines / **three** joints when data allows. Otherwise count follows **Feature Summary** girth welds. 3D still slices the available `girth_welds` list (four welds → full window when centred on target at 0).
6. **NDE label/value layout** — Parser expects **leading text** then **first numeric** to the right on the same row. Rows where the value precedes the label, or multi-row merged values, may not match. **D/S-only** NDE rows are intentionally skipped for the TGW band.
7. **3D NDE** — Grey sleeve uses a second `Surface` and may **z-fight** slightly with the main cylinder depending on angle; boundary **dash** style for `Scatter3d` depends on Plotly/WebGL support.

---

## 7. Quick reference — functions

| Function | Role |
|----------|------|
| `parse_dig_package_excel` | Locate Feature/Joint table sections; per sheet, first hit for **`parse_nde_limits_section`**; read one header + data block each; reshape joint DF when pattern matches |
| `parse_nde_limits_section` | Find **NDE Limits** title; scan label/value rows → TGW start/end (and optional length, target GWD) |
| `_row_label_and_value` / `_parse_float_for_nde` | Helpers: one row → label string + value cell |
| `_reshape_joint_summary_dataframe` | Split merged metric+sources into Metric / Source columns |
| `_parse_joint_summary_matrix` | Build `gwd_to_cols`, parse longseam + joint lengths, `by_source`, `target_gwd_from_header` |
| `build_feature_map_from_dig_package` | Feature map + Joint Summary merge; sets **`scatter_data["nde_region"]`** and **`feature_summary_raw["nde_limits"]`** when Excel parse succeeds |
| `build_feature_map_from_df` | Feature Summary → features, `girth_welds`, scatter axes |
| `_build_feature_map_figure` | Plotly 2D: defects, NDE vrect/vlines, GWD vlines, seams, axis merge |
| `_build_3d_pipeline_figure` | Plotly 3D: cylinder, NDE sleeve + rings, GWD rings, seams, clock labels |
