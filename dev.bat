@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo   Safe-CLI-Agent Desktop (Dev Mode)
echo ========================================
echo.

echo [1/2] Building frontend...
cd /d "%~dp0frontend"
call npm run build
if errorlevel 1 (
    echo Frontend build failed! Check errors above.
    pause
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [2/2] Starting Electron...
echo   - Auto-clean port 8000
echo   - Auto-start Python backend
echo.
echo Press Ctrl+C to quit
echo ========================================
echo.

npm run dev
