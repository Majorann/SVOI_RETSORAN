@echo off
setlocal

for %%I in ("%~dp0") do set "HOST_DIR=%%~fI"

echo [INFO] Starting local app in a new window...
start "SVOI RESTORAN - APP" cmd /k call "%HOST_DIR%01_start_app.bat"

echo [INFO] Waiting 10 seconds for backend to start before tunnel...
echo [INFO] Watch the APP window for [OK] Backend is responding.
timeout /t 10 /nobreak >nul

echo [INFO] Starting public tunnel in a new window...
start "SVOI RESTORAN - TUNNEL" cmd /k call "%HOST_DIR%02_start_public_tunnel.bat"

echo.
echo [DONE] Two windows started:
echo        1) SVOI RESTORAN - APP    ^<-- watch for [OK] Backend is responding
echo        2) SVOI RESTORAN - TUNNEL ^<-- watch for URL from localhost.run
echo.
echo Main mode now uses localhost.run (more stable on your network).
echo Optional fallback script for Cloudflare:
echo   02_start_public_tunnel_cloudflare.bat
echo.
pause

endlocal
