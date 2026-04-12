@echo off
REM AegisKYC Production Server - Windows Batch Launcher
REM No PowerShell execution policy issues

echo ========================================
echo   AegisKYC Production Server (Windows)
echo ========================================
echo.

REM Check if waitress is installed
python -c "import waitress" 2>nul
if errorlevel 1 (
    echo Installing production dependencies...
    pip install waitress
    echo.
)

REM Start the production server
echo Starting production server...
echo.
python start_production_simple.py

pause
