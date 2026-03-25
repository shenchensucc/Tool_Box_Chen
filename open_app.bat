@echo off
REM One-click: backend + frontend in separate windows, then open the UI in your browser.
cd /d "%~dp0"

echo Starting Chen's Engineer Toolbox (backend + frontend)...
echo.

start "Toolbox Backend (8000)" cmd /k "%~dp0run_backend.bat"
REM Give the API a moment to bind before Streamlit starts
ping 127.0.0.1 -n 4 >nul

start "Toolbox Frontend (8501)" cmd /k "%~dp0run_frontend.bat"
REM Brief wait so Streamlit can listen before the browser opens
ping 127.0.0.1 -n 6 >nul

start "" "http://localhost:8501"
echo Opened http://localhost:8501 - keep the Backend and Frontend windows running.
echo.
