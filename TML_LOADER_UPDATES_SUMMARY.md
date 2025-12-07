# TML Data Loader - Updates Summary

## ✅ Implementation Complete

All planned features have been successfully implemented for the TML Data Loader tool.

## 🎯 New Features

### 1. Blank Template Downloads
Users can now download two blank template files directly from the TML Data Loader page:
- **Source Data Template** - Reference for preparing source data with correct columns
- **TM_Loader Template** - Reference for the template file structure

**Location in UI**: Top of the page, under "Download Blank Templates" section

### 2. Combined Export Option
Users now have two download options after processing:
- **Separate Files (ZIP)** - Individual Excel files for each workflow (existing functionality)
- **Combined File (XLSX)** - Single Excel file with all workflow data combined (new feature)

**How it works**: 
- Both files are generated during processing
- Two download buttons appear side-by-side
- Users can download either or both formats

## 📁 Files Modified

### Backend
1. **backend/main.py**
   - Added template download endpoint: `GET /api/tml/download-template/{template_type}`
   - Modified process endpoint: `POST /api/tml/process` (now returns JSON with tokens)
   - Added download endpoint: `GET /api/tml/download/{file_token}`
   - Added file storage mechanism for temporary files

2. **backend/models.py**
   - Added `TMLProcessResponse` model for new API response format

3. **backend/tml/data_processor.py**
   - Added `create_combined_output()` method to combine multiple workflow outputs

### Frontend
4. **frontend/pages/2_TML_Data_Loader.py**
   - Added template download section with two download buttons
   - Updated processing logic to handle token-based responses
   - Replaced single download button with dual download buttons (ZIP + Combined)

### Documentation
5. **docs/functions/TML_DATA_LOADER.md**
   - Updated features list
   - Added template download instructions
   - Updated usage instructions with new step numbering
   - Documented both export options
   - Updated API documentation with new endpoints
   - Added template setup guide for administrators
   - Updated version history

### Directory Structure
6. **backend/static/templates/tml/**
   - Created new directory for template files
   - Added README.md with instructions

## 🚨 ACTION REQUIRED

### You need to provide two template files:

1. **Source_Data_Template.xlsx**
   - Place in: `backend/static/templates/tml/Source_Data_Template.xlsx`
   - Should contain: "Source_Data" sheet with all required column headers
   - Required columns:
     - Equipment ID
     - CML Group ID
     - sub-CML ID
     - AER_Status_CML
     - (Plus workflow-specific columns like CorrValue_Design_Code, CorrValue_Material, etc.)

2. **TM_Loader_Template.xlsx**
   - Place in: `backend/static/templates/tml/TM_Loader_Template.xlsx`
   - Should contain: "Assets" and "TML" sheets with proper column structure
   - Assets sheet columns: Equipment ID, CMMS System
   - TML sheet columns: TML Group ID, TML_ID, CMMS System, TML Analysis Type, (parameter fields)

### File Location
```
backend/
  static/
    templates/
      tml/
        README.md (✅ already created)
        Source_Data_Template.xlsx (❌ you need to add this)
        TM_Loader_Template.xlsx (❌ you need to add this)
```

## 🧪 Testing Checklist

Once you add the template files, test the following:

1. **Template Downloads**
   - [ ] Start backend server
   - [ ] Navigate to TML Data Loader page
   - [ ] Click "Download Source Data Template" - should download Source_Data_Template.xlsx
   - [ ] Click "Download TM_Loader Template" - should download TM_Loader_Template.xlsx

2. **Processing with Dual Export**
   - [ ] Upload source and template files
   - [ ] Select multiple workflows (e.g., 4, 5, 7, 12)
   - [ ] Click "Process TML Data"
   - [ ] Verify both download buttons appear
   - [ ] Download ZIP file - verify it contains separate Excel files for each workflow
   - [ ] Download Combined file - verify it has one Assets sheet and one TML sheet with all data

3. **Data Validation**
   - [ ] Open combined file
   - [ ] Verify Assets sheet has deduplicated Equipment IDs from all workflows
   - [ ] Verify TML sheet has all TML records from all workflows concatenated
   - [ ] Verify column widths are set to 20
   - [ ] Verify data integrity (no missing records)

## 📊 API Changes

### New Endpoints

1. **GET /api/tml/download-template/{template_type}**
   - Parameters: `template_type` = "source" or "tm_loader"
   - Returns: Excel template file

2. **GET /api/tml/download/{file_token}**
   - Parameters: `file_token` from process response
   - Returns: ZIP or Excel file

### Modified Endpoint

**POST /api/tml/process**
- **Before**: Returned ZIP file directly (FileResponse)
- **After**: Returns JSON with tokens:
  ```json
  {
    "success": true,
    "message": "TML data processed successfully",
    "zip_token": "uuid-for-zip",
    "combined_token": "uuid-for-combined",
    "workflows_processed": 4,
    "timestamp": "2025-12-07T..."
  }
  ```

## 🔄 Data Flow

```
User Action: Upload files + select workflows
  ↓
Backend: Process all workflows
  ↓
Generate:
  - Individual Excel files (one per workflow)
  - ZIP file (all individual files)
  - Combined Excel file (all data merged)
  ↓
Store files with unique tokens
  ↓
Return tokens to frontend
  ↓
User: Choose download format
  ↓
Frontend: Request file using token
  ↓
Backend: Return requested file
```

## 💡 Benefits

1. **Better UX**: Users can download reference templates without searching
2. **Flexibility**: Users choose export format based on their needs
3. **Efficiency**: Single upload generates both export formats
4. **Simplicity**: Combined file reduces complexity for users who want consolidated data

## 📚 Documentation

Full documentation updated in:
- `docs/functions/TML_DATA_LOADER.md` - Complete user guide with all new features

## ⚙️ Technical Notes

- File tokens use UUID4 for uniqueness
- Files stored in temp directory (in-memory storage for tokens)
- Combined file uses pandas concatenation with deduplication for Assets
- All column widths standardized to 20 for readability
- Backward compatible: Existing API consumers can adapt to new JSON response

---

**Next Steps:**
1. Add the two template Excel files to `backend/static/templates/tml/`
2. Test the template downloads
3. Test the dual export functionality
4. Deploy and notify users of the new features!

