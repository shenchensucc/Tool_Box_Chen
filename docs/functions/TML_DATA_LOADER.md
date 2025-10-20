# TML Data Loader

## Overview

The TML (Thickness Monitoring Location) Data Loader is a powerful tool for processing and updating TML data in batch. It allows users to process up to 20 different design parameters and static data fields simultaneously, generating formatted output files for each selected workflow.

## Purpose

This tool streamlines the process of updating TML data by:
- Processing multiple parameters in a single operation
- Generating properly formatted output files
- Maintaining data integrity across Assets and TML sheets
- Providing flexible workflow selection for customized processing

## Features

- **Batch Processing**: Process multiple workflows simultaneously
- **20 Available Workflows**: Cover all major TML design parameters
- **File-Based Processing**: Upload source and template files, download results
- **Privacy-Focused**: Files are processed in memory and not stored on the server
- **User-Friendly Interface**: Checkbox-based workflow selection with descriptions
- **Error Handling**: Gracefully handles errors in individual workflows

## Input File Requirements

### Source Data File (input.xlsx)

The source file must contain:
- **Sheet Name**: `Source_Data`
- **Required Column**: `AER_Status_CML` (only records containing "Yes" will be processed)
- **Equipment Columns**:
  - `Equipment ID` (preserved as string to maintain leading zeros)
  - `CML Group ID`
  - `sub-CML ID`
- **Parameter Columns**: Depends on selected workflows (see workflow details below)

### Template File (TM_Loader.xlsx)

The template file must contain:
- **Assets Sheet**: Contains equipment-level data
  - `Equipment ID`
  - `CMMS System`
- **TML Sheet**: Contains TML-level data
  - `TML Group ID`
  - `TML_ID`
  - `CMMS System`
  - `TML Analysis Type`
  - Various parameter fields

## Available Workflows

### 01. Sub-CML Status (Deactivated)
- **Purpose**: Mark TMLs for deactivation
- **Source Column**: `AER_Status_CML` (filters for "To be de-active")
- **Output Column**: `Status Indicator` = "Inactive"
- **Output File**: `01_TM_Loader_Status.xlsx`

### 02. AER Flag
- **Purpose**: Flag TMLs for AER section follow-up
- **Source Column**: `AER_Status_CML` (filters for "Yes")
- **Output Columns**: 
  - `Follow Up TML` = "True"
  - `TML Comment` = "Follow up TML Flag - intended for AER section CML"
- **Output File**: `02_TM_Loader_FollowUp.xlsx`

### 03. Code Year T-Min Formula
- **Purpose**: Update code year for minimum thickness formula
- **Source Column**: `Code Year (T-Min Formula)` (filters for non-"N/A" values)
- **Output Column**: `Code Year (T-Min Formula)` = "N/A"
- **Output File**: `03_TM_Loader_CodeYearTmin.xlsx`

### 04. Design Code
- **Purpose**: Update design code values
- **Source Column**: `CorrValue_Design_Code` (non-empty, non-zero)
- **Output Column**: `Design Code`
- **Output File**: `04_TM_Loader_DC.xlsx`

### 05. Material Specification
- **Purpose**: Update material specification
- **Source Column**: `CorrValue_Material` (non-empty, non-zero)
- **Output Column**: `Material Specification`
- **Output File**: `05_TM_Loader_MaterialSpec.xlsx`

### 06. Material Grade
- **Purpose**: Update material grade
- **Source Column**: `CorrValue_Grade` (non-empty, non-zero)
- **Output Column**: `Material Grade`
- **Output File**: `06_TM_Loader_MaterialGrad.xlsx`

### 07. Design Temperature
- **Purpose**: Update design temperature values
- **Source Column**: `CorrValue_T` (non-empty, non-zero)
- **Output Column**: `Design Temperature`
- **Output File**: `07_TM_Loader_T.xlsx`

### 08. Piping Formula
- **Purpose**: Standardize piping formula to "E"
- **Source Column**: `Piping Formula` (filters for non-"E" values)
- **Output Column**: `Piping Formula` = "E"
- **Output File**: `08_TM_Loader_PF.xlsx`

### 09. Outside Diameter (OD)
- **Purpose**: Update outside diameter values
- **Source Column**: `CorrValue_OD` (non-empty, non-zero)
- **Output Column**: `Outside Diameter`
- **Output File**: `09_TM_Loader_OD.xlsx`

