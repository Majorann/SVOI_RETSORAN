from flask import redirect, render_template, request, session, url_for
from services.business_logic import current_timestamp_value


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
    get_user_by_phone,
    update_user_password_hash,
    verify_and_upgrade_password,
    debug_login_failure=None,
    log_session_debug=None,
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
        user = get_user_by_phone(phone)
        password_ok, password_upgraded = verify_and_upgrade_password(user, password) if user else (False, False)
        if not password_ok:
            if debug_login_failure is not None:
                debug_login_failure("invalid_credentials", phone_raw=phone_raw, normalized_phone=phone)
            return render_template("login.html", error="Неверный телефон или пароль.", form_phone=phone_raw)
        if password_upgraded:
            update_user_password_hash(user.get("id"), user.get("password_hash"))
        preserved_csrf = session.get("csrf_token")
        session.clear()
        if preserved_csrf:
            session["csrf_token"] = preserved_csrf
        session["user_id"] = user.get("id")
        session["user_name"] = user.get("name")
        session.permanent = True
        if log_session_debug is not None:
            log_session_debug(
                "login_success",
                extra={
                    "login_phone": phone,
                    "redirect_to": url_for("index"),
                },
            )
        return render_template(
            "login-success.html",
            redirect_url=url_for("index"),
            title_text="Вход выполнен",
        )
    return render_template("login.html", error=initial_error, form_phone="")


def register_route(
    get_user_by_phone,
    create_user,
    hash_password,
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
        if get_user_by_phone(phone) is not None:
            return render_template(
                "register.html",
                error="Этот номер уже зарегистрирован.",
                form_name=name,
                form_phone=phone_raw,
            )
        new_user = create_user(
            name=name,
            phone=phone,
            password_hash=hash_password(password),
            created_at=current_timestamp_value(),
        )
        preserved_csrf = session.get("csrf_token")
        session.clear()
        if preserved_csrf:
            session["csrf_token"] = preserved_csrf
        session["user_id"] = new_user["id"]
        session["user_name"] = new_user["name"]
        session.permanent = True
        return render_template(
            "login-success.html",
            redirect_url=url_for("index"),
            title_text="Регистрация завершена",
        )
    return render_template("register.html", error=None, form_name="", form_phone="")


def logout_route():
    session.clear()
    return render_template("logout.html", redirect_url=url_for("login"))
