# 🛢️ ILI Visual Tool - Development Guide

## 📍 Function Location

- **Frontend**: `frontend/pages/4_ILI_Visual_Tool.py`
- **Backend**: `backend/main.py` (endpoints: `/api/ili/preview`, `/api/ili/process`)
- **Models**: `backend/models.py` (`PreviewResponse`, `ProcessResponse`, `ColumnStats`, `HistogramData`)

---

## 🎯 Function Purpose

The **ILI (In-Line Inspection) Visual Tool** enables engineers to:
1. Upload Excel files containing pipeline inspection data
2. Preview file structure (sheets, columns, row counts)
3. Map columns to data types (distance, depth, metal loss)
4. Generate statistical summaries and visualizations
5. Export processed results

---

## 🏗️ Architecture

### Data Flow

```
User Upload → Frontend → /api/ili/preview → Backend → Preview Data
                ↓                                           ↓
         User Maps Columns                       Frontend Displays Preview
                ↓
         User Clicks "Process"
                ↓
    Frontend → /api/ili/process → Backend → Statistics & Plot Data
                                      ↓
                          Frontend Visualizes with Plotly
```

### Component Breakdown

#### Frontend (`4_ILI_Visual_Tool.py`)

1. **File Upload Section**
   - Streamlit file uploader
   - File type validation
   - Upload button

2. **Preview Section**
   - Display sheet names
   - Display column names per sheet
   - Display row counts

3. **Column Mapping Section**
   - Sheet selection dropdown
   - Column selection dropdowns (distance, depth, metal loss)

4. **Processing Section**
   - Process button
   - Loading indicator
   - Results display

5. **Visualization Section**
   - Statistical tables
   - Histograms (distribution)
   - Scatter plots (distance-based)
   - Box plots (outliers)

6. **Export Section**
   - Download statistics as CSV

#### Backend (`main.py`)

1. **Preview Endpoint** (`/api/ili/preview`)
   - Validates file type and size
   - Parses Excel with openpyxl
   - Returns sheet names, columns, row counts

2. **Process Endpoint** (`/api/ili/process`)
   - Reads specified sheet with pandas
   - Calculates statistics (mean, std, quartiles)
   - Creates histogram data
   - Prepares scatter plot data
   - Returns structured response

---

## 🔧 Key Functions

### Backend Functions

#### `validate_file_size(file: UploadFile)`
```python
def validate_file_size(file: UploadFile) -> None:
    """Validate uploaded file size"""
```
- **Purpose**: Ensure file doesn't exceed MAX_FILE_SIZE
- **Raises**: `HTTPException(413)` if too large
- **DO NOT MODIFY**: Unless changing file size limits

#### `save_temp_file(upload_file: UploadFile) -> Path`
```python
def save_temp_file(upload_file: UploadFile) -> Path:
    """Save uploaded file to temporary location"""
```
- **Purpose**: Write uploaded file to temp directory
- **Returns**: Path to temporary file
- **IMPORTANT**: Caller must clean up temp file

#### `calculate_stats(series: pd.Series) -> ColumnStats`
```python
def calculate_stats(series: pd.Series) -> ColumnStats:
    """Calculate statistics for a numeric series"""
```
- **Purpose**: Calculate mean, std, min, max, quartiles
- **Input**: Pandas Series (numeric)
- **Returns**: ColumnStats Pydantic model
- **Modify**: Only if adding new statistical metrics

#### `create_histogram(series: pd.Series, column_name: str, bins: int = 30) -> HistogramData`
```python
def create_histogram(series: pd.Series, column_name: str, bins: int = 30) -> HistogramData:
    """Create histogram data for a numeric series"""
```
- **Purpose**: Generate histogram data for plotting
- **Input**: Pandas Series, column name, bin count
- **Returns**: HistogramData (values, bin_edges, counts)
- **Modify**: Only if changing binning strategy

#### `preview_excel(file: UploadFile) -> PreviewResponse`
```python
@app.post("/api/ili/preview", response_model=PreviewResponse)
async def preview_excel(file: UploadFile = File(...)):
    """Preview an Excel file and return sheet names, columns, and row counts"""
```
- **Purpose**: Quick preview without full processing
- **Validation**: File type, size
- **Returns**: Sheet names, columns per sheet, row counts
- **Cleanup**: Deletes temp file in `finally` block

#### `process_ili_data(...) -> ProcessResponse`
```python
@app.post("/api/ili/process", response_model=ProcessResponse)
async def process_ili_data(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    distance_column: str = Form(None),
    depth_column: str = Form(None),
    metal_loss_column: str = Form(None),
):
    """Process ILI data from Excel file and return statistics and plot data"""
```
- **Purpose**: Full data processing and analysis
- **Inputs**: File, sheet name, column mappings
- **Processing**:
  1. Read Excel sheet
  2. Calculate statistics for mapped columns
  3. Generate histogram data
  4. Prepare scatter plot data (if distance column provided)
- **Returns**: Statistics, histograms, scatter data
- **Cleanup**: Deletes temp file in `finally` block

### Frontend Functions

#### Main page structure
```python
st.set_page_config(page_title="ILI Visual Tool", ...)
st.title("🛢️ ILI Visual Tool")
```

#### File upload section
```python
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])
```

#### API call wrappers (in `frontend_utils.py`)
```python
def preview_ili_file(file_content, filename):
    """Call backend preview endpoint"""
    
def process_ili_data(file_content, filename, sheet_name, column_mapping):
    """Call backend process endpoint"""
```

---

## 🚨 CRITICAL: Do Not Modify

### These sections should remain stable:

1. **File validation logic** (`validate_file_size`)
   - Changing limits affects user expectations
   - Document any changes clearly

2. **Temporary file cleanup** (`finally` blocks)
   - Critical for preventing file system bloat
   - Must always execute

