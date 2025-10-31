# 🚀 How to Open This App

**Quick reference for opening Chen's Engineer Toolbox**

---

## ⚡ Quick Start (2 Terminals Required)

### Terminal 1: Start Backend
```bash
python -m uvicorn backend.main:app --reload
```
✅ Backend runs at: **http://localhost:8000**

### Terminal 2: Start Frontend
```bash
# macOS/Linux/Git Bash:
cd frontend && python -m streamlit run Home.py

# PowerShell (Windows):
cd frontend; python -m streamlit run Home.py
```
✅ Frontend opens at: **http://localhost:8501**

> ⚠️ **PowerShell Users**: Use semicolon `;` instead of `&&` to chain commands. PowerShell does not support the `&&` operator.

---

## 🪟 Windows Users - Using Batch Files

**Double-click or run:**
1. `run_backend.bat` (Terminal 1)
2. `run_frontend.bat` (Terminal 2)

---

## 🍎 Mac/Linux Users - Using Shell Scripts

**Run in terminal:**
```bash
./run_backend.sh    # Terminal 1
./run_frontend.sh   # Terminal 2
```

---

## ❗ Common Errors & Fixes

### "uvicorn is not recognized"
```bash
pip install uvicorn fastapi
```

### "streamlit is not recognized"
```bash
pip install streamlit
```

### "No module named 'backend'"
- Make sure you're in the **project root** directory
- Check: You should see both `backend/` and `frontend/` folders

### "Backend API is not available" (in frontend)
- Make sure **backend is running** in Terminal 1
- Check http://localhost:8000/health in your browser

### Port already in use
- Close other apps using ports 8000 or 8501
- Or change backend port: `python -m uvicorn backend.main:app --reload --port 8001`

---

## 📦 First Time Setup

If you haven't installed dependencies yet:
```bash
pip install -r requirements.txt
```

---

## 📍 What You'll See

Once both are running, open **http://localhost:8501** in your browser:

```
Sidebar Navigation:
├─ 🏠 Home
├─ 📊 Dashboard
├─ 🏭 Facility ▶️ (click to expand)
│   └─ ⚙️ TML Data Loader
└─ 🛢️ Pipeline ▶️ (click to expand)
    ├─ 📊 ILI Visual Tool
    └─ 🔬 Metal Loss Assessment
```

---

## 📚 Need More Help?

See **[QUICK_START.md](QUICK_START.md)** for detailed instructions and troubleshooting.

