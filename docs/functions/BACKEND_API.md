# 🔌 Backend API - Development Guide

## 📍 Function Location

- **Main API**: `backend/main.py`
- **Data Models**: `backend/models.py`
- **OCR Worker**: `backend/pipeline/ocr_subprocess.py`
- **Inspection Parser**: `backend/tml/inspection_report_parser.py`
- **Tests**: `tests/test_backend.py`

---

## 🎯 Purpose

The Backend API provides RESTful endpoints for:
1. Health monitoring
2. File upload and validation
3. Data processing and analysis
4. Statistics calculation
5. Error handling and validation

---

## 🏗️ Architecture

### FastAPI Application Structure

```python
app = FastAPI(title="Chen's Engineer Toolbox API", version="0.2.0")

# Middleware
app.add_middleware(CORSMiddleware, ...)

# Lifecycle
@app.on_event("startup")   # Pre-warms OCR worker process
@app.on_event("shutdown")  # Terminates OCR worker process cleanly

# Endpoints (selected)
@app.get("/health")                          # Health check
@app.post("/api/ili/preview")                # Preview Excel file
@app.post("/api/ili/process")                # Process ILI data (visualization)
@app.post("/api/tml/process")                # TML data processing → ZIP
@app.post("/api/tml/deactivate-cml")         # Deactivate CML dataloader
@app.post("/api/tml/inspection-report/read") # Parse PDF reports (OCR)
@app.post("/api/tml/inspection-report")      # Parse PDFs + generate dataloader
@app.post("/api/pipeline/metal-loss/assess") # Metal loss assessment
@app.post("/api/pipeline/dig-package/generate") # Dig package generation (template optional → bundled 2026 xlsx)
```

### Request/Response Flow

```
Client Request
    ↓
FastAPI Route Handler (async)
    ↓
Pydantic Validation (automatic)
    ↓
await asyncio.to_thread(blocking_work)   ← I/O & CPU work runs in thread pool
    ↓                                        (event loop stays free)
Business Logic (helper functions)
    ↓
Pydantic Response Model
    ↓
JSON / FileResponse to Client
```

### OCR Request Flow

```
POST /api/tml/inspection-report/read
    ↓
Check _ocr_busy flag → if True: return HTTP 503 immediately
    ↓
Set _ocr_busy = True
    ↓
await asyncio.to_thread → executor.submit(run_ocr_parse, ...)
    ↓ (runs in OCR subprocess)
    ├─ Success → return readings JSON
    └─ BrokenProcessPool → _reset_ocr_executor() → return HTTP 503 (retry)
    ↓
Set _ocr_busy = False
```

---

## 📡 Endpoints

### 1. Health Check

**Endpoint**: `GET /health`

**Purpose**: Verify API is running

**Request**: None

**Response**:
```json
{
  "ok": true
}
```

**Status Codes**:
- `200`: API is healthy

**When to Modify**:
- Adding system status checks
- Adding version information
- Adding dependency health checks

**DO NOT MODIFY**:
- Basic structure (used by monitoring)

---

### 2. Preview Excel File

**Endpoint**: `POST /api/ili/preview`

**Purpose**: Quick preview of Excel file structure without full processing

**Request**:
```
Content-Type: multipart/form-data

file: [binary Excel file]
```

**Response**:
```json
{
  "filename": "inspection_data.xlsx",
  "sheet_names": ["Sheet1", "Sheet2"],
  "columns": {
    "Sheet1": ["Distance", "Depth", "Metal Loss %"],
    "Sheet2": ["Location", "Date", "Inspector"]
  },
  "row_counts": {
    "Sheet1": 1523,
    "Sheet2": 45
  }
}
```

**Status Codes**:
- `200`: Success
- `400`: Invalid file type
- `413`: File too large
- `500`: Processing error

**Validation**:
- File extension must be `.xlsx` or `.xls`
- File size must be ≤ MAX_FILE_SIZE (100 MB)

