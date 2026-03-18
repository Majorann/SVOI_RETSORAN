from datetime import datetime

from flask import redirect, render_template, request, session, url_for


def normalize_phone(phone_raw):
    digits = "".join(ch for ch in str(phone_raw or "") if ch.isdigit())
    if len(digits) == 10:
        digits = f"7{digits}"
    elif len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    elif len(digits) == 11 and digits.startswith("7"):
        digits = digits
    else:
        return None
    return f"+{digits}"


def login_route(
    load_users,
    hash_password,
    debug_login_failure=None,
    log_session_debug=None,
    issue_auth_token=None,
    auth_storage_key="auth_token",
    auth_query_param="auth_token",
):
    initial_error = request.args.get("error")
    if request.method == "POST":
        phone_raw = (request.form.get("phone") or "").strip()
        phone = normalize_phone(phone_raw)
        password = request.form.get("password") or ""
        if not phone:
            if debug_login_failure is not None:
                debug_login_failure("invalid_phone", phone_raw=phone_raw, normalized_phone=None)
            return render_template("login.html", error="Введите корректный номер телефона.", form_phone=phone_raw)
        users = load_users()
        user = next((u for u in users if normalize_phone(u.get("phone")) == phone), None)
        if not user or user.get("password_hash") != hash_password(password):
            if debug_login_failure is not None:
                debug_login_failure("invalid_credentials", phone_raw=phone_raw, normalized_phone=phone)
            return render_template("login.html", error="Неверный телефон или пароль.", form_phone=phone_raw)
        preserved_csrf = session.get("csrf_token")
        session.clear()
        if preserved_csrf:
            session["csrf_token"] = preserved_csrf
        session["user_id"] = user.get("id")
        session["user_name"] = user.get("name")
        session.permanent = True
        auth_token = issue_auth_token(user.get("id")) if issue_auth_token is not None else ""
        if log_session_debug is not None:
            log_session_debug(
                "login_success",
                extra={
                    "login_phone": phone,
                    "redirect_to": url_for("index"),
                    "auth_token_issued": bool(auth_token),
                },
            )
        return render_template(
            "login-success.html",
            redirect_url=url_for("index"),
            auth_token=auth_token,
            auth_storage_key=auth_storage_key,
            auth_query_param=auth_query_param,
            title_text="Вход выполнен",
        )
    return render_template("login.html", error=initial_error, form_phone="")


def register_route(
    load_users,
    save_users,
    next_user_id,
    hash_password,
    json_file_lock,
    users_path,
    issue_auth_token=None,
    auth_storage_key="auth_token",
    auth_query_param="auth_token",
):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone_raw = (request.form.get("phone") or "").strip()
        phone = normalize_phone(phone_raw)
        password = request.form.get("password") or ""
        if not name or not phone or not password:
            return render_template(
                "register.html",
                error="Заполните все поля. Телефон должен быть в формате +7.",
                form_name=name,
                form_phone=phone_raw,
            )
        with json_file_lock(users_path):
            users = load_users()
            if any(normalize_phone(u.get("phone")) == phone for u in users):
                return render_template(
                    "register.html",
                    error="Этот номер уже зарегистрирован.",
                    form_name=name,
                    form_phone=phone_raw,
                )
            new_user = {
                "id": next_user_id(users),
                "name": name,
                "phone": phone,
                "password_hash": hash_password(password),
                "balance": 0,
                "cards": [],
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            users.append(new_user)
            save_users(users)
        preserved_csrf = session.get("csrf_token")
        session.clear()
        if preserved_csrf:
            session["csrf_token"] = preserved_csrf
        session["user_id"] = new_user["id"]
        session["user_name"] = new_user["name"]
        session.permanent = True
        auth_token = issue_auth_token(new_user["id"]) if issue_auth_token is not None else ""
        return render_template(
            "login-success.html",
            redirect_url=url_for("index"),
            auth_token=auth_token,
            auth_storage_key=auth_storage_key,
            auth_query_param=auth_query_param,
            title_text="Регистрация завершена",
        )
    return render_template("register.html", error=None, form_name="", form_phone="")


def logout_route(auth_storage_key="auth_token"):
    session.clear()
    return render_template(
        "logout.html",
        redirect_url=url_for("login"),
        auth_storage_key=auth_storage_key,
    )
