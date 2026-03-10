from datetime import datetime, timedelta
import json


def parse_datetime_value(date_str, time_str):
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str}")
    except (TypeError, ValueError):
        return None


def overlaps_booking_window(booking, selected_dt, parse_datetime_fn, booking_duration_minutes):
    booking_dt = parse_datetime_fn(booking.get("date"), booking.get("time"))
    if booking_dt is None:
        return False
    end_dt = booking_dt + timedelta(minutes=booking_duration_minutes)
    return booking_dt <= selected_dt < end_dt


def latest_user_booking_entry(user_id, load_bookings_fn):
    bookings = [b for b in load_bookings_fn() if b.get("user_id") == user_id]
    if not bookings:
        return None
    bookings.sort(key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")), reverse=True)
    return bookings[0]


def parse_iso_datetime_value(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def compute_serve_datetime_value(order, booking_dt, parse_datetime_fn):
    serving = order.get("serving") or {}
    mode = serving.get("mode")
    if mode == "booking_start":
        return booking_dt
    if mode == "plus_15":
        return booking_dt + timedelta(minutes=15)
    if mode == "plus_30":
        return booking_dt + timedelta(minutes=30)
    if mode == "plus_45":
        return booking_dt + timedelta(minutes=45)
    if mode == "plus_60":
        return booking_dt + timedelta(minutes=60)
    if mode == "custom":
        custom_time = serving.get("time")
        if not custom_time:
            return None
        return parse_datetime_fn(booking_dt.date().isoformat(), custom_time)
    return None


def order_cooking_window_value(order, parse_datetime_fn, parse_iso_datetime_fn, compute_serve_datetime_fn, booking_duration_minutes):
    booking = order.get("booking") or {}
    booking_dt = parse_datetime_fn(booking.get("date"), booking.get("time"))
    if booking_dt is None:
        return None
    booking_end = booking_dt + timedelta(minutes=booking_duration_minutes)

    order_time = parse_iso_datetime_fn(order.get("created_at"))
    if order_time is None:
        order_time = booking_dt

    serve_dt = compute_serve_datetime_fn(order, booking_dt)
    if serve_dt is None:
        serve_dt = booking_dt

    if serve_dt < booking_dt:
        serve_dt = booking_dt
    if serve_dt > booking_end:
        serve_dt = booking_end

    cook_start = max(order_time, serve_dt - timedelta(minutes=20))
    ready_time = cook_start + timedelta(minutes=20)
    return cook_start, ready_time, booking_end


def build_order_status_timeline_value(order, now, order_status_steps, parse_iso_datetime_fn):
    created_at = parse_iso_datetime_fn(order.get("created_at"))
    if created_at is None:
        return None

    total_duration = sum(step["duration_seconds"] for step in order_status_steps)
    elapsed = int((now - created_at).total_seconds())
    if elapsed < 0:
        elapsed = 0
    if elapsed >= total_duration:
        return None

    phase_key = order_status_steps[-1]["key"]
    phase_duration = order_status_steps[-1]["duration_seconds"]
    phase_start_offset = 0
    elapsed_acc = 0
    for step in order_status_steps:
        next_acc = elapsed_acc + step["duration_seconds"]
        if elapsed < next_acc:
            phase_key = step["key"]
            phase_duration = step["duration_seconds"]
            phase_start_offset = elapsed_acc
            break
        elapsed_acc = next_acc

    phase_elapsed = elapsed - phase_start_offset
    phase_remaining = max(0, phase_duration - phase_elapsed)
    cycle_end = created_at + timedelta(seconds=total_duration)
    phase_start = created_at + timedelta(seconds=phase_start_offset)
    phase_end = phase_start + timedelta(seconds=phase_duration)

    return {
        "order_id": order.get("id"),
        "phase": phase_key,
        "phase_elapsed_seconds": phase_elapsed,
        "phase_remaining_seconds": phase_remaining,
        "phase_duration_seconds": phase_duration,
        "phase_progress_ratio": (phase_elapsed / phase_duration) if phase_duration else 1.0,
        "cycle_started_at": created_at.isoformat(timespec="seconds"),
        "phase_started_at": phase_start.isoformat(timespec="seconds"),
        "phase_ends_at": phase_end.isoformat(timespec="seconds"),
        "cycle_ends_at": cycle_end.isoformat(timespec="seconds"),
    }


def get_user_preparing_orders_value(user_id, load_orders_fn, build_timeline_fn):
    orders = [o for o in load_orders_fn() if o.get("user_id") == user_id]
    now = datetime.now()
    active_orders = []
    status_titles = {
        "preparing": "Заказ готовится",
        "delivering": "Заказ несут",
        "served": "Заказ выдан",
    }
    status_texts = {
        "preparing": "Осталось",
        "delivering": "Сейчас принесём",
        "served": "Можно забирать",
    }

    for order in orders:
        timeline = build_timeline_fn(order, now)
        if timeline is None:
            continue

        phase = timeline.get("phase")
        remaining_seconds = int(timeline.get("phase_remaining_seconds", 0) or 0)
        remaining_seconds = max(0, remaining_seconds)
        minutes, seconds = divmod(remaining_seconds, 60)

        enriched = dict(order)
        enriched["status_phase"] = phase
        enriched["status_title"] = status_titles.get(phase, "Статус заказа")
        enriched["status_text"] = status_texts.get(phase, "Осталось")
        enriched["status_remaining_seconds"] = remaining_seconds
        enriched["status_remaining_mmss"] = f"{minutes:02d}:{seconds:02d}"
        active_orders.append(enriched)

    active_orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return active_orders


def list_active_order_statuses_value(user_id, load_orders_fn, build_timeline_fn):
    now = datetime.now()
    orders = [o for o in load_orders_fn() if o.get("user_id") == user_id]
    active = []
    phase_priority = {"served": 0, "delivering": 1, "preparing": 2}

    for order in orders:
        timeline = build_timeline_fn(order, now)
        if timeline is None:
            continue
        timeline["created_at"] = order.get("created_at", "")
        active.append(timeline)

    active.sort(
        key=lambda item: (
            phase_priority.get(item.get("phase"), 99),
            int(item.get("phase_remaining_seconds", 0) or 0),
            item.get("created_at", ""),
            int(item.get("order_id", 0) or 0),
        )
    )
    return active


def latest_active_order_status_value(user_id, list_active_order_statuses_fn):
    active = list_active_order_statuses_fn(user_id)
    return active[0] if active else None


def latest_user_booking_status_value(user_id, load_bookings_raw_fn, parse_datetime_fn, booking_duration_minutes):
    bookings = [b for b in load_bookings_raw_fn() if b.get("user_id") == user_id]
    if not bookings:
        return {"state": "no_booking", "booking": None}
    bookings.sort(
        key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("created_at", "")),
        reverse=True,
    )
    booking = bookings[0]
    booking_dt = parse_datetime_fn(booking.get("date"), booking.get("time"))
    if booking_dt is None:
        return {"state": "no_booking", "booking": None}
    if booking_dt + timedelta(minutes=booking_duration_minutes) <= datetime.now():
        return {"state": "expired_booking", "booking": booking}
    return {"state": "active", "booking": booking}


def resolve_order_items_value(raw_items_json, load_menu_items_fn):
    try:
        raw_items = json.loads(raw_items_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw_items, list):
        return []

    normalized = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id"))
            qty = int(item.get("qty"))
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        normalized[item_id] = normalized.get(item_id, 0) + qty

    if not normalized:
        return []

    menu_index = {m["id"]: m for m in load_menu_items_fn()}
    items = []
    for item_id, qty in normalized.items():
        menu_item = menu_index.get(item_id)
        if not menu_item:
            continue
        items.append(
            {
                "id": menu_item["id"],
                "name": menu_item["name"],
                "price": menu_item["price"],
                "qty": qty,
                "photo": menu_item.get("photo"),
            }
        )
    return items


def parse_serving_option_value(serve_mode, serve_custom_time, booking, parse_datetime_fn, booking_duration_minutes):
    labels = {
        "booking_start": "К началу брони",
        "plus_15": "Через 15 минут",
        "plus_30": "Через 30 минут",
        "plus_45": "Через 45 минут",
        "plus_60": "Через 60 минут",
    }
    if serve_mode in labels:
        return {"mode": serve_mode, "label": labels[serve_mode]}
    if serve_mode == "custom":
        if not serve_custom_time:
            return None
        booking_start = parse_datetime_fn(booking.get("date"), booking.get("time"))
        custom_time = parse_datetime_fn(booking.get("date"), serve_custom_time)
        if booking_start is None or custom_time is None:
            return None
        booking_end = booking_start + timedelta(minutes=booking_duration_minutes)
        if not (booking_start <= custom_time < booking_end):
            return None
        return {"mode": "custom", "label": f"В своё время ({serve_custom_time})", "time": serve_custom_time}
    return None
