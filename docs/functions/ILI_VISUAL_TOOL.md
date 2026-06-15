# ILI Visual Tool — workflow & implementation

## Locations

- **Frontend UI**: `frontend/pages/3_ILI_Visual_Tool.py` (entry) · shared logic `frontend/ili_visual_shared.py`
- **Backend**: `backend/main.py` — `POST /api/ili/process-feature-map`, `POST /api/ili/preview`, `POST /api/ili/parse-paste`
- **GWD pre-filter**: `backend/pipeline/feature_map_builder.py` — `gwd_chainage_anchor_pairs`, `compute_chainage_bounds_for_gwd_filter`, `filter_df_by_chainage_window`; constant `GWD_CENTER_ADJACENT_GWDS` (±2 welds → up to **5 joints**)
- **API client**: `frontend/frontend_utils.py` — `call_process_feature_map_api`

## Purpose

Visualization only: pipeline ILI (or pipe tally) in chainage × orientation / depth views. No assessment or statistics.

---

## Upload workflow (intended behavior)

1. **Upload** the ILI source workbook (`.xlsx` / `.xls`).
2. Choose **table source**:
   - **Auto-detect (vendor format)** — same ILI layouts as Dig Package (`vendor_format`).
   - **Choose sheet manually** — **Preview File** → pick sheet → then load.
3. **Optional scan** (collapsed expander): `survey_only=true` — distinct GWD list + row count, **no** feature geometry. Helps pick numbers for the next step; **not required** to load.
4. **GWD scope** (sent to backend on **Load**):
   - **Center GWD** — user enters one GWD number. Backend sorts GWDs by chainage, finds that joint, keeps **± `GWD_CENTER_ADJACENT_GWDS`** neighbors (default **2** → **5 joints**), computes chainage min/max, **filters the DataFrame**, then builds features.
   - **GWD range** — **start** and/or **end** GWD (integers; blank side anchors to file min/max chainage). Backend filters rows to that inclusive chainage span, then builds.
   - **Full file** — no GWD parameters; builds from all parsed rows (can be slow on large ILIs).
5. After the map appears, **Zoom to section** filters the **already-loaded** features in the browser (no re-upload).

### API parameters (`POST /api/ili/process-feature-map`)

| Form field       | Meaning |
|------------------|---------|
| `vendor_format`  | Set for auto mode OR |
| `sheet_name`     | Set for manual sheet mode |
| `data_format`    | Optional: `anomaly`, `pipe_tally`, etc. |
| `survey_only`    | `1` = survey only |
| `gwd_center`     | Center weld; ±adjacent along chainage-sorted list |
| `gwd_start` / `gwd_end` | Inclusive range by GWD numbers → chainages |

Paste mode still uses `parse-paste` and does not use this GWD upload flow.

---

## Architecture sketch

```
Upload → optional preview (manual) → optional survey_only
     → Load with gwd_center | gwd_start/gwd_end | (none = full)
     → backend: anchor pairs → chainage bounds → filter_df → build features
     → Streamlit: feature map + local zoom
```

---

## Safe to change

- Plot styling, labels, expander copy  
- Zoom UI (client-side only)

## Do not add here

- Assessment, KPIs, export of engineering conclusions  
- Non–Azure OCR paths (project uses Azure Document Intelligence only for other flows)

---

## Related docs

- `docs/DIG_PACKAGE_EXCEL_READING.md` — vendor Excel conventions  
- `CLAUDE.md` — local run: backend `uvicorn backend.main:app --reload`, frontend `streamlit run frontend/Home.py`

**Last updated**: May 2026
