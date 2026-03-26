# 🔧 Chen's Engineer Toolbox

A Python-based web application providing tools for facility and pipeline engineering, featuring interactive data visualization and analysis capabilities.

## 🎯 Features

- **📊 Dashboard**: Project overview and activity tracking
- **🏭 Facility Tools**:
  - **TML Data Loader**: Process Thickness Monitoring Location (TML) data with 20 customizable workflows
- **🛢️ Pipeline Tools**:
  - **ILI Visual Tool**: Upload or paste In-Line Inspection (ILI) data for the unwrapped pipe feature map
  - **Dig Package Visual Tool**: Visualize ILI features and longseam lines from dig package Excel (Feature summary + Joint Summary)
  - **Metal Loss Assessment**: Assess pipeline metal loss features using modified B31G methodology with corrosion growth projections
  - **Metal Loss Mass Assessment**: Mass assessment of metal loss features across multiple pipeline segments
  - **Dig Package Generator**: Generate dig packages from MDL, ILI data, and template files

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
├── frontend/                      # Frontend UI (Streamlit)
│   ├── Home.py                    # Landing page (entry point)
│   ├── frontend_utils.py          # Shared utilities and API clients
│   ├── pages/                     # Streamlit pages (auto-discovered)
│   │   ├── 1_Dashboard.py         # Dashboard overview
│   │   ├── 2_TML_Data_Loader.py   # TML data processing tool
│   │   ├── 3_Dig_Package_Visual_Tool.py  # Dig package Excel → feature map + workbook preview
│   │   ├── 3_ILI_Visual_Tool.py   # ILI upload / paste → feature map
│   │   ├── 4_Metal_Loss_Assessment.py  # Metal loss assessment tool
│   │   ├── 5_Dig_Package_Generator.py  # Dig package generation tool
│   │   └── 6_Metal_Loss_Mass_Assessment.py  # Metal loss mass assessment tool
│   └── __init__.py
├── backend/                       # Backend API (FastAPI)
│   ├── main.py                    # FastAPI application and endpoints
│   ├── models.py                   # Pydantic models for API validation
│   ├── pipeline/                  # Pipeline engineering tools
│   │   ├── ili_reader.py          # ILI data reading and processing
│   │   ├── dig_package.py         # Dig package generation
│   │   ├── metal_loss.py          # Metal loss assessment calculations
│   │   └── report_generator.py    # Word report generation
│   ├── tml/                       # Thickness Monitoring Location tools
│   │   ├── file_handler.py        # Excel file handling utilities
│   │   ├── data_processor.py      # Data processing utilities
│   │   └── workflows/             # TML workflow modules (20 workflows)
│   │       ├── _01_status.py      # Status indicator workflow
│   │       ├── _02_follow_up_cml.py
│   │       ├── _03_code_year_tmin.py
│   │       ├── _04_design_code.py
│   │       ├── _05_material_spec.py
│   │       ├── _06_material_grade.py
│   │       ├── _07_design_temperature.py
│   │       ├── _08_piping_formula.py
│   │       ├── _09_od.py
│   │       ├── _10_nps.py
│   │       ├── _11_schedule.py
│   │       ├── _12_design_pressure.py
│   │       ├── _13_temperature_coefficient.py
│   │       ├── _14_tnom.py
│   │       ├── _15_tmin.py
│   │       ├── _16_override_allowable_stress.py
│   │       ├── _17_allowable_stress.py
│   │       ├── _18_design_factor.py
│   │       ├── _19_joint_factor.py
│   │       └── _20_location_factor.py
│   └── __init__.py
├── tests/                         # Test suite
│   ├── test_backend.py            # Backend API tests
│   └── test_metal_loss.py         # Metal loss calculation tests
├── docs/                          # 📚 Comprehensive documentation
│   ├── README.md                  # Documentation hub
│   ├── ARCHITECTURE.md            # System architecture guide
│   ├── DEVELOPMENT_GUIDE.md      # Development practices
│   ├── AI_DEVELOPMENT_RULES.md    # ⚠️ CRITICAL for AI development
│   ├── CODE_REVIEW_CHECKLIST.md   # Code review standards
│   ├── PROJECT_STRUCTURE.md      # File organization guide
│   ├── FILE_MANAGEMENT.md        # Documentation file management
│   └── functions/                 # Function-specific guides
│       ├── BACKEND_API.md         # Backend API development guide
│       ├── DASHBOARD.md           # Dashboard functionality
│       ├── FACILITY.md            # Facility tools guide
│       ├── ILI_VISUAL_TOOL.md     # ILI tool development
│       ├── TML_DATA_LOADER.md     # TML data loader guide
│       └── FRONTEND_COMPONENTS.md # Frontend UI patterns
├── pyproject.toml                 # Project configuration (uv/pip)
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
├── run_backend.sh                 # Backend startup script (Linux/Mac)
├── run_backend.bat                # Backend startup script (Windows)
├── run_frontend.sh                # Frontend startup script (Linux/Mac)
├── run_frontend.bat               # Frontend startup script (Windows)
├── HOW_TO_OPEN_APP.md             # Quick run reference
├── TESTING_GUIDE.md               # Testing guidelines
├── .gitignore                     # Git ignore rules
└── README.md                      # This file
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

