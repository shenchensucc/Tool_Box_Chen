# 🔧 Chen's Engineer Toolbox

A Python-based web application providing tools for facility and pipeline engineering, featuring interactive data visualization and analysis capabilities.

## 🎯 Features

- **📊 Dashboard**: Project overview and activity tracking
- **🏭 Facility Tools**: Facility management and analysis (coming soon)
- **🛢️ Pipeline Tools**:
  - **ILI Visual Tool**: Upload and analyze In-Line Inspection (ILI) data from Excel files

## 🏗️ Architecture

- **Frontend**: Streamlit (pure Python UI)
- **Backend**: FastAPI (RESTful API)
- **Visualization**: Plotly (interactive charts)
- **Data Processing**: pandas, openpyxl
- **Validation**: Pydantic
- **Tooling**: uv (package management), ruff (linting), black (formatting)

## 📁 Project Structure

```
Tool_Box_Chen/
├── frontend/
│   ├── Home.py                    # Cover page
│   ├── pages/
│   │   ├── 1_Dashboard.py         # Dashboard overview
│   │   ├── 2_Facility.py          # Facility tools
│   │   └── 3_Pipeline/
│   │       └── ILI_Visual_Tool.py # ILI data analysis tool
│   ├── frontend_utils.py          # Shared utilities
│   └── __init__.py
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── models.py                  # Pydantic models
│   └── __init__.py
├── tests/                         # Test files
├── pyproject.toml                 # Project configuration
├── .pre-commit-config.yaml        # Pre-commit hooks
├── .gitignore
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd Tool_Box_Chen
```

2. **Install dependencies** (choose one method):

**Using uv (recommended):**
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

**Using pip:**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Running the Application

You need to run both the backend and frontend in separate terminals:

**Terminal 1 - Backend API:**
```bash
# Using uv:
uv run uvicorn backend.main:app --reload

# Using pip (with venv activated):
uvicorn backend.main:app --reload
```

The backend will start at `http://127.0.0.1:8000`

**Terminal 2 - Frontend UI:**
```bash
# Using uv:
uv run streamlit run frontend/Home.py

# Using pip (with venv activated):
streamlit run frontend/Home.py
```

The frontend will open automatically in your browser at `http://localhost:8501`

## 🛠️ API Endpoints

### Backend API

- **GET** `/health` - Health check
- **POST** `/api/ili/preview` - Preview Excel file structure
- **POST** `/api/ili/process` - Process ILI data and return statistics

Visit `http://127.0.0.1:8000/docs` for interactive API documentation (Swagger UI).

## 📊 Using the ILI Visual Tool

1. Navigate to **Pipeline → ILI Visual Tool** in the sidebar
2. Upload an Excel file (.xlsx or .xls) containing ILI data
3. Click **Preview File** to see sheets and columns
4. Select the sheet and map columns (distance, depth, metal loss)
5. Click **Process Data** to generate:
   - Statistical summaries
   - Distribution histograms
   - Distance-based scatter plots
   - Box plots
6. Download processed results as CSV

### Expected Excel Format

Your Excel file should contain columns such as:
- **Distance/Location**: Position along the pipeline
- **Depth**: Anomaly depth measurements
- **Metal Loss**: Percentage of metal loss
- Other numeric inspection metrics

## 🧪 Development

### Code Quality

**Format code:**
```bash
# Using uv:
uv run black .
uv run ruff check --fix .

# Using pip:
black .
ruff check --fix .
```

**Install pre-commit hooks:**
```bash
# Using uv:
uv run pre-commit install

# Using pip:
pre-commit install
```

### Running Tests

```bash
# Using uv:
uv run pytest

# Using pip:
pytest
```

## 📝 Configuration

### Environment Variables

Create a `.env` file in the project root (optional):

```env
# Backend Configuration
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
BACKEND_URL=http://127.0.0.1:8000

# Frontend Configuration
FRONTEND_PORT=8501

# File Upload Limits
MAX_FILE_SIZE_MB=10

# Development
DEBUG=true
```

## 🎨 Features by Tool

### ILI Visual Tool

- ✅ Excel file upload (max 10 MB)
- ✅ Multi-sheet support
- ✅ Column mapping interface
- ✅ Statistical analysis (mean, std, min, max, quartiles)
- ✅ Interactive histograms
- ✅ Distance-based scatter plots with color mapping
- ✅ Box plots for distribution analysis
- ✅ CSV export of statistics
- ✅ Real-time processing feedback

## 🔒 Security

- File size validation (10 MB limit)
- Excel file type validation
- Temporary file cleanup after processing
- CORS configured for local development only

## 🚧 Roadmap

- [ ] Add more facility tools
- [ ] Implement user authentication
- [ ] Add database for project persistence
- [ ] Support for more file formats (CSV, JSON)
- [ ] Advanced filtering and data transformation
- [ ] Report generation (PDF export)
- [ ] Multi-user collaboration features

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👤 Author

**Chen**

---

**Version**: 0.1.0  
**Built with**: Streamlit + FastAPI + Python 3.11

For questions or support, please open an issue on GitHub. 