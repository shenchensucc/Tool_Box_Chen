# 🛠️ Development Guide

## 🎯 Purpose

This guide provides general development practices for **Chen's Engineer Toolbox**. For function-specific guidance, see the `functions/` directory.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Code editor (VS Code, PyCharm, etc.)

### Initial Setup

1. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd Tool_Box_Chen
   ```

2. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   # or: pre-commit install
   ```

4. **Verify installation**:
   ```bash
   # Run tests
   uv run pytest
   
   # Run linters
   uv run black --check .
   uv run ruff check .
   ```

---

## 🏗️ Project Structure

```
Tool_Box_Chen/
├── backend/              # Backend API (FastAPI)
├── frontend/             # Frontend UI (Streamlit)
│   └── pages/            # Streamlit pages (auto-discovered)
├── tests/                # Test suite
├── docs/                 # Documentation
│   ├── functions/        # Function-specific guides
│   └── ...               # Architecture, guides, checklists
├── pyproject.toml        # Project configuration
├── requirements.txt      # Dependencies
└── README.md             # Main README
```

---

## 🔄 Development Workflow

### Standard Workflow

```
1. Create branch
   ↓
2. Read relevant function guide (docs/functions/)
   ↓
3. Read AI_DEVELOPMENT_RULES.md (if using AI)
   ↓
4. Make changes (minimal scope)
   ↓
5. Write/update tests
   ↓
6. Run linters and tests
   ↓
7. Update documentation
   ↓
8. Code review (CODE_REVIEW_CHECKLIST.md)
   ↓
9. Commit and push
```

### Branching Strategy

```
main                     # Stable, production-ready
  ├── feature/ili-tool   # New features
  ├── bugfix/file-upload # Bug fixes
  └── docs/update-guide  # Documentation updates
```

**Branch naming**:
- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `hotfix/description` - Urgent fixes
- `docs/description` - Documentation only
- `refactor/description` - Code refactoring

---

## 🧪 Testing

### Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_backend.py

# Specific test function
uv run pytest tests/test_backend.py::test_health_check

# With coverage
uv run pytest --cov=backend --cov=frontend

