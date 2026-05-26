@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Safe-CLI-Agent 桌面端 (开发模式)
echo ========================================
echo.
echo 正在启动...
echo   - 自动清理端口 8000 残留进程
echo   - 自动启动 Python 后端
echo   - 自动打开 Electron 窗口
echo.
echo 按 Ctrl+C 退出
echo ========================================
echo.

npm run dev
