@echo off
setlocal

where ssh >nul 2>nul
if errorlevel 1 (
    echo [ERROR] OpenSSH client not found. Install "OpenSSH Client" in Windows optional features.
    pause
    exit /b 1
)

echo [CHECK] Verifying origin is reachable at http://127.0.0.1:8000 ...
curl.exe -s --max-time 3 http://127.0.0.1:8000/ >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Origin is NOT responding on 127.0.0.1:8000.
    echo [ERROR] Start 01_start_app.bat first.
    pause
    exit /b 1
)
echo [OK] Origin is alive.

echo [INFO] Starting public tunnel via localhost.run
echo [INFO] Auto-reconnect is enabled. Keep this window open.
echo [INFO] URL will appear below (example: https://xxxx.lhr.life)
echo.

:reconnect
ssh ^
  -o StrictHostKeyChecking=no ^
  -o ExitOnForwardFailure=yes ^
  -o ServerAliveInterval=20 ^
  -o ServerAliveCountMax=3 ^
  -o TCPKeepAlive=yes ^
  -o ConnectTimeout=15 ^
  -o ConnectionAttempts=3 ^
  -R 80:127.0.0.1:8000 ^
  nokey@localhost.run

echo.
echo [WARN] Tunnel dropped. Reconnecting in 3 seconds...
timeout /t 3 /nobreak >nul
goto reconnect

endlocal
