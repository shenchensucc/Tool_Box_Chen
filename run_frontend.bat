@echo off

echo Starting Chen's Engineer Toolbox - Frontend UI
echo ==============================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using uv to run frontend...
    uv run streamlit run frontend/Home.py
) else (
    echo Using streamlit directly...
    streamlit run frontend/Home.py
) 