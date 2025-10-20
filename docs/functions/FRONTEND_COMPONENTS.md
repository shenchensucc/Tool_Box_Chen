# 🎨 Frontend Components - Development Guide

## 📍 Location

- **Shared Utilities**: `frontend/frontend_utils.py`
- **Pages**: `frontend/pages/*.py`
- **Main Entry**: `frontend/Home.py`

---

## 🎯 Purpose

This guide covers **reusable frontend patterns, components, and utilities** for building consistent Streamlit interfaces across all pages.

---

## 🏗️ Frontend Architecture

### Page Discovery

Streamlit automatically discovers pages in `frontend/pages/` directory:

```
frontend/
├── Home.py                   # Main entry (cover page)
└── pages/
    ├── 1_Dashboard.py              # Shows as "Dashboard" in sidebar
    ├── Facility/                   # Expandable "Facility" section
    │   └── TML_Data_Loader.py      # Shows as "TML Data Loader" under Facility
    └── Pipeline/                   # Expandable "Pipeline" section
        └── ILI_Visual_Tool.py      # Shows as "ILI Visual Tool" under Pipeline
```

**Naming Convention**: 
- Top-level pages: `N_Page_Name.py` where `N` orders in sidebar
- Sections: Create a directory (e.g., `Facility/`) for expandable sidebar section
- Sub-pages: Place files in section directory (e.g., `Facility/TML_Data_Loader.py`)
- Display names: Underscores become spaces

### Shared Utilities

`frontend_utils.py` contains:
- API call wrappers
- Common validation functions
- Shared constants
- Helper utilities

---

## 🔧 Common Patterns

### 1. Page Setup

```python
import streamlit as st

# Page configuration (must be first Streamlit command)
st.set_page_config(
    page_title="Page Name",
    page_icon="🎯",
    layout="wide",  # or "centered"
    initial_sidebar_state="expanded"
)

# Custom CSS (optional)
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# Page title
st.title("🎯 Page Name")
st.markdown("Brief description of page functionality")
```

### 2. Session State Management

```python
# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if "data" not in st.session_state:
        st.session_state.data = None
    if "processing" not in st.session_state:
        st.session_state.processing = False
    if "history" not in st.session_state:
        st.session_state.history = []

# Call at start of page
init_session_state()

# Access session state
if st.session_state.data is not None:
    display_data(st.session_state.data)

# Update session state
st.session_state.data = new_data

# Clear session state
if st.button("Reset"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.experimental_rerun()
```

### 3. File Upload Component

```python
uploaded_file = st.file_uploader(
    label="Upload File",
    type=["xlsx", "xls", "csv"],
    help="Supported formats: Excel (.xlsx, .xls) and CSV (.csv)",
    key="file_uploader"
)

if uploaded_file is not None:
    # Show file info
    st.info(f"📄 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
    
    # Store in session state
    st.session_state.uploaded_file = uploaded_file
    
    # Process file
    file_content = uploaded_file.read()
    uploaded_file.seek(0)  # Reset file pointer if needed
```

### 4. Form Pattern

```python
with st.form("my_form"):
    st.subheader("Input Form")
    
    # Form inputs
    name = st.text_input("Name")
    value = st.number_input("Value", min_value=0, max_value=100)
    option = st.selectbox("Option", ["A", "B", "C"])
    
    # Form submit button
    submitted = st.form_submit_button("Submit")
    
    if submitted:
        # Validate inputs
        if not name:
            st.error("Name is required")
        else:
            # Process form
            process_form(name, value, option)
            st.success("Form submitted successfully!")
```

### 5. Loading State

```python
if st.button("Process Data"):
    with st.spinner("Processing... Please wait"):
        try:
            result = expensive_operation()
            st.success("✅ Processing complete!")
            st.session_state.result = result
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
```

### 6. Tabs Pattern

```python
tab1, tab2, tab3 = st.tabs(["📊 Overview", "📈 Analysis", "⚙️ Settings"])

with tab1:
    st.subheader("Overview")
    # Overview content
    
with tab2:
    st.subheader("Analysis")
    # Analysis content
    
with tab3:
    st.subheader("Settings")
    # Settings content
```

