@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..\..") do set "REPO_ROOT=%%~fI"
set "PY_CMD="

if not exist "%REPO_ROOT%\run_local.py" (
  echo [ERROR] run_local.py not found in "%REPO_ROOT%"
  pause
  exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)

if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
  )
)

if not defined PY_CMD (
  echo [ERROR] Python 3 is not available in PATH.
  echo [HINT] Install Python 3.10+ and enable "Add python.exe to PATH".
  pause
  exit /b 1
)

cd /d "%REPO_ROOT%"
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000/"
echo [INFO] Starting local development server: http://127.0.0.1:5000/
%PY_CMD% run_local.py --host 127.0.0.1 --port 5000

endlocal
