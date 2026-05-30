@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo   Safe-CLI-Agent
echo ========================================
echo.

cd /d "%~dp0"

if exist "frontend\dist\index.html" (
    echo [+] Frontend dist found, skipping build.
) else (
    echo [!] Frontend dist not found, building...
    echo.
    cd /d "%~dp0frontend"
    call npm run build
    if errorlevel 1 (
        echo.
        echo [X] Frontend build failed!
        pause
        exit /b 1
    )
    cd /d "%~dp0"
)

echo.
echo Starting Electron...
echo Press Ctrl+C to quit
echo ========================================
echo.

npm run dev
