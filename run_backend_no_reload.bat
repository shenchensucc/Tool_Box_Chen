@echo off
REM Backend without --reload: use for long jobs (e.g. dig package generation) so saving
REM code files does not restart the server mid-request. Restart manually after code changes.

echo Starting Chen's Engineer Toolbox - Backend API (no hot reload)
echo ================================================================
echo.
echo Backend: http://localhost:8000
echo API docs: http://localhost:8000/docs
echo.
echo Code changes will NOT auto-reload. Stop this window and run run_backend.bat for dev.
echo.

cd /d "%~dp0"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start backend!
    pause
)
