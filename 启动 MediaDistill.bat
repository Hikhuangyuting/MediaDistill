@echo off
setlocal
set "PYTHONUTF8=1"
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
cd /d "%~dp0"

echo MediaDistill
echo Starting the local workspace...

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [ERROR] The .venv environment does not exist.
  echo Run the setup BAT file first, or run this command in PowerShell:
  echo python .\scripts\bootstrap.py
  pause
  exit /b 1
)

".venv\Scripts\python.exe" scripts\bootstrap.py --check
if errorlevel 1 (
  echo.
  echo [ERROR] Environment validation failed. Run the setup BAT file again.
  echo Diagnostic log: %CD%\logs\windows-install.log
  pause
  exit /b 1
)

".venv\Scripts\python.exe" run.py --web --port 8765
if errorlevel 1 (
  echo.
  echo [ERROR] MediaDistill stopped unexpectedly. Review the messages above.
  echo If port 8765 is already in use, run this command in PowerShell:
  echo .\.venv\Scripts\python.exe .\run.py --web --port 8766
  pause
  exit /b 1
)
