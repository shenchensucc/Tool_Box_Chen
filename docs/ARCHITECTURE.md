# 🏗️ System Architecture

## Overview

Chen's Engineer Toolbox is a modern, Python-based web application built with a **clean separation** between frontend and backend, following RESTful API principles.

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND (Streamlit)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │   Home.py   │ │ Dashboard   │ │   Pages     │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│                         │                                    │
│                         │ HTTP/REST API                      │
│                    (httpx client)                            │
└─────────────────────────┼──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI)                          │
│  ┌──────────────────────────────────────────────┐          │
│  │           API Endpoints                       │          │
│  │  /health  /api/ili/preview  /api/ili/process │          │
│  └────────────────────┬─────────────────────────┘          │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────┐          │
│  │        Business Logic Layer                   │          │
│  │  • File validation  • Data processing        │          │
│  │  • Statistics       • Error handling         │          │
│  └────────────────────┬─────────────────────────┘          │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────┐          │
│  │         Data Layer                            │          │
│  │  • pandas  • openpyxl  • numpy               │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                  ┌──────────────┐
                  │  Temp Files  │
                  │   (cleaned)  │
                  └──────────────┘
```

---

## Technology Stack

### Frontend Layer

| Component | Technology | Purpose | Version |
|-----------|-----------|---------|---------|
| **UI Framework** | Streamlit | Interactive web UI in pure Python | 1.31+ |
| **HTTP Client** | httpx | Async API calls to backend | 0.26+ |
| **Visualization** | Plotly | Interactive charts and graphs | 5.18+ |
| **State Management** | Streamlit Session State | Maintain user session data | Built-in |

**Location**: `frontend/`

### Backend Layer

| Component | Technology | Purpose | Version |
|-----------|-----------|---------|---------|
| **API Framework** | FastAPI | RESTful API server | 0.109+ |
| **Server** | Uvicorn | ASGI server (multi-worker) | 0.27+ |
| **Validation** | Pydantic | Request/response data models | 2.6+ |
| **Data Processing** | pandas | Data analysis and statistics | 2.2+ |
| **Excel Parsing** | openpyxl | Read/write Excel files | 3.1+ |
| **Numeric Computing** | numpy | Statistical calculations | 1.26+ |
| **PDF Parsing** | pdfplumber | Text and table extraction from PDFs | 0.10+ |
| **OCR (primary)** | EasyOCR | Neural-network OCR for image-based reports | Latest |
| **OCR (fallback)** | PaddleOCR / Tesseract | Fallback OCR engines | Latest |
| **Process Isolation** | ProcessPoolExecutor | Isolate OCR crashes from main server | stdlib |

**Location**: `backend/`

### Development Tools

| Tool | Purpose | Version |
|------|---------|---------|
| **uv** | Fast Python package manager | Latest |
| **pytest** | Testing framework | 8.0+ |
| **black** | Code formatter | 24.1+ |
| **ruff** | Fast Python linter | 0.2+ |
| **pre-commit** | Git hooks | 3.6+ |

---

## Directory Structure

```
Tool_Box_Chen/
├── backend/                    # Backend API
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, endpoints, startup/shutdown
│   ├── models.py               # Pydantic models
│   ├── pipeline/               # Pipeline engineering modules
│   │   ├── ocr_subprocess.py   # OCR worker functions (isolated process)
│   │   ├── dig_package.py      # Dig package generation
│   │   ├── metal_loss.py       # Metal loss calculations
│   │   └── report_generator.py # Word report generation
│   └── tml/                    # TML and inspection tools
│       ├── inspection_report_parser.py  # PDF parsing + OCR
│       ├── inspection_dataloader.py     # APM dataloader generation
│       ├── file_handler.py     # Excel file utilities
│       └── data_processor.py   # TML data processing
│
├── frontend/                   # Frontend UI
│   ├── __init__.py
│   ├── Home.py                 # Landing page (entry point)
│   ├── frontend_utils.py       # Shared utilities, API calls, privacy banner
│   └── pages/                  # Streamlit pages (auto-discovered)
│       ├── 1_Dashboard.py      # Dashboard overview
│       ├── 2_TML_Data_Loader.py
│       ├── 7_Deactive_CML.py
│       ├── 8_Inspection_Report_Loader.py
│       └── ...                 # ILI, metal loss, dig package pages
│
├── tests/                      # Test suite
│   ├── __init__.py
│   └── test_backend.py         # Backend tests
│
├── docs/                       # Documentation
│   ├── README.md               # Documentation hub
│   ├── ARCHITECTURE.md         # This file
│   ├── DEVELOPMENT_GUIDE.md    # Development practices
│   ├── AI_DEVELOPMENT_RULES.md # AI constraints
│   ├── CODE_REVIEW_CHECKLIST.md # Review guide
│   └── functions/              # Function-specific guides
│
├── pyproject.toml              # Project config (uv/pip)
├── requirements.txt            # Pip dependencies
├── requirements-dev.txt        # Dev dependencies
├── README.md                   # Main README
└── run_*.{sh,bat}             # Convenience scripts
```

---

## Design Principles

### 1. Separation of Concerns

**Frontend Responsibilities**:
- User interface rendering
- User input collection
- API calls to backend
- Data visualization
- Session state management

**Backend Responsibilities**:
- Business logic
- Data validation
- File processing
- Statistical calculations
- Error handling

**Anti-pattern**: Frontend should NEVER directly process files or perform complex calculations.

### 2. Stateless Backend

- Each API request is independent
- Download tokens stored on the **filesystem** (not in-memory), so multiple Uvicorn workers can serve them
- Temporary files cleaned after each request
- Enables horizontal scaling with multiple workers

### 3. Type Safety

- **Pydantic models** for all API requests/responses
- **Type hints** throughout codebase
- Runtime validation at API boundaries
- Clear contracts between frontend and backend

### 4. Error Handling Strategy

```
User Input → Frontend Validation → API Call → Backend Validation → Processing
                  ↓                               ↓                    ↓
            Client Error              HTTPException (4xx)        Try/Except
            (user feedback)           (structured error)      (log + 500)
