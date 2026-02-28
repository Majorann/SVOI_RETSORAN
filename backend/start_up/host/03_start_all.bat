@echo off
setlocal

for %%I in ("%~dp0") do set "HOST_DIR=%%~fI"

echo [INFO] Starting local app in a new window...
start "SVOI RESTORAN - APP" cmd /k call "%HOST_DIR%01_start_app.bat"

echo [INFO] Waiting 4 seconds before tunnel start...
timeout /t 4 /nobreak >nul

echo [INFO] Starting public tunnel in a new window...
start "SVOI RESTORAN - TUNNEL" cmd /k call "%HOST_DIR%02_start_public_tunnel.bat"

echo [DONE] Two windows started:
echo        1) local app
echo        2) public tunnel
echo.
echo Public URL will appear in the tunnel window as:
echo https://<random>.lhr.life
echo.
pause

endlocal
