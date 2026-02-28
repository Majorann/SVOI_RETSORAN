@echo off
setlocal

where ssh >nul 2>nul
if errorlevel 1 (
  echo [ERROR] OpenSSH client not found. Install "OpenSSH Client" in Windows optional features.
  pause
  exit /b 1
)

echo [INFO] Starting public tunnel via localhost.run
echo [INFO] Keep this window open. Public URL will be printed below.
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:127.0.0.1:8000 nokey@localhost.run

endlocal
