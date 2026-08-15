@echo off
setlocal
set "PYTHONUTF8=1"
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
cd /d "%~dp0"

echo MediaDistill - Windows Setup
echo.

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  echo [ERROR] Python 3.10 or newer was not found.
  echo Run this command in PowerShell:
  echo winget install -e --id Python.Python.3.13
  echo Close this window after installation, then run this file again.
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.10 or newer is required.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ffmpeg was not found.
  echo Run this command in PowerShell:
  echo winget install -e --id Gyan.FFmpeg
  echo Then close all terminal windows and run this file again.
  pause
  exit /b 1
)

where ffprobe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] ffprobe was not found. Reinstall the complete FFmpeg package.
  pause
  exit /b 1
)

%PYTHON_CMD% scripts\bootstrap.py
if errorlevel 1 goto :failed

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv\Scripts\python.exe was not created.
  goto :failed
)

".venv\Scripts\python.exe" scripts\bootstrap.py --check
if errorlevel 1 goto :failed

echo.
echo Setup completed. You can now run the MediaDistill launcher BAT file.
pause
exit /b 0

:failed
echo.
echo [ERROR] Setup did not finish. Review the messages above.
echo Diagnostic log: %CD%\logs\windows-install.log
echo You can also run this command from PowerShell in this folder:
echo python .\scripts\bootstrap.py
pause
exit /b 1
