from flask import jsonify, redirect, render_template, request, session, url_for
from services.business_logic import (
    current_local_date_time_strings_value,
    current_timestamp_value,
)


def reserve_route(list_reserved_table_ids, tables, walls):
    selected_date = request.args.get("date")
    if selected_date is None:
        selected_date, default_time = current_local_date_time_strings_value()
    else:
        default_time = None
    selected_time = request.args.get("time")
    if selected_time is None:
        selected_time = default_time or current_local_date_time_strings_value()[1]

    reserved_ids = set(list_reserved_table_ids(selected_date, selected_time))

    result_tables = []
    for table in tables:
        updated = dict(table)
        if updated["id"] in reserved_ids:
            updated["status"] = "reserved"
        result_tables.append(updated)

    return render_template("reserve.html", tables=result_tables, walls=walls)


def availability_route(list_reserved_table_ids, parse_datetime):
    selected_date = request.args.get("date")
    selected_time = request.args.get("time")
    if not selected_date or not selected_time:
        response = jsonify({"ok": False, "error": "date/time required"})
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response, 400
    selected_dt = parse_datetime(selected_date, selected_time)
    if selected_dt is None:
        response = jsonify({"ok": False, "error": "Некорректные дата или время."})
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response, 400
    reserved_ids = list_reserved_table_ids(selected_date, selected_time)
    response = jsonify({"ok": True, "reserved": reserved_ids})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def book_table_route(
    create_booking_if_available,
    parse_datetime,
):
    data = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    table_id = data.get("table_id")
    date_str = data.get("date")
    time_str = data.get("time")
    name = (data.get("name") or "").strip()

    if not user_id:
        return jsonify({"ok": False, "error": "Нужно войти в аккаунт."}), 401
    if not all([table_id, date_str, time_str, name]):
        return jsonify({"ok": False, "error": "Заполните все поля."}), 400

    booking_dt = parse_datetime(date_str, time_str)
    if booking_dt is None:
        return jsonify({"ok": False, "error": "Некорректные дата или время."}), 400

    current_date, current_time = current_local_date_time_strings_value()
    current_dt = parse_datetime(current_date, current_time)
    if current_dt is not None and booking_dt < current_dt:
        return jsonify({"ok": False, "error": "Время не может быть в прошлом."}), 400

    booking_created = create_booking_if_available(
        user_id=user_id,
        table_id=table_id,
        date_str=date_str,
        time_str=time_str,
        name=name,
        created_at=current_timestamp_value(),
    )
    if not booking_created:
        return jsonify({"ok": False, "error": "Стол уже забронирован на это время."}), 409
    return jsonify({"ok": True})


def cancel_booking_route(cancel_user_booking):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    table_id = request.form.get("table_id", type=int)
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    if not table_id or not date_str or not time_str:
        return redirect(url_for("index"))

    cancel_user_booking(user_id=user_id, table_id=table_id, date_str=date_str, time_str=time_str)
    return redirect(url_for("index"))


def cancel_booking_with_orders_route(cancel_booking_with_orders):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    table_id = request.form.get("table_id", type=int)
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    if not table_id or not date_str or not time_str:
        return redirect(url_for("index"))

    cancel_booking_with_orders(
        user_id=user_id,
        table_id=table_id,
        date_str=date_str,
        time_str=time_str,
        cancelled_at=current_timestamp_value(),
    )

    return redirect(url_for("index"))
