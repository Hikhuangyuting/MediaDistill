@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"

echo MediaDistill · Windows 首次安装
echo.

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  echo [错误] 未找到 Python 3.10 或更高版本。
  echo 可在 PowerShell 中运行：
  echo winget install -e --id Python.Python.3.13
  echo 安装后请关闭本窗口，重新双击本脚本。
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo [错误] 当前 Python 版本低于 3.10，请升级后重试。
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 ffmpeg。
  echo 可在 PowerShell 中运行：
  echo winget install -e --id Gyan.FFmpeg
  echo 安装后请重新打开终端，再双击本脚本。
  pause
  exit /b 1
)

where ffprobe >nul 2>nul
if errorlevel 1 (
  echo [错误] 已找到 ffmpeg，但未找到 ffprobe。请重新安装完整 ffmpeg 套件。
  pause
  exit /b 1
)

echo 正在创建 Python 虚拟环境……
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :failed

echo 正在安装 Python 依赖……
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo 安装完成。以后双击“启动 MediaDistill.bat”即可使用。
pause
exit /b 0

:failed
echo.
echo [错误] 安装未完成，请查看上方错误信息。
pause
exit /b 1
