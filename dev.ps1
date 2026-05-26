# Safe-CLI-Agent 开发模式一键启动 (PowerShell)
# 双击此脚本或在 PowerShell 中运行

$Host.UI.RawUI.WindowTitle = "Safe-CLI-Agent"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Safe-CLI-Agent 桌面端 (开发模式)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  - 自动清理端口 8000 残留进程"
Write-Host "  - 自动启动 Python 后端"
Write-Host "  - 自动打开 Electron 窗口"
Write-Host ""
Write-Host "按 Ctrl+C 退出"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

# 启动 Electron 开发模式
npm run dev
