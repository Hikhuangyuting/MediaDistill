@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
cd /d "%~dp0"

echo MediaDistill · 影音萃取
echo 正在启动本地工作台……

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [错误] 尚未创建 .venv 运行环境。
  echo 请先双击“安装 MediaDistill.bat”，或在 PowerShell 中运行：
  echo python .\scripts\bootstrap.py
  pause
  exit /b 1
)

".venv\Scripts\python.exe" scripts\bootstrap.py --check
if errorlevel 1 (
  echo.
  echo [错误] 环境检查没有通过，请重新运行“安装 MediaDistill.bat”。
  echo 诊断日志：%CD%\logs\windows-install.log
  pause
  exit /b 1
)

".venv\Scripts\python.exe" run.py --web --port 8765
if errorlevel 1 (
  echo.
  echo [错误] 工作台异常退出，请查看上方错误信息。
  echo 如果提示端口占用，可在 PowerShell 中运行：
  echo .\.venv\Scripts\python.exe .\run.py --web --port 8766
  pause
  exit /b 1
)