**Implementation**:
```python
async def preview_excel(file: UploadFile = File(...)):
    # 1. Validate file type
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Must be Excel file")
    
    # 2. Validate size
    validate_file_size(file)
    
    # 3. Save to temp
    temp_path = save_temp_file(file)
    
    try:
        # 4. Parse with openpyxl
        wb = load_workbook(temp_path, read_only=True)
        
        # 5. Extract metadata
        # ...
        
        return PreviewResponse(...)
    finally:
        # 6. ALWAYS cleanup temp file
        if temp_path.exists():
            os.unlink(temp_path)
```

**When to Modify**:
- Supporting new file types (CSV, JSON)
- Adding more metadata (created date, author)
- Improving preview performance

**DO NOT MODIFY**:
- Temp file cleanup logic
- File size validation
- Error handling structure

---

### 3. Process ILI Data

**Endpoint**: `POST /api/ili/process`

**Purpose**: Full data processing with statistics and plot data

**Request**:
```
Content-Type: multipart/form-data

file: [binary Excel file]
sheet_name: "Sheet1"
distance_column: "Distance"      # Optional
depth_column: "Depth"            # Optional
metal_loss_column: "Metal Loss %" # Optional
```

**Response**:
```json
{
  "filename": "inspection_data.xlsx",
  "sheet_name": "Sheet1",
  "total_rows": 1523,
  "stats": {
    "Distance": {
      "count": 1523,
      "mean": 4523.5,
      "std": 123.4,
      "min": 0.0,
      "max": 9500.0,
      "q25": 2200.0,
      "q50": 4500.0,
      "q75": 6800.0
    },
    "Depth": { ... },
    "Metal Loss %": { ... }
  },
  "histograms": [
    {
      "column_name": "Distance",
      "values": [0.0, 10.5, 20.3, ...],
      "bin_edges": [0, 316.67, 633.33, ...],
      "counts": [45, 67, 89, ...]
    }
  ],
  "scatter_data": {
    "x_column": "Distance",
    "x_values": [0.0, 10.5, 20.3, ...],
    "y_data": {
      "depth": [1.2, 2.3, 1.8, ...],
      "metal_loss": [15.2, 22.1, 18.5, ...]
    }
  }
}
```

**Status Codes**:
- `200`: Success
- `400`: Invalid file, sheet, or columns
- `413`: File too large
- `422`: Validation error
- `500`: Processing error

**Validation**:
- File type and size (same as preview)
- Sheet name must exist in file
- Column names must exist in sheet
- Columns must contain numeric data

**Implementation**:
```python
async def process_ili_data(
    file: UploadFile = File(...),
    sheet_name: str = Form(...),
    distance_column: str = Form(None),
    depth_column: str = Form(None),
    metal_loss_column: str = Form(None),
):
    # 1. Validate file
    validate_file_size(file)
    temp_path = save_temp_file(file)
    
    try:
        # 2. Read Excel sheet
        df = pd.read_excel(temp_path, sheet_name=sheet_name)
        
        # 3. Collect columns to analyze
        columns_to_analyze = [...]
        
        # 4. Calculate statistics
        stats = {}
        histograms = []
        for col in columns_to_analyze:
            stats[col] = calculate_stats(df[col])
            histograms.append(create_histogram(df[col], col))
        
        # 5. Prepare scatter data
        scatter_data = prepare_scatter_data(df, ...)
        
        return ProcessResponse(...)
    finally:
        # 6. Cleanup
        if temp_path.exists():
            os.unlink(temp_path)
```

**When to Modify**:
- Adding new statistics
- Adding new column types
- Supporting new file formats
- Improving performance

**DO NOT MODIFY**:
- Temp file cleanup
- Core validation logic
- Response model structure (breaking change)

---

## 🗂️ Data Models

### Location: `backend/models.py`

### HealthResponse
```python
class HealthResponse(BaseModel):
    ok: bool = True
```

**Purpose**: Health check response

**DO NOT MODIFY**: Used by monitoring systems

---