```

### 5. Non-Blocking Async

All CPU-bound and I/O-bound work is offloaded from the async event loop:

```python
# Pattern used throughout main.py for blocking operations
result = await asyncio.to_thread(blocking_sync_function, args)
```

This ensures the event loop stays free to handle concurrent requests (health checks, other uploads) while a long-running task executes in a thread pool.

### 6. OCR Process Isolation

OCR (EasyOCR, PaddleOCR) runs in a separate **subprocess** via `ProcessPoolExecutor`, completely isolated from the FastAPI server process. This means:

- An OCR crash (segfault, OOM) cannot bring down the API server
- On crash, the executor is automatically re-created and the user gets a retryable error
- Only one OCR job runs at a time (single worker); concurrent OCR requests are rejected with HTTP 503 instead of silently queuing

```
FastAPI process
    └── asyncio event loop (non-blocking)
            └── asyncio.to_thread → thread pool (I/O: Excel, file ops)
            └── ProcessPoolExecutor → OCR worker process (EasyOCR / PaddleOCR)
                    ↑ crash here stays here — server keeps running
```

---

## Data Flow: ILI Visual Tool Example

### Upload and Preview Flow

```
1. User uploads Excel file
   └─> frontend/pages/Pipeline/ILI_Visual_Tool.py
       └─> st.file_uploader()

2. Frontend sends file to backend
   └─> httpx.post(f"{BACKEND_URL}/api/ili/preview", files=...)

3. Backend receives and validates
   └─> backend/main.py::preview_excel()
       ├─> validate_file_size()
       ├─> save_temp_file()
       └─> openpyxl.load_workbook()

4. Backend returns sheet/column info
   └─> PreviewResponse(sheet_names, columns, row_counts)

5. Frontend displays preview
   └─> st.selectbox() for sheet selection
   └─> st.multiselect() for column mapping
```

### Process Data Flow

```
1. User selects sheet + columns
   └─> frontend/pages/Pipeline/ILI_Visual_Tool.py

2. Frontend sends processing request
   └─> httpx.post(f"{BACKEND_URL}/api/ili/process",
       files=...,
       data={"sheet_name": ..., "distance_column": ...})

3. Backend processes data
   └─> backend/main.py::process_ili_data()
       ├─> pd.read_excel()
       ├─> calculate_stats() for each column
       ├─> create_histogram() for distributions
       └─> prepare scatter_data

4. Backend returns statistics
   └─> ProcessResponse(stats, histograms, scatter_data)

5. Frontend visualizes results
   └─> plotly.graph_objects.Figure()
       ├─> Histogram (distribution)
       ├─> Scatter (distance plot)
       └─> Box plot (outliers)
```

---

## API Contract

### Request Format

All file uploads use `multipart/form-data`:

```http
POST /api/ili/process
Content-Type: multipart/form-data

