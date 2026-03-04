# Dig Package Excel Reading — Data Flow

## Overview

The dig package Excel has **two main sections** that we read:

1. **Feature summary** — ILI features (defects, girth welds, etc.)
2. **Joint Summary** — GWD positions and **longseam orientation** per joint

**Girth welds have no orientation** (they are circumferential, 360°). The **longseam orientation** is the orientation of the pipe’s longitudinal seam and comes from the **Joint Summary** section, not from the Feature summary.

---

## 1. Excel Reading: `parse_dig_package_excel`

**File:** `backend/pipeline/dig_package_reader.py`

```
parse_dig_package_excel(file_content: bytes)
    → (feature_df, joint_df, metadata)
```

### How it works

1. Load workbook with `openpyxl` (`data_only=True`).
2. Loop over all sheets.
3. For each sheet:
   - **Feature summary:** Find a row whose text contains `"feature summary"` (or similar). Treat the next row with multiple non-empty cells as the header row. Read the table from that header row down until the first empty row.
   - **Joint Summary:** Same idea, but search for `"joint summary"` (or similar).
4. Return two DataFrames: `feature_df` (Feature summary table) and `joint_df` (Joint Summary table).

### Section detection

| Section        | Header keywords                                      |
|----------------|------------------------------------------------------|
| Feature summary| `"feature summary"`, `"feature summary table"`, `"ili feature summary"` |
| Joint Summary  | `"joint summary"`, `"joint summary table"`, `"girth weld summary"` |

### Column detection

Columns are matched by **header text** (case-insensitive, substring match). No fixed cell addresses are used.

---

## 2. Feature Summary → Features and Girth Welds

**File:** `backend/pipeline/feature_map_builder.py` — `build_feature_map_from_df(feature_df, ili_cols)`

### Column mapping (from `ili_reader.COLUMN_KEYWORDS` and `identify_ili_columns`)

| Standard key   | Example Excel headers                                      | Used for                          |
|----------------|------------------------------------------------------------|-----------------------------------|
| `distance`     | "Distance from TGW (m)", "ILI Chainage (m)", "Chainage"    | x-axis (chainage)                 |
| `depth`        | "Depth (%)", "Feature Depth", "Max. Depth"                 | Feature depth                     |
| `length`       | "Length (mm)", "Feature Length"                            | Box length                        |
| `width`        | "Width (mm)", "Feature Width"                              | Box width                         |
| `feature_id`   | "Feature ID", "ID#", "Joint"                               | Feature ID                        |
| `feature_type` | "Feature Type", "Type"                                     | Girth Weld vs defect vs seam      |
| `orientation`  | "Orientation (hh:mm)", "Feature Orientation"               | Defect orientation (not longseam) |
| `joint_number` | "Joint", "GWD", "Joint Number"                             | GWD number                        |
| `source`       | "ILI Source", "Source", "Vendor"                           | ILI source (e.g. MFL-A)           |

### Seam orientation in Feature summary

`feature_map_builder` also looks for a column whose name contains both `"seam"` and `"orientation"` (e.g. `"Longseam Orientation"`, `"Seam Orientation"`). If present, it is used as `seam_orient_col` for girth weld rows.

**Important:** Girth weld rows in the Feature summary often have no orientation column or use `"-"` because girth welds are circumferential. The main source of longseam orientation is the **Joint Summary** section.

### Data produced per row

- **x** — from `distance` column (chainage / Distance from TGW)
- **depth** — from `depth` column (0 for girth welds)
- **length, width** — from `length`, `width` columns
- **orientation_hours** — from `orientation` column (defect orientation; default 6.0 if missing)
- **feature_type** — from `feature_type` column (e.g. "Girth Weld", "GirthWeld")
- **gwd_number** — from `joint_number` or GWD column
- **seam_orient_hours** — from seam orientation column in Feature summary, if present
- **source** — from `source` column

### Girth welds

Rows with `feature_type` containing `"girth"` or `"gwd"` are treated as girth welds. For these we store:

- `chainage` (x)
- `gwd_number`
- `label` (e.g. "GWD 1410")
- `source`

Girth welds do **not** get orientation from the Feature summary; they are drawn as vertical lines.

---

## 3. Joint Summary → Target GWD Longseam (Merged into Feature Summary)

**File:** `backend/pipeline/dig_package_reader.py` — `build_feature_map_from_dig_package`

Joint Summary is parsed to extract **only the target GWD's longseam**. This is merged into the Feature Summary data source (no separate Joint Summary section in the UI).

### Target GWD selection

- **Matrix layout:** Middle GWD in the sorted list (e.g. 3180 when GWDs are 3150–3210).
- **Row-based layout:** Row with Distance to Target = 0.

### Column mapping for Joint Summary

| Standard use        | Example Excel headers                                      |
|---------------------|------------------------------------------------------------|
| Distance to target  | "Distance from TGW (m)", "Distance to Target"              |
| Chainage            | "Chainage", "ILI Chainage (m)", "Odometer"                 |
| **Longseam orientation** | "Long Seam Orientation for the Target", "Longseam Orientation", "Seam Orientation" |
| GWD                 | "GWD", "Joint", "Joint Number"                             |

### Supported structures

**Matrix (GWDs as columns):** First row has GWD numbers (3150, 3160, 3170, …). Data rows have ILI source (e.g. "2022 Rosen", "2025 TDW") and longseam values per GWD. Target = middle GWD.

**Row-based:** One row per GWD. Target = row with Distance to Target = 0.

### Output

- **Target GWD** and **target longseam** are added to `feature_summary_raw`.
- **Per-span blue lines:** For each span [GWD_i, GWD_{i+1}], draw a blue line at D/S longseam of GWD_i. When the longseam passes a GWD (after joint length), use GWD+1's longseam for the next span.

---

## 4. Summary: Where Each Value Comes From

| Visual element        | Data source        | Excel section   | Column(s)                                      |
|-----------------------|-------------------|-----------------|------------------------------------------------|
| Feature boxes (defects)| Feature summary   | Feature summary | distance, depth, length, width, orientation    |
| Girth weld lines (red)| Feature summary   | Feature summary | distance, feature_type, joint_number, source   |
| Longseam line (blue)  | Joint Summary     | Joint Summary   | Target GWD longseam (merged into Feature Summary) |
| Source labels         | Feature summary   | Feature summary | source                                         |

**Girth welds:** Position (chainage) and GWD from Feature summary. No orientation.

**Longseam orientation:** From Joint Summary. Per-span blue lines: D/S longseam of GWD_i for span [GWD_i, GWD_{i+1}].
