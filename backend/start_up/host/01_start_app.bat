@echo off
setlocal

set "BASE_DIR=%~dp0..\.."
pushd "%BASE_DIR%"

echo [INFO] Starting local app on http://127.0.0.1:8000
powershell -NoProfile -ExecutionPolicy Bypass -File ".\ops\start_app.ps1" -InstallDeps

echo.
echo [INFO] Waiting for backend to become ready on 127.0.0.1:8000 ...

set /a TRIES=0
:WAIT_LOOP
set /a TRIES+=1
if %TRIES% GTR 30 (
    echo [ERROR] Backend did not respond after 30 seconds.
    echo [ERROR] Check waitress output above. Exiting.
    popd
    endlocal
    exit /b 1
)

:: Try to connect - curl returns 0 on HTTP response (any code), non-zero on connection refused
curl -s --max-time 1 http://127.0.0.1:8000/ >nul 2>nul
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto WAIT_LOOP
)

echo [OK] Backend is responding on http://127.0.0.1:8000
echo [INFO] Keep this window open.

popd
endlocal
