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


def is_cancelled_order(order):
    status_value = str((order or {}).get("status") or "").strip().lower()
    return status_value in {"cancelled", "canceled"}


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
    order_type = str(order.get("order_type") or "").strip().lower()

    if order_type == "delivery":
        cooking_seconds = 15 * 60
        courier_sent_seconds = 60
        eta_minutes = int(order.get("delivery_eta_minutes", 20) or 20)
        eta_total_seconds = max(cooking_seconds + courier_sent_seconds, eta_minutes * 60)
        delivering_seconds = max(0, eta_total_seconds - cooking_seconds - courier_sent_seconds)
        delivered_seconds = 60

        total_duration = eta_total_seconds + delivered_seconds
        elapsed = int((now - created_at).total_seconds())
        if elapsed < 0:
            elapsed = 0
        if elapsed >= total_duration:
            return None

        segments = (
            ("cooking", cooking_seconds),
            ("courier_sent", courier_sent_seconds),
            ("delivering", delivering_seconds),
            ("delivered", delivered_seconds),
        )

        phase_key = segments[-1][0]
        phase_duration = segments[-1][1]
        phase_start_offset = 0
        elapsed_acc = 0
        for key, duration in segments:
            next_acc = elapsed_acc + duration
            if elapsed < next_acc:
                phase_key = key
                phase_duration = duration
                phase_start_offset = elapsed_acc
                break
            elapsed_acc = next_acc

        phase_elapsed = max(0, elapsed - phase_start_offset)
        phase_remaining = max(0, phase_duration - phase_elapsed)
        phase_start = created_at + timedelta(seconds=phase_start_offset)
        phase_end = phase_start + timedelta(seconds=phase_duration)
        cycle_end = created_at + timedelta(seconds=total_duration)
        eta_end = created_at + timedelta(seconds=eta_total_seconds)
        eta_remaining = max(0, int((eta_end - now).total_seconds()))

        return {
            "order_id": order.get("id"),
            "order_type": "delivery",
            "phase": phase_key,
            "phase_elapsed_seconds": phase_elapsed,
            "phase_remaining_seconds": phase_remaining,
            "phase_duration_seconds": phase_duration,
            "phase_progress_ratio": (phase_elapsed / phase_duration) if phase_duration else 1.0,
            "cycle_started_at": created_at.isoformat(timespec="seconds"),
            "phase_started_at": phase_start.isoformat(timespec="seconds"),
            "phase_ends_at": phase_end.isoformat(timespec="seconds"),
            "cycle_ends_at": cycle_end.isoformat(timespec="seconds"),
            "eta_total_seconds": eta_total_seconds,
            "eta_remaining_seconds": eta_remaining,
            "time_to_target_seconds": eta_remaining,
        }

    steps_index = {
        step.get("key"): int(step.get("duration_seconds", 0) or 0)
        for step in order_status_steps
    }
    cooking_seconds = max(0, steps_index.get("preparing", 15 * 60))
    delivering_seconds = max(0, steps_index.get("delivering", 60))
    delivered_seconds = max(0, steps_index.get("served", 60))

    booking = order.get("booking") or {}
    booking_dt = parse_datetime_value(booking.get("date"), booking.get("time"))
    if booking_dt:
        serve_dt = compute_serve_datetime_value(order, booking_dt, parse_datetime_value) or booking_dt
        if serve_dt < booking_dt:
            serve_dt = booking_dt

        planned_cook_start = serve_dt - timedelta(seconds=cooking_seconds + delivering_seconds)
        cook_start = max(created_at, planned_cook_start)
        delivering_start = cook_start + timedelta(seconds=cooking_seconds)
        delivered_start = delivering_start + timedelta(seconds=delivering_seconds)
        cycle_end = delivered_start + timedelta(seconds=delivered_seconds)
        target_remaining_seconds = max(0, int((delivered_start - now).total_seconds()))

        if now < cook_start:
            waiting_duration = max(1, int((cook_start - created_at).total_seconds()))
            waiting_elapsed = min(waiting_duration, max(0, int((now - created_at).total_seconds())))
            waiting_remaining = max(0, int((cook_start - now).total_seconds()))
            return {
                "order_id": order.get("id"),
                "order_type": "dine_in",
                "phase": "waiting",
                "phase_elapsed_seconds": waiting_elapsed,
                "phase_remaining_seconds": waiting_remaining,
                "phase_duration_seconds": waiting_duration,
                "phase_progress_ratio": (waiting_elapsed / waiting_duration),
                "cycle_started_at": created_at.isoformat(timespec="seconds"),
                "phase_started_at": created_at.isoformat(timespec="seconds"),
                "phase_ends_at": cook_start.isoformat(timespec="seconds"),
                "cycle_ends_at": cycle_end.isoformat(timespec="seconds"),
                "time_to_target_seconds": target_remaining_seconds,
            }

        if now < delivering_start:
            phase_key = "preparing"
            phase_start = cook_start
            phase_end = delivering_start
        elif now < delivered_start:
            phase_key = "delivering"
            phase_start = delivering_start
            phase_end = delivered_start
        elif now < cycle_end:
            phase_key = "served"
            phase_start = delivered_start
            phase_end = cycle_end
        else:
            return None

        phase_duration = max(1, int((phase_end - phase_start).total_seconds()))
        phase_elapsed = min(phase_duration, max(0, int((now - phase_start).total_seconds())))
        phase_remaining = max(0, int((phase_end - now).total_seconds()))
        return {
            "order_id": order.get("id"),
            "order_type": "dine_in",
            "phase": phase_key,
            "phase_elapsed_seconds": phase_elapsed,
            "phase_remaining_seconds": phase_remaining,
            "phase_duration_seconds": phase_duration,
            "phase_progress_ratio": (phase_elapsed / phase_duration),
            "cycle_started_at": cook_start.isoformat(timespec="seconds"),
            "phase_started_at": phase_start.isoformat(timespec="seconds"),
            "phase_ends_at": phase_end.isoformat(timespec="seconds"),
            "cycle_ends_at": cycle_end.isoformat(timespec="seconds"),
            "time_to_target_seconds": target_remaining_seconds,
        }

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
    serving_start_offset = 0
    for step in order_status_steps:
        if step.get("key") == "served":
            break
        serving_start_offset += int(step.get("duration_seconds", 0) or 0)
    serving_start = created_at + timedelta(seconds=serving_start_offset)
    time_to_target_seconds = max(0, int((serving_start - now).total_seconds()))

    return {
        "order_id": order.get("id"),
        "order_type": "dine_in",
        "phase": phase_key,
        "phase_elapsed_seconds": phase_elapsed,
        "phase_remaining_seconds": phase_remaining,
        "phase_duration_seconds": phase_duration,
        "phase_progress_ratio": (phase_elapsed / phase_duration) if phase_duration else 1.0,
        "cycle_started_at": created_at.isoformat(timespec="seconds"),
        "phase_started_at": phase_start.isoformat(timespec="seconds"),
        "phase_ends_at": phase_end.isoformat(timespec="seconds"),
        "cycle_ends_at": cycle_end.isoformat(timespec="seconds"),
        "time_to_target_seconds": time_to_target_seconds,
    }


