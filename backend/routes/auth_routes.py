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


def login_route(load_users, hash_password):
    initial_error = request.args.get("error")
    if request.method == "POST":
        phone_raw = (request.form.get("phone") or "").strip()
        phone = normalize_phone(phone_raw)
        password = request.form.get("password") or ""
        if not phone:
            return render_template("login.html", error="Введите корректный номер телефона.", form_phone=phone_raw)
        users = load_users()
        user = next((u for u in users if normalize_phone(u.get("phone")) == phone), None)
        if not user or user.get("password_hash") != hash_password(password):
            return render_template("login.html", error="Неверный телефон или пароль.", form_phone=phone_raw)
        session["user_id"] = user.get("id")
        session["user_name"] = user.get("name")
        session.permanent = True
        return redirect(url_for("index"))
    return render_template("login.html", error=initial_error, form_phone="")


def register_route(load_users, save_users, next_user_id, hash_password, json_file_lock, users_path):
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
        session["user_id"] = new_user["id"]
        session["user_name"] = new_user["name"]
        session.permanent = True
        return redirect(url_for("index"))
    return render_template("register.html", error=None, form_name="", form_phone="")


def logout_route():
    session.clear()
    return redirect(url_for("login"))
