from datetime import datetime

from flask import redirect, render_template, request, session, url_for


def login_route(load_users, hash_password):
    initial_error = request.args.get("error")
    if request.method == "POST":
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        users = load_users()
        user = next((u for u in users if u.get("phone") == phone), None)
        if not user or user.get("password_hash") != hash_password(password):
            return render_template("login.html", error="Неверный телефон или пароль.")
        session["user_id"] = user.get("id")
        session["user_name"] = user.get("name")
        session.permanent = True
        return redirect(url_for("index"))
    return render_template("login.html", error=initial_error)


def register_route(load_users, save_users, next_user_id, hash_password, json_file_lock, users_path):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        if not name or not phone or not password:
            return render_template("register.html", error="Fill in all fields.")
        with json_file_lock(users_path):
            users = load_users()
            if any(u.get("phone") == phone for u in users):
                return render_template("register.html", error="This phone is already registered.")
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
    return render_template("register.html", error=None)


def logout_route():
    session.clear()
    return redirect(url_for("login"))
