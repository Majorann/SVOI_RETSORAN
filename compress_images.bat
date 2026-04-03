@echo off
setlocal
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%backend\.venv\Scripts\python.exe"
set "TARGET_SIZE=%~1"
set "TARGET_DIR=%~2"
set "QUALITY=%~3"

if not defined TARGET_SIZE set "TARGET_SIZE=480"
if not defined TARGET_DIR set "TARGET_DIR=%SCRIPT_DIR%backend\static\menu_items"
if not defined QUALITY set "QUALITY=82"

if exist "%VENV_PYTHON%" (
  set "PYTHON_BIN=%VENV_PYTHON%"
  set "PYTHON_ARGS="
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_BIN=py"
    set "PYTHON_ARGS=-3"
  ) else (
    set "PYTHON_BIN=python"
    set "PYTHON_ARGS="
  )
)

echo Using Python: %PYTHON_BIN% %PYTHON_ARGS%
echo Target folder: %TARGET_DIR%
echo Target size: %TARGET_SIZE%x%TARGET_SIZE%
echo Quality: %QUALITY%
echo.

call "%PYTHON_BIN%" %PYTHON_ARGS% -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo Pillow is not installed. Installing it now...
  call "%PYTHON_BIN%" %PYTHON_ARGS% -m pip install Pillow
  if errorlevel 1 (
    echo Failed to install Pillow.
    exit /b 1
  )
)

call "%PYTHON_BIN%" %PYTHON_ARGS% "%SCRIPT_DIR%backend\ops\resize_images.py" "%TARGET_DIR%" --size %TARGET_SIZE% --quality %QUALITY%
exit /b %errorlevel%
