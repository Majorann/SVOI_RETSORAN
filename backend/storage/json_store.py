from datetime import timedelta
import json
import os
from services.business_logic import current_time_value
from services.order_status import apply_persisted_status_fields_value


def _read_json_list(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return data


def _write_json_list(path, items):
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, path)


def load_bookings_raw(bookings_path):
    return _read_json_list(bookings_path)


def save_bookings(bookings_path, bookings):
    _write_json_list(bookings_path, bookings)


def load_bookings(bookings_path, parse_datetime_fn, booking_duration_minutes):
    bookings = _read_json_list(bookings_path)
    now = current_time_value()
    active = []
    for booking in bookings:
        booking_dt = parse_datetime_fn(booking.get("date"), booking.get("time"))
        if booking_dt is None:
            continue
        if booking_dt + timedelta(minutes=booking_duration_minutes) <= now:
            continue
        active.append(booking)
    if len(active) != len(bookings):
        save_bookings(bookings_path, active)
    return active


def load_orders(orders_path):
    orders = _read_json_list(orders_path)
    changed = False
    now = current_time_value()
    for order in orders:
        if not isinstance(order, dict):
            continue
        if "effective_status" in order and "effective_status_updated_at" in order and "is_delivery_overdue" in order:
            continue
        apply_persisted_status_fields_value(order, now)
        changed = True
    if changed:
        save_orders(orders_path, orders)
    return orders


def save_orders(orders_path, orders):
    now = current_time_value()
    normalized_orders = []
    for order in orders:
        if not isinstance(order, dict):
            continue
        normalized_orders.append(apply_persisted_status_fields_value(dict(order), now))
    _write_json_list(orders_path, normalized_orders)


def load_users(users_path):
    return _read_json_list(users_path)


def save_users(users_path, users):
    _write_json_list(users_path, users)


def next_user_id(users):
    if not users:
        return 1
    return max(u.get("id", 0) for u in users) + 1


def next_order_id(orders):
    if not orders:
        return 1
    return max(o.get("id", 0) for o in orders) + 1
