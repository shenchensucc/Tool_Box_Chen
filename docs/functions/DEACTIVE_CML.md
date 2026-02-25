# De-active CML

## Overview

The De-active CML tool generates a dataloader that deactivates **all** CMLs included in the uploaded source sheet. Unlike the TML Data Loader's Status workflow (which filters for "To be de-active"), this tool processes every row in the sheet.

## Features

- **Single upload**: Only the source file is required
- **Optional template**: Use default TM_Loader_Template.xlsx or upload your own
- **Flexible column names**: Supports column header variations (e.g., "Circuit ID" vs "Circuit #")
- **Auto-detect sheet**: Tries `Source_Data` first, then scans all sheets for one with required columns
- **Output**: `{upload_filename}_deactive.xlsx` with Status Indicator = "Inactive"
- **Detailed errors**: Frontend and backend show status code, endpoint, and full error detail for debugging

## Required Columns

The source file must have **at least one sheet** with these columns (flexible naming via `COLUMN_ALIASES` in `backend/tml/excel_reader.py`):

| Canonical Name | Example Aliases |
|----------------|-----------------|
| Equipment ID   | Equipment #, Equip ID, EquipmentID |
| CML Group ID   | CML Group, TML Group ID, CMLGroupID |
| sub-CML ID     | Sub CML ID, TML_ID, TML ID, SubCMLID, CML ID, CML_ID, CMLID |

## Sheet Detection

- Prefers sheet named `Source_Data` if it has the required columns
- If not found or missing columns, iterates through all sheets
- Uses the first sheet that contains all required columns (or aliases)

## Output

- **Output column**: Status Indicator
- **Output value**: "Inactive"
- **Output file**: `{source_filename}_deactive.xlsx`
- **Response**: Includes `sheet_used` (Excel tab name read) for debugging

## Usage

1. Navigate to **Facility → De-active CML**
2. Upload your source Excel file (any sheet with required columns)
3. Optionally upload a custom TM_Loader template (or use default)
4. Click **Generate De-active Dataloader**
5. Download the output file

## Error Handling & Debugging

- **Frontend**: On error, shows HTTP status, endpoint URL, and full detail. For 404, suggests restarting the backend.
- **Backend**: Logs request params, tracebacks, and token/storage info for download failures.
- **API**: Errors include exception type and message; check server logs for full traceback.

## Technical Notes

- Excel reading: `backend/tml/excel_reader.py` — `read_excel_auto_sheet()` with `COLUMN_ALIASES`
- Template: `backend/static/templates/tml/TM_Loader_Template.xlsx` (default)
- Reuses `DataProcessor.append_and_save` from TML Data Loader for output generation
