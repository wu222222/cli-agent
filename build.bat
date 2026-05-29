@echo off
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo   Safe-CLI-Agent — Build & Start
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] Building frontend...
cd /d "%~dp0frontend"
call npm run build
if errorlevel 1 (
    echo.
    echo [X] Frontend build failed!
    pause
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [2/2] Starting Electron...
echo Press Ctrl+C to quit
echo ========================================
echo.

npm run dev