### PreviewResponse
```python
class PreviewResponse(BaseModel):
    filename: str
    sheet_names: List[str]
    columns: Dict[str, List[str]]  # sheet_name -> column_names
    row_counts: Dict[str, int]     # sheet_name -> row_count
```

**Purpose**: Excel file metadata

**Safe to Add**:
- `file_size: int`
- `created_date: Optional[datetime]`
- `author: Optional[str]`

**Breaking Changes** (avoid):
- Changing field types
- Removing fields
- Renaming fields

---

### ColumnStats
```python
class ColumnStats(BaseModel):
    count: int
    mean: float
    std: float
    min: float
    max: float
    q25: float  # 25th percentile
    q50: float  # 50th percentile (median)
    q75: float  # 75th percentile
```

**Purpose**: Statistical summary for numeric column

**Safe to Add**:
- `q10: Optional[float]`  # 10th percentile
- `q90: Optional[float]`  # 90th percentile
- `q95: Optional[float]`  # 95th percentile
- `skewness: Optional[float]`
- `kurtosis: Optional[float]`
- `iqr: Optional[float]`  # Interquartile range

**Breaking Changes** (avoid):
- Changing existing field types
- Making optional fields required

---

### HistogramData
```python
class HistogramData(BaseModel):
    column_name: str
    values: List[float]
    bin_edges: List[float]
    counts: List[int]
```

**Purpose**: Histogram plot data

**Safe to Add**:
- `bin_width: float`
- `total_count: int`

---

### ProcessResponse
```python
class ProcessResponse(BaseModel):
    filename: str
    sheet_name: str
    total_rows: int
    stats: Dict[str, ColumnStats]
    histograms: List[HistogramData]
    scatter_data: Optional[Dict[str, Any]] = None
```

**Purpose**: Complete processing results

**Safe to Add**:
- New optional fields
- New data structures in `scatter_data`

---

## 🔧 Helper Functions

### validate_file_size()

```python
def validate_file_size(file: UploadFile) -> None:
    """Validate uploaded file size"""
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to start
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max {MAX_FILE_SIZE // 1024 // 1024} MB")
```

**Purpose**: Enforce file size limits

**When to Modify**:
- Changing MAX_FILE_SIZE constant
- Adding per-user limits
- Adding file type-specific limits

**Critical**:
- Must seek back to start after checking
- Must raise HTTPException, not regular Exception

---

### save_temp_file()

```python
def save_temp_file(upload_file: UploadFile) -> Path:
    """Save uploaded file to temporary location"""
    suffix = Path(upload_file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = upload_file.file.read()
        tmp.write(content)
        return Path(tmp.name)
```

**Purpose**: Save uploaded file for processing

**Critical**:
- `delete=False` is intentional (manual cleanup in `finally`)
- Preserves file extension (important for openpyxl/pandas)
- Returns Path for easy manipulation

**DO NOT MODIFY** unless:
- Changing to cloud storage (S3, etc.)
- Implementing streaming for large files

---

### calculate_stats()

```python
def calculate_stats(series: pd.Series) -> ColumnStats:
    """Calculate statistics for a numeric series"""
    desc = series.describe()
    return ColumnStats(
        count=int(desc["count"]),
        mean=float(desc["mean"]),
        std=float(desc["std"]),
        min=float(desc["min"]),
        max=float(desc["max"]),
        q25=float(desc["25%"]),
        q50=float(desc["50%"]),
        q75=float(desc["75%"]),
    )
```

**Purpose**: Calculate statistics from pandas Series

**Safe to Modify**:
- Add more statistics to ColumnStats model
- Add custom calculations (IQR, MAD, etc.)

**Keep**:
- Use `series.describe()` for efficiency
- Cast to Python types (int, float) not numpy types

---

### create_histogram()

```python
def create_histogram(series: pd.Series, column_name: str, bins: int = 30) -> HistogramData:
    """Create histogram data for a numeric series"""
    clean_series = series.dropna()
    
    if len(clean_series) == 0:
        return HistogramData(column_name=column_name, values=[], bin_edges=[], counts=[])
    
    counts, bin_edges = np.histogram(clean_series, bins=bins)
    
    return HistogramData(
        column_name=column_name,
        values=clean_series.tolist(),
        bin_edges=bin_edges.tolist(),
        counts=counts.tolist(),
    )
```

