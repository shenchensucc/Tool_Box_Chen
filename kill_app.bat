@echo off
REM Hard kill all Tool Box processes (backend port 8000, frontend port 8501)
REM Use this when normal Ctrl+C or closing the terminal leaves processes running

echo.
echo ============================================
echo  Hard Kill - Chen's Engineer Toolbox
echo ============================================
echo.
echo Killing processes on ports 8000 (backend) and 8501 (frontend)...
echo.

REM Kill processes on port 8000 (backend)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000"') do (
    if not "%%a"=="" if not "%%a"=="0" (
        echo Killing PID %%a ^(port 8000^)...
        taskkill /F /PID %%a 2>nul
    )
)

REM Kill processes on port 8501 (frontend)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8501"') do (
    if not "%%a"=="" if not "%%a"=="0" (
        echo Killing PID %%a ^(port 8501^)...
        taskkill /F /PID %%a 2>nul
    )
)

echo.
echo Done. Ports 8000 and 8501 should now be free.
echo You can restart the app with run_backend.bat and run_frontend.bat
echo.
if /i not "%1"=="nopause" pause
