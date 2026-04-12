@echo off

echo Starting Chen's Engineer Toolbox - Frontend UI
echo ==============================================
echo.
echo Starting frontend at http://localhost:8501
echo The app will open automatically in your browser
echo.

cd /d "%~dp0\frontend"
python -m streamlit run Home.py --server.headless true

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start frontend!
    echo.
    echo Please ensure:
    echo   1. Python 3.11+ is installed: python --version
    echo   2. Streamlit is installed: pip install streamlit
    echo   3. You are in the project root directory
    echo.
    pause
) 