@echo off
setlocal

echo [INFO] Stopping known tunnel processes...
taskkill /F /IM ssh.exe >nul 2>nul
taskkill /F /IM cloudflared.exe >nul 2>nul
taskkill /F /IM ngrok.exe >nul 2>nul

echo [INFO] Stopping python app processes from this project...
powershell -NoProfile -Command ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*\backend\app:app*' }; foreach($p in $procs){ Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }; 'Stopped: ' + ($procs | Measure-Object | Select-Object -ExpandProperty Count)"

echo [DONE] Stop signal sent.
pause

endlocal
