# 🚀 Quick Start Guide

Get Chen's Engineer Toolbox up and running in 3 steps!

## Prerequisites

- **Python 3.11+** installed and added to PATH
- Verify: `python --version` should show 3.11 or higher

## Step 1: Install Dependencies

**From the project root directory**, run:

```bash
pip install -r requirements.txt
```

**Optional - Install development tools:**
```bash
pip install -r requirements-dev.txt
```

**Alternative - Using virtual environment (recommended):**
```bash
# Create virtual environment
python -m venv venv

# Activate it:
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Start the Backend

Open a terminal **in the project root directory** and run:

**Windows (using batch file):**
```bash
run_backend.bat
```

**macOS/Linux (using shell script):**
```bash
./run_backend.sh
```

**Or manually (works on all platforms):**
```bash
python -m uvicorn backend.main:app --reload
```

✅ Backend will start at: **http://localhost:8000**  
📚 API docs available at: **http://localhost:8000/docs**

**Keep this terminal window open!**

---

## Step 3: Start the Frontend

Open a **second terminal** (keep the backend running) and run:

**Windows (using batch file):**
```bash
run_frontend.bat
```

**macOS/Linux (using shell script):**
```bash
./run_frontend.sh
```

**Or manually:**
```bash
# macOS/Linux/Git Bash:
cd frontend && python -m streamlit run Home.py

# PowerShell (Windows):
cd frontend; python -m streamlit run Home.py
```

> ⚠️ **PowerShell Note**: Use semicolon `;` instead of `&&` to chain commands in PowerShell. The `&&` operator is not supported in PowerShell.

✅ Frontend will open automatically in your browser at: **http://localhost:8501**

**If it doesn't open automatically, manually navigate to http://localhost:8501**

## 🎉 You're Ready!

Navigate through the sidebar:
- **🏠 Home**: Welcome page
- **📊 Dashboard**: Project overview
- **🏭 Facility** (expandable): Click to expand and see:
  - **⚙️ TML Data Loader**: Process thickness monitoring location data
- **🛢️ Pipeline** (expandable): Click to expand and see:
  - **📊 ILI Visual Tool**: Upload and analyze in-line inspection Excel files

## 📝 Testing the Tools

### ILI Visual Tool (Pipeline Inspection)
1. Click **🛢️ Pipeline** in the sidebar to expand
2. Click **📊 ILI Visual Tool**
3. Upload an Excel file with numeric data
4. Click "Preview" to see file structure
5. Select sheet and map columns (distance, depth, metal loss)
6. Click "Process Data" and view visualizations!

### TML Data Loader (Facility Management)
1. Click **🏭 Facility** in the sidebar to expand
2. Click **⚙️ TML Data Loader**
3. Upload source Excel file and template file
4. Select workflows to process (up to 20 available)
5. Click "Process TML Data"
6. Download the generated ZIP file with results

## 🆘 Troubleshooting

### Backend not starting?

**"uvicorn is not recognized" or "No module named uvicorn":**
```bash
pip install uvicorn fastapi
```

**Port 8000 already in use:**
- Find and close the other application using port 8000
- Or change the port: `python -m uvicorn backend.main:app --reload --port 8001`

**"No module named 'backend'":**
- Make sure you're in the project root directory (not inside backend/ or frontend/)
- Check: `dir` (Windows) or `ls` (Mac/Linux) should show both `backend/` and `frontend/` folders

### Frontend not starting?

**"streamlit is not recognized" or "No module named streamlit":**
```bash
pip install streamlit
```

**"Cannot connect to backend" or "Backend API is not available":**
- Ensure the backend is running in a separate terminal
- Check that backend shows no errors
- Verify backend is at http://localhost:8000 (try opening in browser)

### Import errors?
- Reinstall dependencies: `pip install -r requirements.txt`
- Make sure you're in the project root directory
- Try with a fresh virtual environment

### Both terminals close immediately?
- Run commands directly in PowerShell/Command Prompt, not by double-clicking
- Or right-click the .bat file → "Run as Administrator"

### "The token '&&' is not a valid statement separator" error?
- **This is a PowerShell issue!** PowerShell doesn't support the `&&` operator
- **Solution**: Use semicolon `;` instead of `&&` to chain commands
- Example: `cd frontend; python -m streamlit run Home.py`
- Alternatively: Use the provided `.bat` files which handle this automatically

## 📖 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check API documentation at http://127.0.0.1:8000/docs
- Set up pre-commit hooks: `uv run pre-commit install`

---

Need help? Check the README or open an issue on GitHub! 