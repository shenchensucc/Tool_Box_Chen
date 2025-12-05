# Dig Package Generator - Implementation Summary

## Overview

The Dig Package Generator has been successfully implemented as a new sub-page within the Pipeline section. This tool replicates the VBA Excel tool functionality, generating dig package Excel and PDF files from three source files:

1. **MDL (Master Dig List)** - Contains dig IDs and target features
2. **ILI (In-Line Inspection) Data** - Detailed feature information
3. **Template** - Fillable Excel template with named ranges

## Files Created

### Backend
- **`backend/pipeline/dig_package.py`** (750+ lines)
  - Core logic for parsing, matching, and generating dig packages
  - Column keyword matching system
  - MDL and ILI file parsing
  - Feature matching (by ID and dimensions)
  - Template population using named ranges
  - Excel to PDF conversion
  - ZIP file packaging

### Frontend
- **`frontend/pages/5_Dig_Package_Generator.py`** (260+ lines)
  - User interface for file upload
  - Configuration options (revision number)
  - Progress indicators
  - Download functionality
  - Comprehensive help documentation

## Files Modified

### Backend
- **`backend/main.py`**
  - Added import: `from backend.pipeline.dig_package import generate_dig_packages`
  - Added endpoint: `POST /api/pipeline/dig-package/generate`
  - Accepts 3 Excel files + revision number
  - Returns ZIP file with all dig packages

### Frontend
- **`frontend/frontend_utils.py`**
  - Added navigation link: "📦 Dig Package Generator" under Pipeline section

### Dependencies
- **`requirements.txt`**
  - Added: `pywin32>=306; sys_platform == 'win32'` for Windows PDF conversion
  - Note: openpyxl was already present

## Key Features Implemented

### 1. Flexible Column Matching
- Uses keyword lists to find columns in source files
- Case-insensitive matching
- Supports multiple naming conventions
- Handles both metric and imperial units

### 2. Feature Matching
Two methods for matching MDL target features with ILI features:

**Method A: Feature ID Matching (Primary)**
- Direct match when Feature ID is available
- Most reliable method

**Method B: Dimension Matching (Fallback)**
- Matches by Length and Width
- Rounded to 3 decimal places
- Used when Feature ID is missing or for Rosen-type data

### 3. Template Population
- Uses Excel named ranges for flexibility
- Populates single-value fields (Dig ID, pipe properties, etc.)
- Populates excavation summary sections
- Dynamically generates feature table with multiple rows
- Applies formatting (bold, red, grey) to target features

### 4. Output Generation
- Creates individual Excel file for each Dig ID
- Converts Excel to PDF (Windows only, using COM automation)
- Naming convention: `{DigID}_DP_R{revision}.xlsx/pdf`
- Packages all files in a single ZIP for download

## How to Use

### 1. Start the Backend Server
```bash
cd C:\Users\cshen\Documents\Tool_Box_Chen
uv run uvicorn backend.main:app --reload
```

### 2. Start the Frontend
```bash
cd C:\Users\cshen\Documents\Tool_Box_Chen
streamlit run frontend/Home.py
```

### 3. Navigate to the Tool
- Go to http://localhost:8501
- Click on Pipeline section in sidebar
- Select "📦 Dig Package Generator"

### 4. Upload Files
- Upload MDL (Master Dig List) Excel file
- Upload ILI Data Excel file
- Upload Template Excel file

### 5. Configure
- Set revision number (default: 1)

### 6. Generate
- Click "🚀 Generate Dig Packages"
- Wait for processing (may take a few minutes for large files)
- Download the ZIP file containing all dig packages

## Template Requirements

The template Excel file must have these named ranges defined:

### Single-Value Fields
- `tmp_DigID_` - Dig ID
- `tmp_revNum` - Revision number
- `tmp_dddIss` - Date issued
- `tmp_pipNme` - Pipeline name
- `tmp_pipeOD` - Pipe outer diameter
- `tmp_pipeNWT` - Pipe nominal wall thickness
- `tmp_mop` - Maximum operating pressure
- `tmp_sep` - Safe excavation pressure
- `tmp_Lat`, `tmp_Lon` - Coordinates
- `tmp_mp_` - Milepost
- `tmp_tarGWsPipYer` - Pipe year
- `tmp_tarGWsPipGrd` - Pipe grade
- `tmp_ILI_Run_Name` - ILI run name
- `tmp_ILI_Run_Name_Acc` - ILI run accuracy
- `US_AGM`, `DS_AGM` - AGM values
- `tmp_tarGrtWld` - Target girth weld
- `tmp_numExv` - Number of excavations

