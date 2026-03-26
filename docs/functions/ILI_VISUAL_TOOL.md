# 🛢️ ILI Visual Tool - Development Guide

## 📍 Function Location

- **Frontend**: `frontend/pages/3_ILI_Visual_Tool.py`
- **Backend**: `backend/main.py` (endpoints: `/api/ili/preview`, `/api/ili/process`, `/api/ili/parse-paste`)
- **Models**: `backend/models.py` (`PreviewResponse`, `ProcessResponse`, `FeatureMapResponse`)

---

## 🎯 Function Purpose

The **ILI (In-Line Inspection) Visual Tool** is a **visualization-only** tool. It enables engineers to:

1. Upload Excel files or paste tabular data containing pipeline inspection data
2. Visualize features along the pipeline (chainage vs depth)
3. Hover over features to see details (ID, type, depth, length, width, orientation)
4. Color-coded by depth (Viridis scale)

**No assessment, statistics, or analysis** — visualization only.

---

## 🏗️ Architecture

### Data Flow

**Upload mode:**
```
User Upload → /api/ili/preview → Preview (sheets, columns)
                ↓
         User Maps Columns, Clicks Process
                ↓
    /api/ili/process → Scatter plot (chainage vs depth)
```

**Paste mode:**
```
User pastes into Excel-like table → Clicks Generate
                ↓
    /api/ili/parse-paste → Feature map visualization
```

### Component Breakdown

#### Frontend (`3_ILI_Visual_Tool.py`)

1. **Input mode**: Upload Excel File | Paste from Clipboard

2. **Upload mode**
   - File uploader
   - Preview (sheets, columns, row counts)
   - Column mapping (distance, depth, metal loss)
   - Process button → Feature map only

3. **Paste mode**
   - Excel-like data editor (paste directly from Excel; column format preserved)
   - Generate button → Feature map only

4. **Visualization**
   - Interactive Plotly scatter plot
   - Feature boxes proportional to length/width when available
   - Color by depth (Viridis)
   - Hover tooltips with feature details

#### Backend (`main.py`)

1. **Preview** (`/api/ili/preview`) — Excel structure
2. **Process** (`/api/ili/process`) — Excel → scatter data (used for visualization)
3. **Parse-paste** (`/api/ili/parse-paste`) — Pasted text → features + scatter data

---

## 🔧 Key Functions

### Backend

- `parse_pasted_ili(pasted_text)` — Parses pasted CSV/tab data, uses `ili_reader.identify_ili_columns`, returns features for visualization
- `_parse_orientation_to_degrees(val)` — Converts clock format (e.g. 2:48) to degrees

### Frontend

- `call_parse_paste_api(pasted_text)` — Calls `/api/ili/parse-paste`
- `call_preview_api(file)` — Calls `/api/ili/preview`
- `call_process_api(...)` — Calls `/api/ili/process`

---

## ✅ Safe to Modify

- Visualization styles (colors, layouts)
- Column mapping UI
- Error messages

---

## 🚨 Do Not Add

- Statistics or assessment
- Histograms, box plots
- Export of analysis results

This tool is **visualization only**.

---

## 🔗 Related Documentation

- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [BACKEND_API.md](BACKEND_API.md)
- [DIG_PACKAGE_EXCEL_READING.md](../DIG_PACKAGE_EXCEL_READING.md) — dig package Excel (Joint Summary, TGW layout). Used by **Dig Package Visual Tool** (`frontend/pages/3_Dig_Package_Visual_Tool.py`); ILI Visual shares `ili_visual_shared.render_feature_map` for the map only.

---

**Last Updated**: February 2025  
**Function Version**: 0.2.0