### 10. NPS (Nominal Pipe Size)
- **Purpose**: Update nominal pipe size
- **Source Column**: `CorrValue_NPS` (non-empty, non-zero)
- **Output Column**: `Piping Nominal Diameter - NPS`
- **Output File**: `10_TM_Loader_NPS.xlsx`

### 11. Schedule
- **Purpose**: Update pipe schedule
- **Source Column**: `CorrValue_Schedule` (non-empty, non-zero)
- **Output Column**: `Schedule`
- **Output File**: `11_TM_Loader_Schedule.xlsx`

### 12. Design Pressure
- **Purpose**: Update design pressure values (rounded to integer)
- **Source Column**: `CorrValue_P` (non-empty, non-zero)
- **Output Column**: `Design Pressure` (rounded to 0 decimals)
- **Output File**: `12_TM_Loader_P.xlsx`

### 13. Temperature Coefficient
- **Purpose**: Standardize temperature coefficient to 1
- **Source Column**: `Temperature Coefficient` (filters for non-1 values)
- **Output Column**: `Temperature Factor` = 1
- **Output File**: `13_TM_Loader_TempCoef.xlsx`

### 14. Tnom (Nominal Thickness)
- **Purpose**: Update nominal thickness
- **Source Column**: `CorrValue_Tnom` (non-empty, non-zero)
- **Output Column**: `TNominal Thickness`
- **Output File**: `14_TM_Loader_Tnom.xlsx`

### 15. Tmin (Minimum Thickness)
- **Purpose**: Update minimum thickness
- **Source Column**: `CorrValue_Tmin` (non-empty, non-zero)
- **Output Column**: `Minimum Thickness`
- **Output File**: `15_TM_Loader_Tmin.xlsx`

### 16. Override Allowable Stress
- **Purpose**: Enable allowable stress override
- **Source Column**: `Override Allowable Stress` (filters for non-True values)
- **Output Column**: `Override Allowable Stress` = "True"
- **Output File**: `16_TM_Loader_OAS.xlsx`

### 17. Allowable Stress
- **Purpose**: Update allowable stress values
- **Source Column**: `AER_SMYS` (non-empty, non-zero)
- **Output Column**: `Allowable Stress`
- **Output Files**: 
  - `17_TM_Loader_AllowableStress.xlsx` (filtered records)
  - `17_TM_Loader_AllowableStress_All.xlsx` (all records)

### 18. Design Factor
- **Purpose**: Standardize design factor to 0.8
- **Source Column**: `Design Factor` (filters for non-0.8 values)
- **Output Column**: `Design Factor` = 0.8
- **Output File**: `18_TM_Loader_DesignFactor.xlsx`

### 19. Joint Factor
- **Purpose**: Standardize joint factor to 1
- **Source Column**: `Joint Factor` (filters for non-1 values)
- **Output Column**: `Joint Factor` = 1
- **Output File**: `19_TM_Loader_JointFactor.xlsx`

### 20. Location Factor
- **Purpose**: Update location factor
- **Source Column**: `CorrValue_LocFactor` (non-empty, non-zero)
- **Output Column**: `Location Factor`
- **Output File**: `20_TM_Loader_LocationFatcor.xlsx`

## Usage Instructions

### 1. Access the Tool
Navigate to the TML Data Loader page in the application:
```
http://localhost:8501/TML_Data_Loader
```

### 2. Upload Files
- **Source File**: Upload your input Excel file containing TML data
- **Template File**: Upload the TM_Loader.xlsx template file

### 3. Select Workflows
- Review the 20 available workflows
- Check the boxes for workflows you want to process
- Use "Select All" or "Deselect All" buttons for convenience

### 4. Process Data
- Click the "Process TML Data" button
- Wait for processing to complete (typically 30 seconds to a few minutes)
- Processing time depends on:
  - File size
  - Number of workflows selected
  - Number of records to process

### 5. Download Results
- Click the "Download Output Files (ZIP)" button
- Extract the ZIP file to access individual Excel files
- Each file is named according to its workflow number (e.g., `01_TM_Loader_Status.xlsx`)

## Output File Structure

Each output file contains:
- **Assets Sheet**: Updated equipment-level data
  - Equipment IDs (with leading zeros preserved)
  - CMMS System = "P1R-100"
  - Deduplicated entries
  