### Summary Sections
- `tmp_numExv_num` - Excavation label (+ rows for length, start, end)
- `tmp_numExp_num` - Exposure label (+ rows for length, start, end)

### Feature Table
- `tmp_feaIDs_row` - Starting row for feature table (data starts 2 rows below)

To view/edit named ranges in Excel: **Formulas** tab → **Name Manager**

## Column Matching Keywords

The tool searches for columns using keyword lists. Here are the main ones:

### MDL Columns
- **Dig ID**: "Dig Name", "Dig ID", "DigName", "NEW Dig Name"
- **Feature ID**: "ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"
- **Pipeline Name**: "Pipeline Name", "Pipeline_Name", "PipelineName"
- **Pipe OD**: "Pipe OD", "Pipe_OD", "PipeOD", "OD (mm)"
- **Pipe NWT**: "Pipe NWT", "Pipe_NWT", "PipeNWT", "Nominal Wall Thickness (mm)"
- And many more... (see plan document for full list)

### ILI Columns
- **Feature ID**: "ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"
- **Feature Type**: "Feature Type", "Feature", "Event", "Anomaly Type"
- **Feature Depth**: "Depth (%)", "Max Depth", "Peak Depth", "Feature Depth"
- **ILI Chainage**: "ILI Chainage (m)", "Odometer (m)", "Log Distance"
- And many more...

## Known Limitations

1. **PDF Conversion**: Requires Windows with Excel COM automation (pywin32)
   - On non-Windows systems, PDF files won't be generated (only Excel)
   - Can be enhanced with cross-platform solutions (weasyprint, reportlab)

2. **ILI Range Filtering**: Currently simplified
   - The full girth weld range filtering (3 upstream to 3 downstream) is not fully implemented
   - All ILI data is processed for now
   - Can be enhanced based on VBA logic (GetILIData function)

3. **Target Girth Weld Extraction**: Currently set to 0.0
   - Should be extracted from ILI data based on joint number
   - Can be enhanced to properly locate target girth weld chainage

## Testing Checklist

Before using with production data, test with sample files:

- [ ] Upload all three files successfully
- [ ] Verify revision number is applied
- [ ] Check that valid Dig IDs are extracted (must contain "GW")
- [ ] Verify feature matching is working (check target feature highlighting)
- [ ] Confirm Excel files are generated
- [ ] Check PDF conversion (Windows only)
- [ ] Verify ZIP file downloads correctly
- [ ] Extract and inspect generated dig packages
- [ ] Validate data accuracy in output files

## Troubleshooting

### Error: "No valid Dig IDs found"
- Check that MDL has Dig ID column
- Ensure Dig IDs contain "GW" in the text

### Error: "Named range not found"
- Verify template has all required named ranges defined
- Check spelling of named range names (case-sensitive)

### Features Not Matching
- Check if Feature IDs exist in both MDL and ILI
- Verify dimensions (length/width) match when Feature ID is missing
- Check that values are rounded to same precision

### PDF Not Generated
- Requires Windows with Microsoft Excel installed
- Install pywin32: `pip install pywin32`
- Check that Excel COM automation is accessible

### Large File Processing
- May take several minutes for large datasets
- Backend timeout is set to 5 minutes (300 seconds)
- Consider processing in smaller batches if needed

## Next Steps

To enhance the tool further, consider:

1. **Full Girth Weld Range Filtering**
   - Implement the logic from VBA GetILIData function
   - Find 3 upstream and 3 downstream girth welds
   - Filter ILI data to this range

2. **Target Girth Weld Extraction**
   - Locate target girth weld in ILI data
   - Use for distance calculations in feature table

3. **Cross-Platform PDF Conversion**
   - Implement weasyprint or reportlab fallback
   - Convert Excel formatting to HTML/CSS

4. **Progress Tracking**
   - Show progress bar for each Dig ID being processed
   - Display current status during generation

5. **Validation Reports**
   - Generate summary of matched vs unmatched features
   - List any missing columns or data issues

6. **Batch Processing Options**
   - Select specific Dig IDs to process
   - Skip or include certain features

## Support

For issues or questions:
1. Check the Help section in the UI (ℹ️ icon)
2. Review the plan document: `dig-package.plan.md`
3. Check VBA source code: `C:\Users\cshen\Documents\NC_Dig_package_Tool\VBA.txt`
4. Review implementation: `backend/pipeline/dig_package.py`

---

**Implementation Date**: November 18, 2024
**Status**: ✅ Complete and Ready for Testing