### 7. Columns Layout

```python
# Equal columns
col1, col2 = st.columns(2)

with col1:
    st.metric("Metric 1", "100")
    
with col2:
    st.metric("Metric 2", "200")

# Custom column ratios
col1, col2, col3 = st.columns([2, 1, 1])  # 2:1:1 ratio

with col1:
    # Wide column
    pass

with col2:
    # Narrow column
    pass

with col3:
    # Narrow column
    pass
```

### 8. Expander Pattern

```python
with st.expander("📝 Show Details", expanded=False):
    st.write("Detailed information here...")
    st.code("code example")
    st.json({"key": "value"})
```

### 9. Sidebar Usage

```python
with st.sidebar:
    st.header("Filters")
    
    date_range = st.date_input("Date Range", [])
    category = st.multiselect("Category", ["A", "B", "C"])
    
    if st.button("Apply Filters"):
        apply_filters(date_range, category)
```

### 10. Data Display

```python
import pandas as pd

# Display dataframe
st.dataframe(df, use_container_width=True)

# Editable dataframe
edited_df = st.data_editor(df, num_rows="dynamic")

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Mean", f"{df['value'].mean():.2f}")
col2.metric("Median", f"{df['value'].median():.2f}")
col3.metric("Std Dev", f"{df['value'].std():.2f}")

# Charts
st.line_chart(df[['column1', 'column2']])
st.bar_chart(df['column'])
```

---

## 🔌 API Integration

### API Call Wrapper Pattern

```python
# frontend_utils.py

import httpx
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"

def api_call_wrapper(
    method: str,
    endpoint: str,
    **kwargs
) -> dict:
    """
    Generic API call wrapper with error handling
    
    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        **kwargs: Additional arguments for httpx request
        
    Returns:
        Response JSON data
        
    Raises:
        Exception with user-friendly message
    """
    url = f"{BACKEND_URL}{endpoint}"
    
    try:
        response = httpx.request(method, url, timeout=30.0, **kwargs)
        response.raise_for_status()
        return response.json()
        
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json().get("detail", "Unknown error")
        raise Exception(f"API Error: {error_detail}")
        
    except httpx.TimeoutException:
        raise Exception("Request timed out. Please try again.")
        
    except httpx.RequestError as e:
        raise Exception(f"Connection error: {str(e)}")
        
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")

# Specific API calls
def preview_file(file_content: bytes, filename: str) -> dict:
    """Preview Excel file"""
    return api_call_wrapper(
        "POST",
        "/api/ili/preview",
        files={"file": (filename, file_content)}
    )

def process_data(file_content: bytes, filename: str, params: dict) -> dict:
    """Process data"""
    return api_call_wrapper(
        "POST",
        "/api/ili/process",
        files={"file": (filename, file_content)},
        data=params
    )
```

### Using API Calls in Pages

```python
from frontend_utils import preview_file, process_data

try:
    # Call API
    result = preview_file(file_content, filename)
    
    # Store result
    st.session_state.preview = result
    
    # Display result
    st.json(result)
    
except Exception as e:
    # Show user-friendly error
    st.error(str(e))
```

---

## 📊 Visualization Patterns

### Plotly Chart Pattern

```python
import plotly.graph_objects as go

def create_histogram(data: list, column_name: str) -> go.Figure:
    """Create histogram visualization"""
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=data,
        name=column_name,
        marker=dict(
            color='rgba(31, 119, 180, 0.7)',
            line=dict(color='rgba(31, 119, 180, 1)', width=1)
        ),
        nbinsx=30
    ))
    
    fig.update_layout(
        title=f"Distribution of {column_name}",
        xaxis_title=column_name,
        yaxis_title="Frequency",
        template="plotly_white",
        hovermode="x unified",
        showlegend=False
    )
    
    return fig

# Display in Streamlit
fig = create_histogram(data, "Column Name")
st.plotly_chart(fig, use_container_width=True)
```

### Multi-Chart Pattern