def get_user_preparing_orders_value(user_id, load_orders_fn, build_timeline_fn):
    orders = [
        o for o in load_orders_fn()
        if o.get("user_id") == user_id and not is_cancelled_order(o)
    ]
    now = datetime.now()
    active_orders = []
    for order in orders:
        timeline = build_timeline_fn(order, now)
        if timeline is None:
            continue

        order_type = timeline.get("order_type", "dine_in")
        phase = timeline.get("phase")
        remaining_seconds = int(
            timeline.get("eta_remaining_seconds")
            if order_type == "delivery"
            else timeline.get("phase_remaining_seconds", 0)
            or 0
        )
        remaining_seconds = max(0, remaining_seconds)
        minutes, seconds = divmod(remaining_seconds, 60)

        if order_type == "delivery":
            status_titles = {
                "cooking": "Готовим заказ",
                "courier_sent": "Отправили курьера",
                "delivering": "Заказ в пути",
                "delivered": "Заказ доставлен",
            }
            status_texts = {
                "cooking": "До прибытия",
                "courier_sent": "До прибытия",
                "delivering": "До прибытия",
                "delivered": "Доставлено",
            }
        else:
            status_titles = {
                "waiting": "Ожидаем время брони",
                "preparing": "Заказ готовится",
                "delivering": "Заказ несут",
                "served": "Заказ выдан",
            }
            status_texts = {
                "waiting": "До начала готовки",
                "preparing": "Осталось",
                "delivering": "Сейчас принесём",
                "served": "Можно забирать",
            }

        enriched = dict(order)
        enriched["order_type"] = order_type
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
    orders = [
        o for o in load_orders_fn()
        if o.get("user_id") == user_id and not is_cancelled_order(o)
    ]
    active = []
    phase_priority = {
        "served": 0,
        "delivered": 0,
        "courier_sent": 1,
        "delivering": 1,
        "cooking": 2,
        "preparing": 2,
        "waiting": 3,
    }

    for order in orders:
        timeline = build_timeline_fn(order, now)
        if timeline is None:
            continue
        timeline["created_at"] = order.get("created_at", "")
        active.append(timeline)

    active.sort(
        key=lambda item: (
            int(item.get("time_to_target_seconds", 0) or 0),
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
