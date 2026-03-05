@echo off
setlocal

set "CF_BIN="
where cloudflared >nul 2>nul
if not errorlevel 1 set "CF_BIN=cloudflared"
if not defined CF_BIN if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" set "CF_BIN=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if not defined CF_BIN if exist "C:\Program Files\cloudflared\cloudflared.exe" set "CF_BIN=C:\Program Files\cloudflared\cloudflared.exe"

if not defined CF_BIN (
    echo [ERROR] cloudflared not found.
    echo [INFO] Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
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

echo [INFO] Starting Cloudflare Quick Tunnel (fallback mode)
echo [INFO] URL format: https://xxxx.trycloudflare.com
echo [INFO] Keep this window open.
echo.

"%CF_BIN%" tunnel --no-autoupdate --protocol http2 --edge-ip-version 4 --grace-period 30s --url http://127.0.0.1:8000

echo.
echo [WARN] Tunnel stopped. Re-run this script to get a new URL.
pause

endlocal