# Verbose output
uv run pytest -v
```

### Writing Tests

#### Backend Tests (pytest)

```python
# tests/test_backend.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_preview_excel():
    """Test Excel file preview"""
    with open("tests/fixtures/sample.xlsx", "rb") as f:
        response = client.post(
            "/api/ili/preview",
            files={"file": ("sample.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "sheet_names" in data
```

#### Frontend Tests (manual for now)

1. Start backend: `uv run uvicorn backend.main:app --reload`
2. Start frontend: `uv run streamlit run frontend/Home.py`
3. Test manually in browser
4. **TODO**: Add `pytest-playwright` for E2E tests

### Test Guidelines

- ✅ Test happy paths (expected behavior)
- ✅ Test edge cases (empty data, large data)
- ✅ Test error cases (invalid input, missing files)
- ✅ Use fixtures for test data
- ✅ Keep tests independent (no shared state)
- ❌ Don't test third-party libraries (pandas, FastAPI)
- ❌ Don't test unchanged code when making focused changes

---

## 🎨 Code Quality

### Linting and Formatting

**Black** (code formatter):
```bash
# Check formatting
uv run black --check .

# Format code
uv run black .
```

**Ruff** (linter):
```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .
```

**Pre-commit hooks** (automatic):
```bash
# Install hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

### Code Style Guidelines

#### Python Style

- **PEP 8** compliant (enforced by Black and Ruff)
- **Type hints** on all function signatures
- **Docstrings** on all public functions (Google style)
- **4-space indentation** (no tabs)
- **Max line length**: 100 characters

Example:
```python
def calculate_statistics(data: pd.DataFrame, column: str) -> Dict[str, float]:
    """
    Calculate statistical metrics for a DataFrame column.
    
    Args:
        data: Input DataFrame containing numeric data
        column: Name of the column to analyze
        
    Returns:
        Dictionary with statistics (mean, std, min, max)
        
    Raises:
        ValueError: If column doesn't exist or contains non-numeric data
    """
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found")
    
    series = data[column].dropna()
    return {
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": float(series.min()),
        "max": float(series.max()),
    }
```

#### Import Order

```python
# 1. Standard library
import os
import sys
from pathlib import Path

# 2. Third-party libraries
import pandas as pd
import numpy as np
from fastapi import FastAPI

# 3. Local imports
from backend.models import ProcessResponse
from backend.utils import validate_data
```

#### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Variables | `snake_case` | `file_path`, `total_count` |
| Functions | `snake_case` | `calculate_stats()`, `process_data()` |
| Classes | `PascalCase` | `ProcessResponse`, `ColumnStats` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_FILE_SIZE`, `API_VERSION` |
| Private | `_leading_underscore` | `_internal_function()` |

---

## 📁 File Organization

### Adding New Files

#### Backend

```python
# backend/new_module.py
"""
Module description here
"""
from typing import List
import pandas as pd

def new_function(param: str) -> List[dict]:
    """Function docstring"""
    pass
```

Then import in `backend/main.py`:
```python
from backend.new_module import new_function
```

#### Frontend

```python
# frontend/pages/5_New_Page.py
"""
New page description
"""
import streamlit as st
from frontend_utils import api_call

st.title("🆕 New Page")
st.write("Page content here...")
```

Streamlit auto-discovers pages in `frontend/pages/` with naming pattern `N_PageName.py`.

---

## 🔌 API Development

### Adding New Endpoint

1. **Define Pydantic models** (`backend/models.py`):
   ```python
   class NewRequest(BaseModel):
       param: str
       value: int
   
   class NewResponse(BaseModel):
       result: str
       data: List[dict]
   ```

2. **Implement endpoint** (`backend/main.py`):
   ```python
   @app.post("/api/new-endpoint", response_model=NewResponse)
   async def new_endpoint(request: NewRequest):
       """
       Endpoint description
       """
       # Process request
       result = process_new_request(request)
       return NewResponse(result=result, data=[])
   ```

3. **Add frontend integration** (`frontend_utils.py`):
   ```python
   def call_new_endpoint(param: str, value: int) -> dict:
       """Call new endpoint"""
       response = httpx.post(
           f"{BACKEND_URL}/api/new-endpoint",
           json={"param": param, "value": value}
       )
       response.raise_for_status()
       return response.json()
   ```

4. **Write tests** (`tests/test_backend.py`):
   ```python
   def test_new_endpoint():
       response = client.post(
           "/api/new-endpoint",
           json={"param": "test", "value": 42}
       )
       assert response.status_code == 200
       data = response.json()
       assert "result" in data
   ```

### API Best Practices

- ✅ Use Pydantic models for validation
- ✅ Return structured responses (not raw dicts)
- ✅ Use appropriate HTTP status codes
- ✅ Provide clear error messages
- ✅ Document with docstrings (auto-generates OpenAPI docs)
- ✅ Handle exceptions gracefully
- ❌ Don't return bare exceptions to client
- ❌ Don't use generic error messages

---

## 🎨 Frontend Development

### Streamlit Patterns

#### Page Structure

```python
import streamlit as st
from frontend_utils import api_call

# Page config
st.set_page_config(
    page_title="Page Name",
    page_icon="🎯",
    layout="wide"
)

# Title and description
st.title("🎯 Page Name")
st.markdown("Description of page functionality")

# Session state initialization
if "data" not in st.session_state:
    st.session_state.data = None

# Main content
col1, col2 = st.columns(2)

with col1:
    user_input = st.text_input("Input label")
    
with col2:
    if st.button("Process"):
        with st.spinner("Processing..."):
            result = api_call(user_input)
            st.session_state.data = result
        st.success("Done!")

# Display results
if st.session_state.data:
    st.subheader("Results")
    st.json(st.session_state.data)
```

#### Session State Management

```python
# Initialize
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
    st.session_state.preview_data = None

# Update
if uploaded_file:
    st.session_state.uploaded_file = uploaded_file
    st.session_state.preview_data = preview_file(uploaded_file)

# Clear
if st.button("Reset"):
    st.session_state.clear()
    st.experimental_rerun()
```

#### Error Handling

```python
try:
    result = api_call(params)
    st.success("Success!")
except httpx.HTTPStatusError as e:
    st.error(f"API Error: {e.response.json().get('detail', 'Unknown error')}")
except Exception as e:
    st.error(f"Error: {str(e)}")
```

---

## 📊 Visualization

### Plotly Charts

```python
import plotly.graph_objects as go

# Create figure
fig = go.Figure()

# Add traces
fig.add_trace(go.Scatter(
    x=x_values,
    y=y_values,
    mode="markers",
    name="Data Points",
    marker=dict(
        color=color_values,
        colorscale="Viridis",
        showscale=True,
    )
))

# Update layout
fig.update_layout(
    title="Chart Title",
    xaxis_title="X Axis",
    yaxis_title="Y Axis",
    hovermode="closest",
)

# Display in Streamlit
st.plotly_chart(fig, use_container_width=True)
```

---

## 🐛 Debugging

### Process Management & Hard Kill

If the app keeps running after closing the terminal (ghost processes), or you need to free ports 8000/8501:

- **Windows**: Run `kill_app.bat` (double-click or `.\kill_app.bat` in terminal)
- **Mac/Linux**: Run `./kill_app.sh`

This force-kills all processes on ports 8000 (backend) and 8501 (frontend).

### Backend Debugging

**Using uvicorn reload**:
```bash
uv run uvicorn backend.main:app --reload --reload-dir backend --log-level debug
```

If reload doesn't detect file changes (common on Windows), set `WATCHFILES_FORCE_POLLING=True` before running.

**Print debugging**:
```python
print(f"Debug: {variable}")  # Shows in terminal
```

**Logging**:
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")
```

### Frontend Debugging

**Streamlit debugging**:
```python
st.write("Debug:", variable)  # Shows in UI
st.json(data)  # Pretty-print JSON
st.exception(e)  # Show exception details
```

**Session state inspection**:
```python
st.sidebar.write("Session State:", st.session_state)
```

---

## 🔒 Security Best Practices

### Input Validation

- ✅ Validate all user inputs
- ✅ Use Pydantic models for API requests
- ✅ Sanitize file names
- ✅ Enforce file size limits
- ✅ Validate file types (not just extensions)

### Secrets Management

```python
# ❌ DON'T hardcode secrets
API_KEY = "sk-1234567890"

# ✅ DO use environment variables
import os
API_KEY = os.getenv("API_KEY")

# ✅ DO use .env files (not committed)
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv("API_KEY")
```

### File Upload Security

- ✅ Validate file size before processing
- ✅ Use temporary files (not user-provided paths)
- ✅ Clean up temp files in `finally` blocks
- ✅ Prevent path traversal attacks

---

## 🚀 Performance Tips

### Backend Performance

- **Always use `asyncio.to_thread()`** for blocking I/O inside `async def` endpoints — never call `pd.read_excel`, `load_workbook`, or any slow sync function directly on the event loop
- OCR (Azure Document Intelligence) runs via `asyncio.to_thread()` — it is network I/O, not CPU-bound
- Use generators for large datasets
- Cache expensive calculations
- Use database indexes (when added)
- Profile with `cProfile` for bottlenecks

### Frontend Performance

- Use `st.cache_data` for expensive computations
- Minimize API calls (cache in session state)
- Use lazy loading for large datasets
- Sample data for visualizations (> 10k points)

---

## 📝 Documentation Standards

### When to Update Documentation

| Change Type | Documentation to Update |
|-------------|------------------------|
| New feature | `README.md`, function guide in `docs/functions/` |
| API change | `docs/functions/BACKEND_API.md`, function guide |
| Architecture change | `docs/ARCHITECTURE.md` |
| New development practice | `docs/DEVELOPMENT_GUIDE.md` (this file) |
| Breaking change | All relevant docs + migration guide |

### Writing Good Documentation

- ✅ Clear, concise language
- ✅ Code examples for complex concepts
- ✅ Explain "why", not just "how"
- ✅ Keep it up-to-date
- ❌ Don't duplicate information (link instead)
- ❌ Don't write documentation for self-explanatory code

---

## 🆘 Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

#### Import Errors

```bash
# Reinstall dependencies
uv sync

# Or with pip
pip install -e ".[dev]"
```

#### Streamlit Caching Issues

```python
# Clear cache
st.cache_data.clear()

# Or restart Streamlit with 'c' in terminal
```

---

## 📞 Getting Help

- **Architecture questions**: See `docs/ARCHITECTURE.md`
- **Function-specific questions**: Check `docs/functions/`
- **Code review questions**: See `docs/CODE_REVIEW_CHECKLIST.md`
- **AI development questions**: Read `docs/AI_DEVELOPMENT_RULES.md`

---

**Last Updated**: March 2026  
**Project Version**: 0.2.0
