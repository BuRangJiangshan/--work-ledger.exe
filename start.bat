@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ==== 优先使用打包好的 exe ====
if exist "release\work-ledger\work-ledger.exe" (
    echo 正在启动「事项办理全程留痕工具」(exe 模式)...
    start "" "release\work-ledger\work-ledger.exe"
    exit /b 0
)

REM ==== 开发模式 ====
if exist "backend\app_pack.py" (
    echo 正在启动「事项办理全程留痕工具」(开发模式)...
    python backend\app_pack.py
    pause
    exit /b 0
)

echo [ERROR] 未找到可运行的启动入口
pause
exit /b 1
