from datetime import datetime
from typing import Any


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def update_order_status(service, *, admin_user_id: int, order_id: int, status: str, reason: str, entity_action: str, allowed_statuses: tuple[str, ...]):
    normalized = str(status or "").strip().lower()
    if normalized not in allowed_statuses:
        raise ValueError("Недопустимый статус заказа.")
    order = service.get_order_detail(order_id)
    if order is None:
        raise ValueError("Заказ не найден.")
    cancelled_at = datetime.now().isoformat(timespec="seconds") if normalized == "cancelled" else ""
    service._execute(
        "UPDATE orders SET status = %s, cancelled_at = %s WHERE id = %s",
        (normalized, cancelled_at, int(order_id)),
    )
    service._refresh_persisted_order_fields(order_ids=[int(order_id)])
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type=entity_action,
        entity_type="order",
        entity_id=order_id,
        reason=reason,
        payload={"from_status": order.get("status"), "to_status": normalized},
    )


def cancel_order(service, *, admin_user_id: int, order_id: int, reason: str, action_type: str = "order_cancelled", allowed_statuses: tuple[str, ...]):
    update_order_status(
        service,
        admin_user_id=admin_user_id,
        order_id=order_id,
        status="cancelled",
        reason=reason,
        entity_action=action_type,
        allowed_statuses=allowed_statuses,
    )


def cancel_booking(service, *, admin_user_id: int, booking_id: int, reason: str):
    booking = service.get_booking_detail(booking_id)
    if booking is None:
        raise ValueError("Бронь не найдена.")
    service._execute("DELETE FROM bookings WHERE id = %s", (int(booking_id),))
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type="booking_cancelled",
        entity_type="booking",
        entity_id=booking_id,
        reason=reason,
        payload={
            "table_id": booking.get("table_id"),
            "booking_date": str(booking.get("booking_date") or ""),
            "booking_time": str(booking.get("booking_time") or ""),
            "user_id": booking.get("user_id"),
        },
    )


def update_delivery_status(service, *, admin_user_id: int, order_id: int, status: str, reason: str, allowed_statuses: tuple[str, ...], order_statuses: tuple[str, ...]):
    normalized = str(status or "").strip().lower()
    if normalized not in allowed_statuses:
        raise ValueError("Недопустимый статус доставки.")
    update_order_status(
        service,
        admin_user_id=admin_user_id,
        order_id=order_id,
        status=normalized,
        reason=reason,
        entity_action="delivery_status_changed",
        allowed_statuses=order_statuses,
    )


def cancel_delivery(service, *, admin_user_id: int, order_id: int, reason: str, order_statuses: tuple[str, ...]):
    cancel_order(
        service,
        admin_user_id=admin_user_id,
        order_id=order_id,
        reason=reason,
        action_type="delivery_cancelled",
        allowed_statuses=order_statuses,
    )


def adjust_user_balance(service, *, admin_user_id: int, user_id: int, delta: int, reason: str):
    user = service.get_user_detail(user_id)
    if user is None:
        raise ValueError("Пользователь не найден.")
    new_balance = max(0, _safe_int(user.get("balance")) + int(delta))
    service._execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, int(user_id)))
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type="user_bonus_adjusted",
        entity_type="user",
        entity_id=user_id,
        reason=reason,
        payload={"delta": int(delta), "previous_balance": _safe_int(user.get("balance")), "new_balance": new_balance},
    )


def sync_content_from_host(service, *, admin_user_id: int, reason: str):
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("Укажите причину действия.")
    summary = service.menu_content.sync_host_content_to_storage()
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type="content_autosync",
        entity_type="content",
        entity_id="host_sync",
        reason=normalized_reason,
        payload=summary,
    )
    return summary
