# 🚀 Quick Start Guide

Get Chen's Engineer Toolbox up and running in 3 steps!

## Step 1: Install Dependencies

Choose your preferred method:

### Option A: Using uv (Recommended - Faster!)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or on Windows with PowerShell:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install project dependencies
uv sync
```

### Option B: Using pip

```bash
# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# Or with dev dependencies:
pip install -e ".[dev]"
```

## Step 2: Start the Backend

Open a terminal and run:

**Windows:**
```bash
run_backend.bat
```

**macOS/Linux:**
```bash
./run_backend.sh
```

**Or manually:**
```bash
uv run uvicorn backend.main:app --reload
```

✅ Backend will start at: http://127.0.0.1:8000  
📚 API docs available at: http://127.0.0.1:8000/docs

## Step 3: Start the Frontend

Open a **second terminal** and run:

**Windows:**
```bash
run_frontend.bat
```

**macOS/Linux:**
```bash
./run_frontend.sh
```

**Or manually:**
```bash
uv run streamlit run frontend/Home.py
```

✅ Frontend will open automatically in your browser at: http://localhost:8501

## 🎉 You're Ready!

Navigate through the sidebar:
- **Home**: Welcome page
- **Dashboard**: Project overview
- **Facility**: Facility tools (coming soon)
- **Pipeline → ILI Visual Tool**: Upload and analyze Excel files!

## 📝 Testing the ILI Tool

1. Navigate to **Pipeline → ILI Visual Tool**
2. Upload an Excel file with numeric data
3. Preview the file structure
4. Map columns (distance, depth, metal loss)
5. Process and view visualizations!

## 🆘 Troubleshooting

### Backend not starting?
- Make sure port 8000 is not in use
- Check that all dependencies are installed
- Verify Python 3.11+ is installed: `python --version`

### Frontend not connecting to backend?
- Ensure backend is running first
- Check the backend URL in frontend (default: http://127.0.0.1:8000)

### Import errors?
- Reinstall dependencies: `uv sync` or `pip install -r requirements.txt`
- Make sure you're in the project root directory

## 📖 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check API documentation at http://127.0.0.1:8000/docs
- Set up pre-commit hooks: `uv run pre-commit install`

---

Need help? Check the README or open an issue on GitHub! 