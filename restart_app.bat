@echo off
REM Kill toolbox processes (ports 8000 + 8501), wait for ports to release, then start backend + frontend + browser.
cd /d "%~dp0"

echo.
echo ============================================
echo  Restart - Chen's Engineer Toolbox
echo ============================================
echo.

call "%~dp0kill_app.bat" nopause

echo Waiting for ports to release...
timeout /t 3 /nobreak >nul

call "%~dp0open_app.bat"