file: [binary Excel file]
sheet_name: "Sheet1"
distance_column: "Distance"
depth_column: "Depth"
metal_loss_column: "Metal Loss %"
```

### Response Format

All responses use JSON with Pydantic models:

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
    }
  },
  "histograms": [...],
  "scatter_data": {...}
}
```

### Error Format

```json
{
  "detail": "File too large. Maximum size is 100 MB"
}
```

HTTP Status Codes:
- `200`: Success
- `400`: Bad Request (invalid file, bad parameters)
- `413`: Payload Too Large
- `422`: Validation Error
- `500`: Internal Server Error

---

## Configuration

### Environment Variables

Currently optional, defaults provided:

```env
# Backend
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
BACKEND_URL=http://127.0.0.1:8000

# Frontend
FRONTEND_PORT=8501

# Limits
MAX_FILE_SIZE_MB=30

# Development
DEBUG=true
```

### Future Configuration Needs

- Database connection strings
- Authentication secrets
- External API keys
- Email service config
- Cloud storage credentials

---

## Security Architecture

### Current Security Measures

1. **File Upload Security**:
   - Size limits (100 MB)
   - Type validation (Excel only)
   - Temporary file cleanup

2. **CORS Configuration**:
   - Currently `allow_origins=["*"]` for local dev
   - **TODO**: Restrict in production

3. **Input Validation**:
   - Pydantic models validate all inputs
   - File extension checks
   - Column name validation

### Future Security Enhancements

- [ ] User authentication (JWT tokens)
- [ ] API rate limiting
- [ ] Input sanitization (XSS prevention)
- [ ] HTTPS enforcement
- [ ] Database query parameterization
- [ ] Audit logging
- [ ] Secret management (environment variables)

---

## Scalability Considerations

### Current Architecture Limits

- **OCR bottleneck**: Single OCR worker process; concurrent OCR requests are rejected (HTTP 503)
- **In-memory file processing**: 100 MB limit per file
- **No caching layer**
- **No database** (stateless by design)

### Scaling Strategies

1. **Horizontal Scaling**:
   - Multiple backend instances behind load balancer
   - Stateless design enables easy scaling

2. **Async Processing**:
   - Background tasks for large file processing
   - Celery/Redis for task queue
   - WebSockets for real-time updates

3. **Caching**:
   - Redis for session data
   - Cache processed file results

4. **Database**:
   - PostgreSQL for persistent data
   - Store user projects, analysis results
   - Enable collaboration features

5. **File Storage**:
   - S3/Cloud storage for large files
   - Pre-signed URLs for secure uploads

---

## Performance Characteristics

### Typical Response Times

| Operation | Expected Time | Notes |
|-----------|--------------|-------|
| Health check | < 10 ms | Simple JSON response |
| File preview | 100-500 ms | Depends on file size |
| Process data | 500-2000 ms | Depends on rows (< 10k rows) |
| Frontend render | 50-200 ms | After receiving API response |

### Bottlenecks

1. **Excel parsing**: `openpyxl` is slower than `xlrd`
2. **Large datasets**: Memory usage grows linearly
3. **Visualization**: Plotly rendering 10k+ points is slow
4. **Synchronous processing**: No parallelization currently

---

## Testing Strategy

### Backend Tests

Location: `tests/test_backend.py`

```python
# Unit tests for endpoints
test_health_check()           # /health endpoint
test_preview_valid_file()     # File preview success
test_preview_invalid_type()   # Error handling

# Integration tests
test_full_ili_workflow()      # End-to-end flow
```

Run: `pytest tests/test_backend.py -v`

### Frontend Tests

Currently manual testing:
- UI interaction
- API integration
- Visualization rendering

**Future**: Consider `pytest-playwright` for E2E tests

---

## Deployment Architecture

### Local Development

```
┌──────────────┐         ┌──────────────┐
│  Frontend    │ ──────> │   Backend    │
│ localhost:   │ HTTP    │ localhost:   │
│    8501      │         │    8000      │
└──────────────┘         └──────────────┘
```

Commands:
```bash
# Terminal 1
uvicorn backend.main:app --reload

# Terminal 2
streamlit run frontend/Home.py
```

### Production Deployment (Future)

```
┌─────────┐       ┌──────────────┐       ┌──────────────┐
│  Users  │ ───>  │ Load Balancer│ ───>  │  Frontend    │
└─────────┘       │   (Nginx)    │       │  (Docker)    │
                  └──────────────┘       └──────┬───────┘
                                                 │
                                                 ▼
                                         ┌──────────────┐
                                         │  Backend API │
                                         │  (Docker)    │
                                         └──────┬───────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │  Database    │
                                         │ (PostgreSQL) │
                                         └──────────────┘
```

