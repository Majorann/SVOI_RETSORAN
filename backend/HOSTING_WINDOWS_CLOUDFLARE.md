# Hosting on Your PC (Secure Internet Access)

## Prerequisites
- Domain is delegated to Cloudflare DNS.
- `cloudflared` installed on Windows.
- Python 3.12+ installed.

## 1) Start the app locally
Run in PowerShell:

```powershell
cd "C:\Users\almaz\OneDrive\Рабочий стол\Проект\backend"
powershell -ExecutionPolicy Bypass -File .\ops\start_app.ps1 -InstallDeps
```

This starts the Flask app on `127.0.0.1:8000` (not exposed directly to internet).

## 2) Start Cloudflare Tunnel
In a second PowerShell window:

```powershell
cd "C:\Users\almaz\OneDrive\Рабочий стол\Проект\backend"
powershell -ExecutionPolicy Bypass -File .\ops\start_tunnel.ps1 -Hostname app.example.com -TunnelName svoi-restoran
```

On the first run, browser auth will open (`cloudflared tunnel login`).

## 3) Auto-start after reboot (optional)

```powershell
cd "C:\Users\almaz\OneDrive\Рабочий стол\Проект\backend"
powershell -ExecutionPolicy Bypass -File .\ops\install_startup_tasks.ps1 -Hostname app.example.com
```

## Security notes
- Use a real hostname without `_` (underscore is invalid in web hostnames).
- `FLASK_SECRET_KEY` is auto-generated in `.env.local` if missing.
- Session cookies are configured as `HttpOnly`, `SameSite=Lax`, `Secure=true` by default.
- No router port forwarding is required.