**Purpose**: Generate histogram data for plotting

**Safe to Modify**:
- Binning strategy (auto, fd, scott, etc.)
- Default bin count
- Outlier handling

**Keep**:
- Handle empty series gracefully
- Drop NaN values before histogram
- Convert to Python lists (for JSON serialization)

---

---

## ⚡ Async Pattern

All CPU-bound and I/O-bound work **must not** block the async event loop. Use `asyncio.to_thread()`:

```python
# ✅ Correct — blocking work runs in thread pool
result = await asyncio.to_thread(pd.read_excel, temp_path, sheet_name=sheet)

# ❌ Wrong — blocks the event loop; other requests stall
df = pd.read_excel(temp_path, sheet_name=sheet)
```

This applies to: `pd.read_excel`, `load_workbook`, file I/O, ZIP creation, and any other synchronous call that takes > ~1 ms.

---

## 📡 Inspection Report Endpoints

### Read Reports

**Endpoint**: `POST /api/tml/inspection-report/read`

**Purpose**: Parse one or more PDF inspection reports and return a reading summary.

**Request**: `multipart/form-data` — one or more `files` (PDF)

**Response**: JSON list of `ExtractedReading` objects (circuit, CML, reading, date)

**Status Codes**:
- `200`: Success
- `503`: OCR worker is busy — retry after current job finishes
- `500`: Parse error

**OCR isolation**: The actual parsing runs in a `ProcessPoolExecutor` subprocess. If the worker crashes (segfault, OOM), the endpoint returns HTTP 503 and the executor is re-created automatically.

---

### Generate Dataloader

**Endpoint**: `POST /api/tml/inspection-report`

**Purpose**: Parse PDFs + optionally match with source Excel → generate APM measurement dataloader Excel.

**Request**: `multipart/form-data`
- `files`: PDFs (required)
- `source_file`: Source Excel with `Source_Data` sheet (optional)

**Response**: `FileResponse` — `Inspection_Report_Dataloader.xlsx`

**Status Codes**:
- `200`: Excel file download
- `503`: OCR worker busy
- `500`: Parse or generation error

---

## 🧪 Testing Guidelines

### Test File: `tests/test_backend.py`

### Required Tests

1. **Health Check**
   ```python
   def test_health_check():
       response = client.get("/health")
       assert response.status_code == 200
       assert response.json()["ok"] is True
   ```

2. **File Validation**
   ```python
   def test_preview_invalid_file_type():
       # Test .csv rejection
       
   def test_preview_file_too_large():
       # Test size limit
   ```

3. **Preview Endpoint**
   ```python
   def test_preview_valid_excel():
       # Test successful preview
       
   def test_preview_multi_sheet():
       # Test multiple sheets
   ```

4. **Process Endpoint**
   ```python
   def test_process_with_column_mapping():
       # Test full processing
       
   def test_process_auto_detect_columns():
       # Test without column mapping
   ```

5. **Error Handling**
   ```python
   def test_process_invalid_sheet_name():
       # Test 400 error
       
   def test_process_invalid_column_name():
       # Test 400 error
   ```

### Test Fixtures

Create in `tests/fixtures/`:
- `sample_ili_data.xlsx`: Typical ILI data (1000 rows, 3 columns)
- `empty_sheet.xlsx`: Empty Excel file
- `multi_sheet.xlsx`: Multiple sheets
- `large_file.xlsx`: Approaching size limit

---

## 🚨 Common Pitfalls

### 1. Forgetting Temp File Cleanup

❌ **Bad**:
```python
def process_data(file: UploadFile):
    temp_path = save_temp_file(file)
    df = pd.read_excel(temp_path)
    return process(df)
    # temp_path never deleted!
```

