@echo off

echo Starting Chen's Engineer Toolbox - Backend API
echo ==============================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using uv to run backend...
    uv run uvicorn backend.main:app --reload
) else (
    echo Using uvicorn directly...
    uvicorn backend.main:app --reload
) 