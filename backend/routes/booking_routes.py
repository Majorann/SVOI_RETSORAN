from datetime import date, datetime

from flask import jsonify, redirect, render_template, request, session, url_for


def reserve_route(load_bookings, parse_datetime, overlaps_booking, tables, walls):
    selected_date = request.args.get("date")
    if selected_date is None:
        selected_date = date.today().isoformat()
    selected_time = request.args.get("time")
    if selected_time is None:
        selected_time = datetime.now().strftime("%H:%M")

    bookings = load_bookings()
    selected_dt = parse_datetime(selected_date, selected_time)
    reserved_ids = {
        item["table_id"]
        for item in bookings
        if selected_dt and overlaps_booking(item, selected_dt)
    }

    result_tables = []
    for table in tables:
        updated = dict(table)
        if updated["id"] in reserved_ids:
            updated["status"] = "reserved"
        result_tables.append(updated)

    return render_template("reserve.html", tables=result_tables, walls=walls)


def availability_route(load_bookings, parse_datetime, overlaps_booking):
    selected_date = request.args.get("date")
    selected_time = request.args.get("time")
    if not selected_date or not selected_time:
        return jsonify({"ok": False, "error": "date/time required"}), 400
    bookings = load_bookings()
    selected_dt = parse_datetime(selected_date, selected_time)
    if selected_dt is None:
        return jsonify({"ok": False, "error": "Invalid date/time"}), 400
    reserved_ids = [
        item["table_id"]
        for item in bookings
        if overlaps_booking(item, selected_dt)
    ]
    return jsonify({"ok": True, "reserved": reserved_ids})


def book_table_route(load_bookings, save_bookings, overlaps_booking, json_file_lock, bookings_path):
    data = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    table_id = data.get("table_id")
    date_str = data.get("date")
    time_str = data.get("time")
    name = (data.get("name") or "").strip()

    if not user_id:
        return jsonify({"ok": False, "error": "Login is required."}), 401
    if not all([table_id, date_str, time_str, name]):
        return jsonify({"ok": False, "error": "Fill in all fields."}), 400

    try:
        booking_dt = datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid date/time."}), 400

    if booking_dt < datetime.now():
        return jsonify({"ok": False, "error": "Time cannot be in the past."}), 400

    with json_file_lock(bookings_path):
        bookings = load_bookings()
        if any(
            b.get("table_id") == table_id and overlaps_booking(b, booking_dt)
            for b in bookings
        ):
            return jsonify({"ok": False, "error": "Table is already reserved for this time."}), 409

        bookings.append(
            {
                "table_id": table_id,
                "date": date_str,
                "time": time_str,
                "name": name,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_bookings(bookings)
    return jsonify({"ok": True})


def cancel_booking_route(load_bookings, save_bookings, json_file_lock, bookings_path):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    table_id = request.form.get("table_id", type=int)
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    if not table_id or not date_str or not time_str:
        return redirect(url_for("index"))

    with json_file_lock(bookings_path):
        bookings = load_bookings()
        remaining = []
        removed = False
        for booking in bookings:
            if (
                not removed
                and booking.get("user_id") == user_id
                and booking.get("table_id") == table_id
                and booking.get("date") == date_str
                and booking.get("time") == time_str
            ):
                removed = True
                continue
            remaining.append(booking)
        if removed:
            save_bookings(remaining)
    return redirect(url_for("index"))