```python
def create_dashboard_charts(df: pd.DataFrame) -> list:
    """Create multiple charts for dashboard"""
    charts = []
    
    # Histogram
    fig1 = go.Figure(data=[go.Histogram(x=df['column'])])
    fig1.update_layout(title="Distribution")
    charts.append(fig1)
    
    # Scatter plot
    fig2 = go.Figure(data=[go.Scatter(x=df['x'], y=df['y'], mode='markers')])
    fig2.update_layout(title="Scatter Plot")
    charts.append(fig2)
    
    # Box plot
    fig3 = go.Figure(data=[go.Box(y=df['column'])])
    fig3.update_layout(title="Box Plot")
    charts.append(fig3)
    
    return charts

# Display in tabs
charts = create_dashboard_charts(df)
tabs = st.tabs(["Distribution", "Scatter", "Box Plot"])

for tab, chart in zip(tabs, charts):
    with tab:
        st.plotly_chart(chart, use_container_width=True)
```

---

## 🎨 Styling

### Custom CSS

```python
def apply_custom_styles():
    """Apply custom CSS styles"""
    st.markdown("""
    <style>
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Custom button style */
        .stButton>button {
            background-color: #1f77b4;
            color: white;
            border-radius: 5px;
            padding: 0.5rem 1rem;
        }
        
        /* Custom header */
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            margin-bottom: 1rem;
        }
        
        /* Card style */
        .card {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)

# Apply at page start
apply_custom_styles()
```

---

## ✅ Best Practices

### Do's ✅

1. **Always initialize session state** at page start
2. **Use form for multiple inputs** (better UX)
3. **Show loading indicators** for slow operations
4. **Provide clear error messages** to users
5. **Use `use_container_width=True`** for responsive charts
6. **Cache expensive operations** with `@st.cache_data`
7. **Validate user inputs** before processing
8. **Store processed data** in session state (avoid re-computation)

### Don'ts ❌

1. **Don't put heavy computations outside functions** (runs on every rerun)
2. **Don't forget to reset file pointers** after reading
3. **Don't use bare except clauses** (catch specific exceptions)
4. **Don't hardcode backend URL** (use config/environment variable)
5. **Don't display raw tracebacks** to users (log them, show friendly message)
6. **Don't nest forms** (not supported in Streamlit)
7. **Don't use `st.set_page_config` multiple times** (only once, first command)

---

## 🧪 Testing Frontend

### Manual Testing Checklist

- [ ] Page loads without errors
- [ ] All buttons work correctly
- [ ] Form validation works
- [ ] Error messages display properly
- [ ] Loading indicators show during processing
- [ ] Session state persists across interactions
- [ ] Charts render correctly
- [ ] Responsive on different screen sizes
- [ ] No console errors in browser

### Common Issues

**Issue**: Page refreshes unexpectedly  
**Solution**: Use `st.form` for inputs that trigger reruns

**Issue**: Session state lost  
**Solution**: Check if `st.experimental_rerun()` is called unnecessarily

**Issue**: Charts not rendering  
**Solution**: Verify data types (convert numpy types to Python types)

**Issue**: API calls failing  
**Solution**: Check backend is running, verify URL, check CORS settings

---

## 📝 Component Checklist

When creating new frontend components:

- [ ] Read `docs/AI_DEVELOPMENT_RULES.md`
- [ ] Follow existing patterns in this guide
- [ ] Initialize session state properly
- [ ] Add error handling
- [ ] Add loading indicators
- [ ] Make responsive (use `use_container_width=True`)
- [ ] Test on different browsers
- [ ] Update this guide if creating new patterns

---

## 🔗 Related Documentation

- [DEVELOPMENT_GUIDE.md](../DEVELOPMENT_GUIDE.md) - General development
- [ILI_VISUAL_TOOL.md](ILI_VISUAL_TOOL.md) - Example implementation
- [DASHBOARD.md](DASHBOARD.md) - Dashboard patterns
- [Streamlit Docs](https://docs.streamlit.io) - Official documentation

---

**Last Updated**: October 2025  
**Framework Version**: Streamlit 1.31+