2. **Set up environment variables** (required for Chat with Chen and web search):
```bash
# Copy the example and add your token (never commit .env)
# Windows: copy .env.example .env
# macOS/Linux: cp .env.example .env
# Edit .env and set AI_BUILDER_TOKEN=your_token_here
```

3. **Install dependencies** (choose one method):

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

> ⚠️ **Secrets**: Keep `AI_BUILDER_TOKEN` in `.env` only. `.env` is in `.gitignore` and must never be committed.

### Running the Application

You need to run both the backend and frontend in separate terminals:

**Terminal 1 - Backend API:**
```bash
# Using uv:
uv run uvicorn backend.main:app --reload --reload-dir backend

# Using pip (with venv activated):
uvicorn backend.main:app --reload --reload-dir backend
```

> **Windows**: If hot reload doesn't detect changes, set `WATCHFILES_FORCE_POLLING=True` before running. The `run_backend.bat` script does this automatically.

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

**Health & Status:**
- **GET** `/health` - Health check endpoint

**ILI (In-Line Inspection) Tools:**
- **POST** `/api/ili/preview` - Preview Excel file structure (sheets, columns, row counts)
- **POST** `/api/ili/process` - Process ILI data and return statistics, histograms, and scatter plots

**TML (Thickness Monitoring Location) Tools:**
- **POST** `/api/tml/process` - Process TML data with selected workflows and return ZIP file with outputs

**Pipeline Metal Loss Assessment:**
- **POST** `/api/pipeline/metal-loss/assess` - Assess metal loss feature and return calculated results
- **POST** `/api/pipeline/metal-loss/mass-assess` - Bulk assess metal loss features from Excel for 10-year Pf decay
- **POST** `/api/pipeline/metal-loss/export-word` - Generate and download Word document report

Visit `http://127.0.0.1:8000/docs` for interactive API documentation (Swagger UI).

## 📊 Using the Tools

### ILI Visual Tool

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

**Expected Excel Format:**
Your Excel file should contain columns such as:
- **Distance/Location**: Position along the pipeline
- **Depth**: Anomaly depth measurements
- **Metal Loss**: Percentage of metal loss
- Other numeric inspection metrics

### TML Data Loader

1. Navigate to **Facility → TML Data Loader** in the sidebar
2. Upload two Excel files:
   - **Source File**: Contains TML data with `Source_Data` sheet
   - **Template File**: Contains `Assets` and `TML` sheets (TM_Loader.xlsx)
3. Select workflows to process (1-20) using checkboxes
4. Click **Process TML Data** to generate output files
5. Download the ZIP file containing all processed outputs

**Required File Structure:**
- Source file must have `Source_Data` sheet with required columns
- Template file must have `Assets` and `TML` sheets
- See [`docs/functions/TML_DATA_LOADER.md`](docs/functions/TML_DATA_LOADER.md) for detailed requirements

### Metal Loss Assessment

1. Navigate to **Pipeline → Metal Loss Assessment** in the sidebar
2. Select a preset scenario or choose "Customized" to input all parameters
3. Fill in pipe properties, defect information, and growth rates
4. Click **Run Assessment** to calculate:
   - Defect depth growth projections
   - Safe Operating Pressure (SOP) decay
   - 80% wall thickness cutoff tracking