3. **Pydantic models** (in `models.py`)
   - Breaking changes affect frontend/backend contract
   - Use versioning for major changes

4. **CORS settings** (in `main.py`)
   - Security implications
   - Coordinate with deployment team

---

## ✅ Safe to Modify

### You can change these without breaking things:

1. **Statistics calculations**
   - Add new metrics (skewness, kurtosis)
   - Add percentiles (10th, 90th, 95th)

2. **Visualization styles**
   - Colors, layouts, chart types
   - Axis labels, titles

3. **Column mapping UI**
   - Add more column types
   - Improve validation

4. **Error messages**
   - Make more user-friendly
   - Add more context

---

## 🧪 Testing Requirements

### When modifying this function, test:

1. **File Upload**
   - [ ] Valid Excel file (.xlsx)
   - [ ] Valid Excel file (.xls)
   - [ ] Invalid file type (.csv, .txt)
   - [ ] File too large (> 30 MB)
   - [ ] Empty file

2. **Preview**
   - [ ] Single sheet file
   - [ ] Multi-sheet file
   - [ ] Sheet with no data
   - [ ] Sheet with mixed data types

3. **Processing**
   - [ ] All columns mapped correctly
   - [ ] Only distance column mapped
   - [ ] No columns mapped (auto-detect)
   - [ ] Invalid column names
   - [ ] Non-numeric columns selected

4. **Statistics**
   - [ ] Normal distribution data
   - [ ] Data with outliers
   - [ ] Data with NaN values
   - [ ] Single data point
   - [ ] Empty column

5. **Visualizations**
   - [ ] Histogram renders correctly
   - [ ] Scatter plot with distance
   - [ ] Box plot for outliers
   - [ ] Large datasets (> 5000 rows)

### Test Data

Create test files in `tests/fixtures/`:
- `valid_ili_data.xlsx` (typical structure)
- `multi_sheet.xlsx` (multiple sheets)
- `empty_sheet.xlsx` (no data)
- `large_file.xlsx` (approaching size limit)

---

## 🐛 Common Issues & Solutions

### Issue: "File too large" error for small files

**Cause**: File size check might be too strict

**Solution**: 
```python
# Check MAX_FILE_SIZE constant
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB
```

### Issue: Preview works but processing fails

**Cause**: 
- Sheet name mismatch
- Column name mismatch
- Encoding issues

**Solution**:
- Validate sheet name exists before processing
- Trim whitespace from column names
- Handle encoding errors gracefully

### Issue: Visualizations not rendering

**Cause**:
- Too many data points (> 10k)
- Invalid data types
- NaN values

**Solution**:
- Implement data sampling for large datasets
- Filter NaN before plotting
- Validate numeric types

### Issue: Memory errors with large files

**Cause**: Loading entire file into memory

**Solution**:
- Increase file size limit cautiously
- Consider streaming/chunking for very large files
- Use `read_only=True` in openpyxl when possible

---

## 📈 Performance Considerations

### Current Performance

| Operation | Time | Bottleneck |
|-----------|------|------------|
| Preview | 100-500 ms | openpyxl parsing |
| Process (1k rows) | 200-500 ms | pandas operations |
| Process (10k rows) | 1-2 seconds | Statistics calculation |
| Visualization | 50-200 ms | Plotly rendering |

### Optimization Opportunities

1. **Caching**:
   - Cache preview results in session state
   - Avoid re-uploading same file

2. **Parallel Processing**:
   - Calculate statistics for columns in parallel
   - Use multiprocessing for large datasets

3. **Data Sampling**:
   - For visualization, sample large datasets
   - Full stats on complete data, plot subset

4. **Lazy Loading**:
   - Load visualizations on-demand (tabs)
   - Don't render all charts immediately

---

## 🔄 Extension Ideas

### Easy Additions (< 1 hour)

- [ ] Add more statistics (median absolute deviation, IQR)
- [ ] Add more percentiles (5th, 10th, 90th, 95th)
- [ ] Add correlation matrix for multiple columns
- [ ] Add summary statistics table
- [ ] Add data quality indicators (% missing, % outliers)

### Medium Additions (2-4 hours)

- [ ] Support CSV file upload
- [ ] Add filtering capabilities (date range, value range)
- [ ] Add comparison mode (compare two files)
- [ ] Generate PDF report
- [ ] Add anomaly detection highlighting

### Complex Additions (1+ days)

- [ ] Support streaming for very large files (> 100 MB)
- [ ] Add machine learning anomaly detection
- [ ] Integrate with external databases
- [ ] Add collaborative annotations
- [ ] Implement version control for analyses

---

## 📝 Modification Checklist

Before modifying the ILI Visual Tool:

- [ ] Read this guide completely
- [ ] Read `docs/AI_DEVELOPMENT_RULES.md`
- [ ] Identify exact scope of changes
- [ ] List files that will be modified
- [ ] List files that should NOT be touched
- [ ] Create tests for new functionality
- [ ] Update this guide if adding new features
- [ ] Run full test suite
- [ ] Test manually with sample files

---

## 🔗 Related Documentation

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Overall system design
- [BACKEND_API.md](BACKEND_API.md) - Backend API details
- [FRONTEND_COMPONENTS.md](FRONTEND_COMPONENTS.md) - Frontend patterns
- [CODE_REVIEW_CHECKLIST.md](../CODE_REVIEW_CHECKLIST.md) - Review standards

---

## 📞 Questions?

- **File processing issues**: Check pandas/openpyxl documentation
- **API issues**: Review FastAPI documentation
- **Visualization issues**: Check Plotly documentation
- **Architecture questions**: See `ARCHITECTURE.md`

---

**Last Updated**: October 2025  
**Function Version**: 0.1.0