Technologies:
- **Docker**: Containerization
- **Nginx**: Reverse proxy, SSL termination
- **PostgreSQL**: Persistent storage
- **Redis**: Caching, session storage

---

## Module Dependencies

### Backend Module Graph

```
backend/main.py
    ├─> backend/models.py              (Pydantic models)
    ├─> backend/pipeline/ocr_subprocess.py  (OCR worker — runs in subprocess)
    ├─> backend/tml/inspection_report_parser.py  (PDF + OCR parsing)
    ├─> backend/tml/inspection_dataloader.py     (APM dataloader generation)
    ├─> backend/pipeline/dig_package.py          (Dig package generation)
    ├─> backend/pipeline/metal_loss.py           (Metal loss calculations)
    ├─> fastapi                        (Framework)
    ├─> pandas                         (Data processing)
    ├─> openpyxl                       (Excel parsing)
    └─> numpy                          (Statistics)

backend/pipeline/ocr_subprocess.py    (isolated subprocess)
    └─> backend/tml/inspection_report_parser.py  (imported inside worker)
```

### Frontend Module Graph

```
frontend/Home.py
    └─> streamlit

frontend/pages/Pipeline/ILI_Visual_Tool.py
    ├─> streamlit
    ├─> frontend_utils.py (API calls)

frontend/pages/Facility/TML_Data_Loader.py
    ├─> streamlit
    ├─> frontend_utils.py (API calls)
    ├─> plotly (Visualization)
    ├─> pandas (Data display)
    └─> httpx (Backend communication)

frontend/frontend_utils.py
    └─> httpx
```

---

## Extension Points

### Adding New Functions

1. **Backend**: Add endpoint in `backend/main.py`
   ```python
   @app.post("/api/new-function")
   async def new_function_handler(...):
       pass
   ```

2. **Models**: Define request/response in `backend/models.py`
   ```python
   class NewFunctionRequest(BaseModel):
       param: str
   
   class NewFunctionResponse(BaseModel):
       result: dict
   ```

3. **Frontend**: Create page in `frontend/pages/`
   ```python
   # frontend/pages/5_New_Function.py
   import streamlit as st
   from frontend_utils import call_new_function_api
   ```

4. **Documentation**: Create guide in `docs/functions/`
   ```markdown
   # docs/functions/NEW_FUNCTION.md
   ```

### Adding New Data Sources

Currently: Excel files only

Future extensibility:
- CSV: `pd.read_csv()`
- JSON: `pd.read_json()`
- Database: SQLAlchemy connection
- Cloud Storage: boto3 (S3), azure-storage-blob

---

## Decision Log

### Why Streamlit for Frontend?

**Pros**:
- Pure Python (no JavaScript)
- Rapid prototyping
- Built-in components
- Automatic reactivity

**Cons**:
- Limited customization
- State management quirks
- Not ideal for complex UIs

**Decision**: Good fit for internal engineering tools, may reconsider for public-facing app.

### Why FastAPI for Backend?

**Pros**:
- Fast and modern
- Automatic API docs
- Type safety with Pydantic
- Async support
- Great for RESTful APIs

**Cons**:
- Overkill for very simple apps

**Decision**: Excellent choice for scalable, maintainable API.

### Why Not a Database Yet?

**Reasoning**:
- Current scope is stateless (file upload → analyze → download)
- Adds complexity
- No user accounts yet

**Future**: Add PostgreSQL when implementing:
- User authentication
- Project persistence
- Historical analysis

---

## Server Lifecycle

### Startup (`@app.on_event("startup")`)

1. Logs registered API routes for verification.
2. Spawns the OCR worker process via `ProcessPoolExecutor` in a background daemon thread.
3. Submits a warmup job so OCR models (EasyOCR, PaddleOCR) are pre-loaded before the first real request. This takes 30–60 s on first run; the server is fully responsive during warmup.

### Shutdown (`@app.on_event("shutdown")`)

Calls `_reset_ocr_executor()` which signals the OCR worker process to terminate cleanly. Without this, the subprocess would be orphaned after uvicorn exits.

---

## Known Limitations

1. **File size**: Limited to 100 MB (memory constraints)
2. **OCR concurrency**: Only one OCR parse at a time (single-worker executor); concurrent requests receive HTTP 503
3. **State**: No persistent user storage (by design — session-only)
4. **Auth**: No user authentication
5. **Collaboration**: Session-isolated per browser tab

---

**Last Updated**: March 2026  
**Architecture Version**: 0.2.0
