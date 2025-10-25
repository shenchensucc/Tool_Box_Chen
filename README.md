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
│   │   ├── 1_Dashboard.py              # Dashboard overview
│   │   ├── Facility/                   # Facility tools (expandable)
│   │   │   └── TML_Data_Loader.py      # TML data processing
│   │   └── Pipeline/                   # Pipeline tools (expandable)
│   │       └── ILI_Visual_Tool.py      # ILI data analysis tool
│   ├── frontend_utils.py          # Shared utilities
│   └── __init__.py
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── models.py                  # Pydantic models
│   └── __init__.py
├── tests/                         # Test files
├── docs/                          # 📚 Comprehensive documentation
│   ├── README.md                  # Documentation hub
│   ├── AI_DEVELOPMENT_RULES.md    # ⚠️ CRITICAL for AI development
│   ├── CODE_REVIEW_CHECKLIST.md   # Code review standards
│   └── functions/                 # Function-specific guides
├── pyproject.toml                 # Project configuration
├── .pre-commit-config.yaml        # Pre-commit hooks
├── .gitignore
└── README.md
```

> 📚 **New!** Comprehensive documentation is now available in the [`docs/`](docs/) folder. See [`docs/README.md`](docs/README.md) for the documentation hub.

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

> ⚠️ **PowerShell Users**: When running commands manually with `cd`, use semicolon `;` instead of `&&` to chain commands (e.g., `cd frontend; python -m streamlit run Home.py`). PowerShell does not support the `&&` operator.

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

> 📚 **For comprehensive development guidelines**, see [`docs/DEVELOPMENT_GUIDE.md`](docs/DEVELOPMENT_GUIDE.md)

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

### 🤖 AI-Assisted Development

**⚠️ CRITICAL**: If using AI assistance for development, **MUST READ** [`docs/AI_DEVELOPMENT_RULES.md`](docs/AI_DEVELOPMENT_RULES.md) before making any code changes to prevent over-modification and scope creep.

### 📋 Code Reviews

Use [`docs/CODE_REVIEW_CHECKLIST.md`](docs/CODE_REVIEW_CHECKLIST.md) for consistent, senior-level code reviews across all functions.

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

## 📚 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) folder:

### For Developers
- 📖 [**Documentation Hub**](docs/README.md) - Start here for all documentation
- 🏗️ [**Architecture Guide**](docs/ARCHITECTURE.md) - System design and tech stack
- 🛠️ [**Development Guide**](docs/DEVELOPMENT_GUIDE.md) - Development practices and setup
- 🤖 [**AI Development Rules**](docs/AI_DEVELOPMENT_RULES.md) - ⚠️ **CRITICAL** for AI-assisted development
- 📋 [**Code Review Checklist**](docs/CODE_REVIEW_CHECKLIST.md) - Senior-level review standards
- 📁 [**Project Structure**](docs/PROJECT_STRUCTURE.md) - File organization guide

### Function-Specific Guides
- 🛢️ [**ILI Visual Tool**](docs/functions/ILI_VISUAL_TOOL.md) - ILI tool development
- 📊 [**Dashboard**](docs/functions/DASHBOARD.md) - Dashboard functionality
- 🏭 [**Facility Tools**](docs/functions/FACILITY.md) - Facility management
- 🔌 [**Backend API**](docs/functions/BACKEND_API.md) - API development
- 🎨 [**Frontend Components**](docs/functions/FRONTEND_COMPONENTS.md) - UI patterns

### Quick Links
- For quick setup: [QUICK_START.md](QUICK_START.md)
- For project overview: [docs/DOCUMENTATION_SETUP_COMPLETE.md](docs/DOCUMENTATION_SETUP_COMPLETE.md)

## 🤝 Contributing

1. Fork the repository
2. **Read** [`docs/AI_DEVELOPMENT_RULES.md`](docs/AI_DEVELOPMENT_RULES.md) if using AI assistance
3. **Read** relevant function guide in [`docs/functions/`](docs/functions/)
4. Create a feature branch (`git checkout -b feature/AmazingFeature`)
5. Make changes (follow scope constraints!)
6. Write tests and update documentation
7. **Review** changes using [`docs/CODE_REVIEW_CHECKLIST.md`](docs/CODE_REVIEW_CHECKLIST.md)
8. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
9. Push to the branch (`git push origin feature/AmazingFeature`)
10. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👤 Author

**Chen**

---

**Version**: 0.1.0  
**Built with**: Streamlit + FastAPI + Python 3.11

For questions or support, please open an issue on GitHub. 