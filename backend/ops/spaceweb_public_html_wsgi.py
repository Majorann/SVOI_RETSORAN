# -*- coding: utf-8 -*-
import os
import sys

PUBLIC_HTML_DIR = os.path.dirname(os.path.abspath(__file__))
HOME_DIR = os.path.dirname(PUBLIC_HTML_DIR)
BACKEND_DIR = os.path.join(HOME_DIR, "backend")

for candidate in (BACKEND_DIR, HOME_DIR):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

VENV_SITE_PACKAGES = os.path.join(
    HOME_DIR,
    ".flaskvenv",
    "lib",
    "python3.11",
    "site-packages",
)
if VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

SYSTEM_SITE_PACKAGES = "/usr/lib/python3.11/site-packages"
if SYSTEM_SITE_PACKAGES in sys.path:
    sys.path.remove(SYSTEM_SITE_PACKAGES)

os.environ["TRUST_PROXY_HEADERS"] = "1"
os.environ["SESSION_COOKIE_SECURE"] = "0"
os.environ["SESSION_COOKIE_SAMESITE"] = "Lax"
os.environ["SESSION_COOKIE_PARTITIONED"] = "0"

os.environ["DB_KEEPALIVE_ENABLED"] = "0"
os.environ["DB_KEEPALIVE_INTERVAL_SECONDS"] = "200"
os.environ["POSTGRES_STARTUP_RETRIES"] = "2"
os.environ["POSTGRES_STARTUP_RETRY_DELAY_SECONDS"] = "4"
os.environ["DB_OPERATION_RETRIES"] = "4"
os.environ["DB_RETRY_DELAY_SECONDS"] = "2"

os.environ["MENU_CACHE_ENABLED"] = "true"
os.environ["MENU_CACHE_TTL_SECONDS"] = "600"
os.environ["MENU_CACHE_KEY"] = "menu:items:v1"

os.environ["PUBLIC_BASE_URL"] = "http://koptakcby2.temp.swtest.ru/"
os.environ["CONTENT_AUTOSYNC_ON_STARTUP"] = "0"
os.environ["PG_CONNECT_TIMEOUT_SECONDS"] = "5"
os.environ["APP_TIMEZONE"] = "Europe/Kaliningrad"
os.environ["FLASK_SECRET_KEY"] = "DsNSwRq-AChh3pLlVN90rmeLeICF6TUym3KVckv9vH76dD58TlH_j6Dsj7HFqqKWgoJlR_UWE7IMpBvYWSIedw"

os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)

from app import app as _flask_application


def application(environ, start_response):
    path_info = environ.get("PATH_INFO", "") or ""
    script_name = environ.get("SCRIPT_NAME", "") or ""

    if path_info.startswith("/wsgi.py"):
        path_info = path_info[len("/wsgi.py"):] or "/"

    if script_name == "/wsgi.py":
        script_name = ""

    environ["PATH_INFO"] = path_info
    environ["SCRIPT_NAME"] = script_name
    return _flask_application.wsgi_app(environ, start_response)
