@echo off
setlocal

set "BASE_DIR=%~dp0..\.."
pushd "%BASE_DIR%"

echo [INFO] Starting local app on http://127.0.0.1:8000
powershell -NoProfile -ExecutionPolicy Bypass -File ".\ops\start_app.ps1" -InstallDeps

popd
endlocal
