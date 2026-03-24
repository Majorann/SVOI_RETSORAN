from flask import jsonify, redirect, render_template, request, session, url_for
from services.business_logic import (
    current_local_date_time_strings_value,
    current_timestamp_value,
)


def reserve_route(load_bookings, parse_datetime, overlaps_booking, tables, walls):
    selected_date = request.args.get("date")
    if selected_date is None:
        selected_date, default_time = current_local_date_time_strings_value()
    else:
        default_time = None
    selected_time = request.args.get("time")
    if selected_time is None:
        selected_time = default_time or current_local_date_time_strings_value()[1]

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
        response = jsonify({"ok": False, "error": "date/time required"})
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response, 400
    bookings = load_bookings()
    selected_dt = parse_datetime(selected_date, selected_time)
    if selected_dt is None:
        response = jsonify({"ok": False, "error": "Некорректные дата или время."})
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response, 400
    reserved_ids = [
        item["table_id"]
        for item in bookings
        if overlaps_booking(item, selected_dt)
    ]
    response = jsonify({"ok": True, "reserved": reserved_ids})
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def book_table_route(
    load_bookings,
    save_bookings,
    overlaps_booking,
    parse_datetime,
    json_file_lock,
    bookings_path,
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

    with json_file_lock(bookings_path):
        bookings = load_bookings()
        if any(
            b.get("table_id") == table_id and overlaps_booking(b, booking_dt)
            for b in bookings
        ):
            return jsonify({"ok": False, "error": "Стол уже забронирован на это время."}), 409

        bookings.append(
            {
                "table_id": table_id,
                "date": date_str,
                "time": time_str,
                "name": name,
                "user_id": user_id,
                "created_at": current_timestamp_value(),
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


def cancel_booking_with_orders_route(
    load_bookings,
    save_bookings,
    json_file_lock,
    bookings_path,
    load_orders,
    save_orders,
    orders_path,
):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    table_id = request.form.get("table_id", type=int)
    date_str = request.form.get("date")
    time_str = request.form.get("time")
    if not table_id or not date_str or not time_str:
        return redirect(url_for("index"))

    booking_removed = False
    with json_file_lock(bookings_path):
        bookings = load_bookings()
        remaining_bookings = []
        for booking in bookings:
            if (
                not booking_removed
                and booking.get("user_id") == user_id
                and booking.get("table_id") == table_id
                and booking.get("date") == date_str
                and booking.get("time") == time_str
            ):
                booking_removed = True
                continue
            remaining_bookings.append(booking)
        if booking_removed:
            save_bookings(remaining_bookings)

    # Keep order state consistent with booking cancellation.
    if booking_removed:
        with json_file_lock(orders_path):
            orders = load_orders()
            changed = False
            cancelled_at = current_timestamp_value()
            for order in orders:
                if order.get("user_id") != user_id:
                    continue
                if str(order.get("order_type") or "").strip().lower() == "delivery":
                    continue
                status_value = str(order.get("status") or "").strip().lower()
                if status_value in {"cancelled", "canceled"}:
                    continue
                booking = order.get("booking") or {}
                if (
                    booking.get("table_id") == table_id
                    and booking.get("date") == date_str
                    and booking.get("time") == time_str
                ):
                    order["status"] = "cancelled"
                    order["cancelled_at"] = cancelled_at
                    changed = True
            if changed:
                save_orders(orders)

    return redirect(url_for("index"))
