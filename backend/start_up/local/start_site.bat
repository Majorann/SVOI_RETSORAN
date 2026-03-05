@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "BACKEND_DIR=%%~fI"
set "VENV_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "PY_CMD="

if not exist "%BACKEND_DIR%\app.py" (
  echo [ERROR] app.py not found in "%BACKEND_DIR%"
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

if not exist "%VENV_PY%" (
  echo [INFO] Creating virtual environment...
  %PY_CMD% -m venv "%BACKEND_DIR%\.venv"
  if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    echo [HINT] Selected launcher: %PY_CMD%
    pause
    exit /b 1
  )
)

echo [INFO] Installing dependencies...
"%VENV_PY%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Failed to install dependencies.
  pause
  exit /b 1
)

cd /d "%BACKEND_DIR%"
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000/"
echo [INFO] Starting local development server: http://127.0.0.1:5000/
"%VENV_PY%" app.py

endlocal
