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
# From project root (all platforms):
streamlit run frontend/Home.py

# Or from frontend directory:
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

**To force-stop all app processes** (e.g. after closing terminal but app still running):
- Double-click `kill_app.bat`

---

## 🍎 Mac/Linux Users - Using Shell Scripts

**Run in terminal:**
```bash
./run_backend.sh    # Terminal 1
./run_frontend.sh   # Terminal 2
```

**To force-stop all app processes:**
```bash
./kill_app.sh
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

### App still running after closing terminal (ghost processes)
If the app seems to still be running after you killed the process or closed the terminal:
- **Windows**: Double-click `kill_app.bat` to force-kill all processes on ports 8000 and 8501
- **Mac/Linux**: Run `./kill_app.sh` in the project root
- Then restart with `run_backend.bat` / `run_frontend.bat` (or `.sh` on Mac/Linux)

### Backend code changes not taking effect
If you changed backend code but the app still behaves like before:
1. **Hard restart**: Run `kill_app.bat` (or `kill_app.sh`), then start backend again
2. **Clear Python cache**: Delete `backend/__pycache__` and `backend/**/__pycache__` folders, then restart
3. **Browser cache**: Do a hard refresh (Ctrl+Shift+R or Cmd+Shift+R) in the browser
4. **Streamlit cache**: If frontend calls backend, Streamlit may cache responses — click "Rerun" in the Streamlit UI or refresh the page

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
    ├─ 🔬 Metal Loss Assessment
    ├─ 📉 Metal Loss Mass Assessment
    └─ 📦 Dig Package Generator
```

---

## 📚 Need More Help?

See **[README.md](README.md)** for full documentation and [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) for detailed setup.

