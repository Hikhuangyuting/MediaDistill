@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo MediaDistill · 影音萃取
echo 正在启动本地工作台……

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [错误] 尚未安装运行环境。请先双击“安装 MediaDistill.bat”。
  pause
  exit /b 1
)

".venv\Scripts\python.exe" run.py --web --port 8765
if errorlevel 1 (
  echo.
  echo [错误] 工作台异常退出，请查看上方错误信息。
  pause
  exit /b 1
)
