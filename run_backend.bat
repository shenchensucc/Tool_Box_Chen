@echo off

echo Starting Chen's Engineer Toolbox - Backend API
echo ==============================================
echo.
echo Starting backend at http://localhost:8000
echo API docs will be at http://localhost:8000/docs
echo.

cd /d "%~dp0"

REM Force polling mode for file watcher (fixes reload not detecting changes on Windows)
set WATCHFILES_FORCE_POLLING=True

REM Explicitly watch backend dir and subdirs for reliable hot reload
python -m uvicorn backend.main:app --reload --reload-dir backend

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start backend!
    echo.
    echo Please ensure:
    echo   1. Python 3.11+ is installed: python --version
    echo   2. Dependencies are installed: pip install -r requirements.txt
    echo   3. You are in the project root directory
    echo.
    pause
) 