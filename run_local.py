#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import os
import secrets
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
VENV_DIR = BACKEND_DIR / ".venv"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Universal local launcher for the Flask backend."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=5000, help="Bind port. Default: 5000")
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Force dependency reinstall even if marker already exists.",
    )
    parser.add_argument(
        "--install-only",
        action="store_true",
        help="Prepare the environment and exit without starting the server.",
    )
    return parser.parse_args()


def get_venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv():
    venv_python = get_venv_python()
    if venv_python.exists():
        return venv_python

    print("[local] creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    return venv_python


def install_dependencies(venv_python: Path, force: bool):
    marker = VENV_DIR / ".deps_installed"
    if marker.exists() and not force:
        return

    requirements = BACKEND_DIR / "requirements.txt"
    print("[local] installing dependencies...")
    subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(requirements)], check=True)
    marker.write_text("ok\n", encoding="utf-8")


def load_env_file(env_path: Path):
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def ensure_secret_key(env_path: Path):
    if os.environ.get("FLASK_SECRET_KEY"):
        return

    secret = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii")
    os.environ["FLASK_SECRET_KEY"] = secret
    with env_path.open("a", encoding="utf-8") as fh:
        if env_path.stat().st_size > 0:
            fh.write("\n")
        fh.write(f"FLASK_SECRET_KEY={secret}\n")


def apply_local_defaults():
    local_defaults = {
        "SESSION_COOKIE_SECURE": "0",
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_PARTITIONED": "0",
        "TRUST_PROXY_HEADERS": "0",
    }
    for name, value in local_defaults.items():
        os.environ.setdefault(name, value)


def run_server(venv_python: Path, host: str, port: int):
    print(f"[local] starting waitress on http://{host}:{port}")
    subprocess.run(
        [
            str(venv_python),
            "-m",
            "waitress",
            "--host",
            host,
            "--port",
            str(port),
            "app:app",
        ],
        check=True,
        cwd=BACKEND_DIR,
    )


def main():
    args = parse_args()
    env_path = BACKEND_DIR / ".env.local"
    load_env_file(env_path)
    ensure_secret_key(env_path)
    apply_local_defaults()

    venv_python = ensure_venv()
    install_dependencies(venv_python, force=args.install_deps)

    if args.install_only:
        print("[local] environment is ready")
        return

    run_server(venv_python, args.host, args.port)


if __name__ == "__main__":
    main()