✅ **Good**:
```python
def process_data(file: UploadFile):
    temp_path = save_temp_file(file)
    try:
        df = pd.read_excel(temp_path)
        return process(df)
    finally:
        if temp_path.exists():
            os.unlink(temp_path)
```

### 2. Not Validating Column Existence

❌ **Bad**:
```python
df[column_name]  # KeyError if column doesn't exist
```

✅ **Good**:
```python
if column_name not in df.columns:
    raise HTTPException(400, f"Column '{column_name}' not found")
```

### 3. Returning Numpy Types

❌ **Bad**:
```python
return {"mean": np.float64(123.45)}  # Not JSON serializable
```

✅ **Good**:
```python
return {"mean": float(123.45)}  # Python native type
```

### 4. Bare Except Clauses

❌ **Bad**:
```python
try:
    process_data()
except:  # Too broad
    return {"error": "Something went wrong"}
```

✅ **Good**:
```python
try:
    process_data()
except HTTPException:
    raise  # Re-raise HTTP exceptions
except Exception as e:
    raise HTTPException(500, f"Processing error: {str(e)}")
```

---

## 🔒 Security Considerations

### File Upload Security

1. **Validate file type** (not just extension):
   ```python
   # TODO: Implement magic number checking
   # import magic
   # mime = magic.from_buffer(file_content, mime=True)
   ```

2. **Enforce size limits**:
   - Current: 30 MB
   - Consider per-user limits in future

3. **Clean temp files immediately**:
   - Use `finally` blocks
   - Consider timeout cleanup for abandoned files

4. **Prevent path traversal**:
   ```python
   # Don't use user-provided filenames directly
   # Use tempfile.NamedTemporaryFile instead
   ```

### CORS Configuration

**Current** (local development):
```python
allow_origins=["*"]  # Allows all origins
```

**Production** (TODO):
```python
allow_origins=[
    "https://yourdomain.com",
    "https://app.yourdomain.com"
]
```

---

## 📈 Performance Optimization

### Current Bottlenecks

1. **openpyxl parsing**: Slow for large files
   - Consider using `xlrd` for .xls files
   - Consider `pyxlsb` for binary files

2. **pandas read_excel**: Memory intensive
   - Use `usecols` to read only needed columns
   - Use `nrows` for sampling

3. **Statistics calculation**: Sequential
   - Parallelize with `multiprocessing` for multiple columns
   - Cache results in session

### Optimization Opportunities

```python
# Current
df = pd.read_excel(file_path, sheet_name=sheet_name)

# Optimized
df = pd.read_excel(
    file_path,
    sheet_name=sheet_name,
    usecols=columns_to_analyze,  # Only read needed columns
    nrows=10000  # Limit rows for preview
)
```

---

## 🔄 Extension Points

### Adding New Endpoints

```python
@app.post("/api/new-function", response_model=NewResponse)
async def new_function_handler(
    file: UploadFile = File(...),
    param: str = Form(...),
):
    """
    Document your new endpoint here
    """
    # 1. Validate inputs
    # 2. Process data
    # 3. Return structured response
    pass
```

### Adding New File Types

```python
if file.filename.endswith(".csv"):
    df = pd.read_csv(temp_path)
elif file.filename.endswith((".xlsx", ".xls")):
    df = pd.read_excel(temp_path)
elif file.filename.endswith(".json"):
    df = pd.read_json(temp_path)
else:
    raise HTTPException(400, "Unsupported file type")
```

---

## 📝 Modification Checklist

Before modifying Backend API:

- [ ] Read `docs/AI_DEVELOPMENT_RULES.md`
- [ ] Identify exact endpoints/functions to modify
- [ ] Check if changes are breaking (response models)
- [ ] Plan migration strategy if breaking
- [ ] Write tests BEFORE modifying code
- [ ] Update Pydantic models if needed
- [ ] Update OpenAPI documentation (automatic in FastAPI)
- [ ] Test with real files
- [ ] Verify temp file cleanup
- [ ] Update this guide if adding new endpoints

---

**Last Updated**: March 2026  
**API Version**: 0.2.0
