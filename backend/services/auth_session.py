import json
import secrets
from datetime import datetime

from flask import g, jsonify, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired


class AuthSessionService:
    def __init__(
        self,
        *,
        app,
        auth_session_cookie_name: str,
        auth_session_cookie_max_age_seconds: int,
        auth_session_serializer,
        checkout_preview_max_age_seconds: int,
        checkout_preview_serializer,
        login_debug_enabled: bool,
        login_debug_log_path,
        login_debug_lock,
        session_debug_enabled: bool,
        session_debug_log_path,
        session_debug_lock,
        load_users,
        load_bookings,
        get_user_preparing_orders,
    ):
        self.app = app
        self.auth_session_cookie_name = auth_session_cookie_name
        self.auth_session_cookie_max_age_seconds = auth_session_cookie_max_age_seconds
        self.auth_session_serializer = auth_session_serializer
        self.checkout_preview_max_age_seconds = checkout_preview_max_age_seconds
        self.checkout_preview_serializer = checkout_preview_serializer
        self.login_debug_enabled = login_debug_enabled
        self.login_debug_log_path = login_debug_log_path
        self.login_debug_lock = login_debug_lock
        self.session_debug_enabled = session_debug_enabled
        self.session_debug_log_path = session_debug_log_path
        self.session_debug_lock = session_debug_lock
        self.load_users = load_users
        self.load_bookings = load_bookings
        self.get_user_preparing_orders = get_user_preparing_orders

    def _load_users_cached(self):
        if getattr(g, "_auth_users_loaded", False):
            return getattr(g, "_auth_users", [])
        users = self.load_users()
        g._auth_users_loaded = True
        g._auth_users = users
        return users

    def _load_bookings_cached(self):
        if getattr(g, "_auth_bookings_loaded", False):
            return getattr(g, "_auth_bookings", [])
        bookings = self.load_bookings()
        g._auth_bookings_loaded = True
        g._auth_bookings = bookings
        return bookings

    def debug_login_failure(self, reason: str, phone_raw: str = "", normalized_phone: str | None = None):
        if not self.login_debug_enabled:
            return

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "reason": reason,
            "phone_raw": phone_raw,
            "normalized_phone": normalized_phone,
            "request": {
                "method": request.method,
                "path": request.path,
                "scheme": request.scheme,
                "host": request.host,
                "remote_addr": request.remote_addr,
                "forwarded_for": request.headers.get("X-Forwarded-For"),
                "real_ip": request.headers.get("X-Real-Ip"),
                "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
                "user_agent": request.headers.get("User-Agent"),
                "referer": request.headers.get("Referer"),
                "origin": request.headers.get("Origin"),
            },
        }

        try:
            self.login_debug_log_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(log_entry, ensure_ascii=False)
            with self.login_debug_lock:
                with self.login_debug_log_path.open("a", encoding="utf-8") as fh:
                    fh.write(payload + "\n")
        except OSError as exc:
            print(f"[auth-debug] failed to write login debug log ({exc})")

    def log_session_debug(self, event: str, extra: dict | None = None):
        if not self.session_debug_enabled:
            return

        session_keys = sorted(session.keys())
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "event": event,
            "request": {
                "method": request.method,
                "path": request.path,
                "query_string": request.query_string.decode("utf-8", errors="ignore"),
                "scheme": request.scheme,
                "host": request.host,
                "remote_addr": request.remote_addr,
                "forwarded_for": request.headers.get("X-Forwarded-For"),
                "real_ip": request.headers.get("X-Real-Ip"),
                "cf_connecting_ip": request.headers.get("CF-Connecting-IP"),
                "forwarded_proto": request.headers.get("X-Forwarded-Proto"),
                "user_agent": request.headers.get("User-Agent"),
                "referer": request.headers.get("Referer"),
                "origin": request.headers.get("Origin"),
            },
            "session": {
                "has_user_id": "user_id" in session,
                "user_id": session.get("user_id"),
                "user_name": session.get("user_name"),
                "has_csrf_token": "csrf_token" in session,
                "session_keys": session_keys,
                "permanent": session.permanent,
                "cookie_secure": self.app.config["SESSION_COOKIE_SECURE"],
                "cookie_samesite": self.app.config["SESSION_COOKIE_SAMESITE"],
                "cookie_partitioned": self.app.config["SESSION_COOKIE_PARTITIONED"],
            },
        }
        if extra:
            log_entry["extra"] = extra

        try:
            self.session_debug_log_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(log_entry, ensure_ascii=False)
            with self.session_debug_lock:
                with self.session_debug_log_path.open("a", encoding="utf-8") as fh:
                    fh.write(payload + "\n")
        except OSError as exc:
            print(f"[session-debug] failed to write session debug log ({exc})")

    def issue_auth_session_cookie(self, user_id: int) -> str:
        return self.auth_session_serializer.dumps({"user_id": int(user_id), "v": 1})

    def verify_auth_session_cookie(self, cookie_value: str | None):
        if not cookie_value:
            return None
        try:
            payload = self.auth_session_serializer.loads(
                cookie_value,
                max_age=self.auth_session_cookie_max_age_seconds,
            )
        except (BadSignature, SignatureExpired):
            return None
        try:
            user_id = int(payload.get("user_id"))
        except (TypeError, ValueError, AttributeError):
            return None
        if user_id <= 0:
            return None
        return {"user_id": user_id}

    def issue_checkout_preview_token(self, preview: dict) -> str:
        return self.checkout_preview_serializer.dumps({"preview": preview, "v": 1})

    def verify_checkout_preview_token(self, token: str | None):
        if not token:
            return None
        try:
            payload = self.checkout_preview_serializer.loads(
                token,
                max_age=self.checkout_preview_max_age_seconds,
            )
        except (BadSignature, SignatureExpired):
            return None
        preview = payload.get("preview")
        return preview if isinstance(preview, dict) else None

    def apply_session_user(self, user: dict):
        preserved_csrf = session.get("csrf_token")
        session.clear()
        if preserved_csrf:
            session["csrf_token"] = preserved_csrf
        session["user_id"] = user.get("id")
        session["user_name"] = user.get("name")
        session.permanent = True

    def build_auth_session_cookie_kwargs(self, max_age=None):
        cookie_kwargs = {
            "httponly": True,
            "path": "/",
            "secure": self.app.config["SESSION_COOKIE_SECURE"],
            "samesite": self.app.config["SESSION_COOKIE_SAMESITE"],
        }
        if max_age is not None:
            cookie_kwargs["max_age"] = max_age
        if self.app.config["SESSION_COOKIE_PARTITIONED"]:
            cookie_kwargs["partitioned"] = True
        return cookie_kwargs

    def set_auth_session_cookie(self, response, user_id: int):
        cookie_kwargs = self.build_auth_session_cookie_kwargs(
            max_age=self.auth_session_cookie_max_age_seconds
        )
        cookie_value = self.issue_auth_session_cookie(user_id)
        try:
            response.set_cookie(
                self.auth_session_cookie_name,
                cookie_value,
                **cookie_kwargs,
            )
        except TypeError:
            cookie_kwargs.pop("partitioned", None)
            response.set_cookie(
                self.auth_session_cookie_name,
                cookie_value,
                **cookie_kwargs,
            )

    def clear_auth_session_cookie(self, response):
        cookie_kwargs = self.build_auth_session_cookie_kwargs()
        try:
            response.set_cookie(
                self.auth_session_cookie_name,
                "",
                expires=0,
                max_age=0,
                **cookie_kwargs,
            )
        except TypeError:
            cookie_kwargs.pop("partitioned", None)
            response.set_cookie(
                self.auth_session_cookie_name,
                "",
                expires=0,
                max_age=0,
                **cookie_kwargs,
            )

    def _set_request_user(self, user: dict | None):
        g.current_user_loaded = True
        g.current_user = user
        try:
            g.current_user_id = int(user.get("id")) if user else None
        except (TypeError, ValueError, AttributeError):
            g.current_user_id = None

    def get_request_user(self, user_id=None):
        try:
            normalized_user_id = int(user_id if user_id is not None else session.get("user_id"))
        except (TypeError, ValueError):
            self._set_request_user(None)
            return None

        if normalized_user_id <= 0:
            self._set_request_user(None)
            return None

        if getattr(g, "current_user_loaded", False) and getattr(g, "current_user_id", None) == normalized_user_id:
            return getattr(g, "current_user", None)

        user = next((u for u in self._load_users_cached() if u.get("id") == normalized_user_id), None)
        self._set_request_user(user)
        return user

    def get_request_notification_data(self):
        if getattr(g, "notifications_loaded", False):
            return getattr(g, "notification_bookings", []), getattr(g, "notification_preparing_orders", [])

        user_id = session.get("user_id")
        if not user_id:
            g.notifications_loaded = True
            g.notification_bookings = []
            g.notification_preparing_orders = []
            return g.notification_bookings, g.notification_preparing_orders

        bookings = [b for b in self._load_bookings_cached() if b.get("user_id") == user_id]
        preparing_orders = self.get_user_preparing_orders(user_id)
        g.notifications_loaded = True
        g.notification_bookings = bookings
        g.notification_preparing_orders = preparing_orders
        return bookings, preparing_orders

    def register_hooks(self):
        @self.app.before_request
        def restore_auth_from_cookie():
            if request.endpoint == "static":
                return

            current_user_id = session.get("user_id")
            cookie_value = request.cookies.get(self.auth_session_cookie_name)
            if not cookie_value:
                return

            payload = self.verify_auth_session_cookie(cookie_value)
            if payload is None:
                g.clear_auth_session_cookie = True
                if self.session_debug_enabled:
                    self.log_session_debug(
                        "auth_session_cookie_invalid",
                        extra={"cookie_name": self.auth_session_cookie_name},
                    )
                return

            user_id = payload["user_id"]
            source = "auth_session_cookie"
            if current_user_id == user_id and session.get("user_name"):
                session.permanent = True
                if self.session_debug_enabled:
                    self.log_session_debug(
                        "auth_session_confirmed",
                        extra={"source": source, "user_id": user_id},
                    )
                return

            user = self.get_request_user(user_id)
            if not user:
                g.clear_auth_session_cookie = True
                if self.session_debug_enabled:
                    self.log_session_debug(
                        "auth_user_missing",
                        extra={"source": source, "user_id": user_id},
                    )
                return

            self.apply_session_user(user)
            self._set_request_user(user)
            if self.session_debug_enabled:
                self.log_session_debug(
                    "auth_session_restored",
                    extra={
                        "source": source,
                        "user_id": user_id,
                        "previous_user_id": current_user_id,
                    },
                )

        @self.app.before_request
        def hydrate_current_user():
            if request.endpoint == "static":
                return

            user_id = session.get("user_id")
            if not user_id:
                self._set_request_user(None)
                return

            self.get_request_user(user_id)

        @self.app.before_request
        def keep_user_session():
            if request.endpoint == "static":
                return

            if self.session_debug_enabled and request.endpoint in {"login", "profile", "index"}:
                self.log_session_debug("before_request")

            user_id = session.get("user_id")
            if not user_id:
                return

            session.permanent = True
            if session.get("user_name"):
                return

            user = self.get_request_user(user_id)
            if not user:
                return
            if not session.get("user_name"):
                session["user_name"] = user.get("name")
                if self.session_debug_enabled and request.endpoint in {"login", "profile", "index"}:
                    self.log_session_debug("user_name_restored")

        @self.app.before_request
        def ensure_csrf_token():
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_urlsafe(32)

        @self.app.before_request
        def validate_csrf_token():
            if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
                return
            if request.endpoint == "static":
                return

            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if token and token == session.get("csrf_token"):
                return

            if request.is_json:
                return jsonify({"ok": False, "error": "CSRF token is missing or invalid."}), 400
            return redirect(url_for("index"))

        @self.app.after_request
        def sync_auth_session_cookie_response(response):
            if request.endpoint == "static":
                return response

            session_user_id = session.get("user_id")
            try:
                normalized_user_id = int(session_user_id)
            except (TypeError, ValueError):
                normalized_user_id = None

            if normalized_user_id and normalized_user_id > 0:
                self.set_auth_session_cookie(response, normalized_user_id)
                return response

            has_auth_cookie = bool(request.cookies.get(self.auth_session_cookie_name))
            if has_auth_cookie or getattr(g, "clear_auth_session_cookie", False):
                self.clear_auth_session_cookie(response)
            return response