5. View interactive charts and download Word report

**Methodology:**
Uses Modified B31G methodology with corrosion growth rate projections. See help section in the tool for detailed methodology information.

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

### 📝 Planning File Management

**⚠️ IMPORTANT**: When planning new functions or features:
- ✅ **DO**: Update `README.md` Features section with new function descriptions
- ✅ **DO**: Update `README.md` Roadmap section (mark completed items)
- ✅ **DO**: Create/update function guide in `docs/functions/` if needed
- ✅ **DO**: Document API changes in `docs/functions/BACKEND_API.md`
- ❌ **DON'T**: Create temporary planning files (`*_SUMMARY.md`, `*_PLAN.md`, `*_INTEGRATION.md`) at root
- ❌ **DON'T**: Leave planning files after implementation is complete

**After completing a feature:**
1. Extract important information from any temporary planning files
2. Consolidate into `README.md` (features/roadmap) or relevant function guides
3. Delete temporary planning files

See [`docs/FILE_MANAGEMENT.md`](docs/FILE_MANAGEMENT.md) for detailed cleanup process.

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
MAX_FILE_SIZE_MB=30

# Development
DEBUG=true
```

## 🎨 Features by Tool

### TML Data Loader

- ✅ Excel file upload (source + template files)
- ✅ 20 customizable workflows for data processing
- ✅ Batch processing with workflow selection
- ✅ Automatic data filtering and mapping
- ✅ Output generation as ZIP file
- ✅ Support for multiple output files per workflow
- ✅ Real-time processing feedback

### ILI Visual Tool

- ✅ Excel file upload (max 30 MB)
- ✅ Multi-sheet support
- ✅ Column mapping interface
- ✅ Statistical analysis (mean, std, min, max, quartiles)
- ✅ Interactive histograms
- ✅ Distance-based scatter plots with color mapping
- ✅ Box plots for distribution analysis
- ✅ CSV export of statistics
- ✅ Real-time processing feedback

### Metal Loss Assessment

- ✅ Modified B31G methodology implementation
- ✅ Corrosion growth rate projections (low, average, high scenarios)
- ✅ Safe Operating Pressure (SOP) calculations
- ✅ Interactive depth growth charts
- ✅ SOP decay visualization
- ✅ 80% wall thickness cutoff tracking
- ✅ Word document report generation
- ✅ Test case validation (Standard compatibility)

### Metal Loss Mass Assessment

- ✅ Mass assessment of metal loss features across multiple pipeline segments
- ✅ Batch processing support
- ✅ Excel data integration

### Dig Package Generator

- ✅ Upload MDL, ILI data, and template files
- ✅ Generate dig packages for pipeline excavation planning
- ✅ Excel-to-PDF conversion (Windows)

## 🔒 Security

- File size validation (100 MB limit per file)
- Excel file type validation (extension checking)
- Temporary file cleanup after processing
- CORS configured for local development
- Input validation via Pydantic models
- Secure temporary file handling

## 🚧 Roadmap

- [x] TML Data Loader with 20 workflows
- [x] Metal Loss Assessment tool
- [x] Metal Loss Mass Assessment tool
- [x] Dig Package Generator
- [x] Word document report generation
- [ ] Implement user authentication
- [ ] Add database for project persistence
- [ ] Support for more file formats (CSV, JSON)
- [ ] Advanced filtering and data transformation
- [ ] PDF export for reports
- [ ] Multi-user collaboration features
- [ ] File content validation (magic number checking)
- [ ] Rate limiting for API endpoints

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
- ⚙️ [**TML Data Loader**](docs/functions/TML_DATA_LOADER.md) - TML data processing guide
- 🔌 [**Backend API**](docs/functions/BACKEND_API.md) - API development
- 🎨 [**Frontend Components**](docs/functions/FRONTEND_COMPONENTS.md) - UI patterns

### Quick Links
- For quick setup: [HOW_TO_OPEN_APP.md](HOW_TO_OPEN_APP.md)
- For project overview: [docs/README.md](docs/README.md)

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