- **TML Sheet**: Updated TML-level data
  - TML Group IDs and TML IDs
  - CMMS System = "P1R-100"
  - TML Analysis Type = "TML"
  - Updated parameter values

## Data Processing Details

### Filtering Logic
1. Source data is first filtered for `AER_Status_CML` containing "Yes"
2. Each workflow applies additional filtering based on its specific requirements
3. Only records meeting the filter criteria are included in output

### Data Merging
- Template data from Assets and TML sheets is preserved
- Processed data is appended to template data
- Duplicate equipment IDs in Assets sheet are removed
- All TML records are preserved (including duplicates if present in source)

### Column Formatting
- All output columns are set to width = 20 for consistent display
- Equipment IDs are stored as strings to preserve leading zeros
- Numeric values maintain their precision (except where rounding is specified)

## API Endpoint

### POST /api/tml/process

Process TML data with selected workflows.

**Request:**
- `source_file`: Uploaded source Excel file
- `template_file`: Uploaded template Excel file
- `workflows`: Comma-separated list of workflow IDs (e.g., "1,2,7,12")

**Response:**
- ZIP file containing all generated output files
- HTTP 200 on success
- HTTP 400 on validation errors
- HTTP 500 on processing errors

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/api/tml/process" \
  -F "source_file=@input.xlsx" \
  -F "template_file=@TM_Loader.xlsx" \
  -F "workflows=1,2,7,12" \
  -o TML_Output.zip
```

## Error Handling

### Common Errors and Solutions

**Error: "Source file must contain sheet 'Source_Data'"**
- Solution: Ensure your source file has a sheet named exactly "Source_Data"

**Error: "Template file must contain sheets 'Assets' and 'TML'"**
- Solution: Verify your template file structure

**Error: "No records found matching the criteria"**
- Solution: Check that your source data contains records with AER_Status_CML = "Yes" and the required columns for your selected workflows

**Error: "Invalid workflow IDs format"**
- Solution: This is typically an internal error; contact support if it occurs

## Performance Considerations

- **File Size**: Maximum 30 MB per file
- **Processing Time**: 
  - Small files (< 1 MB): 5-30 seconds
  - Medium files (1-10 MB): 30 seconds - 2 minutes
  - Large files (10-30 MB): 2-5 minutes
- **Recommended**: Process in batches if you have very large datasets

## Privacy and Security

- ✅ Files are processed in memory only
- ✅ No permanent storage of user files
- ✅ Temporary files are automatically cleaned up
- ✅ All processing happens locally on the server
- ✅ No data is transmitted to external services

## Troubleshooting

### Backend Not Available
If you see "Backend API is not available":
1. Ensure the backend server is running:
   ```bash
   uv run uvicorn backend.main:app --reload
   ```
2. Check that the server is accessible at `http://localhost:8000`

### Processing Timeout
If processing takes too long:
1. Try processing fewer workflows at once
2. Check file size (reduce if > 20 MB)
3. Verify data quality (remove unnecessary columns/rows)

### Download Issues
If the ZIP file doesn't download:
1. Check browser download settings
2. Ensure sufficient disk space
3. Try a different browser

## Technical Details

### Backend Components

#### FileHandler
- Manages file paths dynamically
- Handles Excel file reading with pandas
- Creates output directory structure

#### DataProcessor
- Filters records based on workflow requirements
- Appends data to template sheets
- Maintains data integrity and formatting

#### Workflow Processors
- 20 separate workflow modules
- Each implements specific business logic
- Independent processing (failures don't cascade)

### Frontend Components

#### Upload Interface
- Streamlit file uploaders for source and template
- Client-side file validation
- File size checks

#### Workflow Selection
- 20 checkboxes organized in 4-column grid
- Select/Deselect All functionality
- Session state management

#### Download Interface
- Streamlit download button
- ZIP file streaming
- Processing summary display

## Version History

### v1.0 (Current)
- Initial release
- 20 workflows implemented
- Batch processing support
- ZIP file output
- Comprehensive error handling

## Support

For issues or questions:
1. Check the "Help & Information" section in the app
2. Review this documentation
3. Contact the development team

## References

- TML Data Processing Standards
- APM Data Loading Guidelines
- P1R-100 CMMS System Documentation

