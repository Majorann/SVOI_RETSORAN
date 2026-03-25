from datetime import datetime, timedelta

from config import ORDER_STATUS_STEPS
from services.business_logic import (
    build_order_status_timeline_value,
    current_time_value,
    parse_iso_datetime_value,
)


FINAL_EFFECTIVE_STATUSES = {"served", "cancelled"}


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def runtime_effective_status_value(order: dict, now: datetime | None = None) -> str:
    stored_status = str((order or {}).get("status") or "").strip().lower()
    if stored_status == "cancelled":
        return "cancelled"

    order_type = str((order or {}).get("order_type") or "").strip().lower()
    timeline = build_order_status_timeline_value(
        order,
        now or current_time_value(),
        ORDER_STATUS_STEPS,
        parse_iso_datetime_value,
    )

    if order_type == "delivery":
        rank_to_status = {1: "cooking", 2: "delivering", 3: "served"}
        status_to_rank = {
            "preparing": 1,
            "cooking": 1,
            "ready": 2,
            "delivering": 2,
            "served": 3,
        }
        timeline_to_rank = {
            "cooking": 1,
            "courier_sent": 2,
            "delivering": 2,
            "delivered": 3,
        }
        completed_rank = 3
    else:
        rank_to_status = {1: "preparing", 2: "cooking", 3: "ready", 4: "delivering", 5: "served"}
        status_to_rank = {
            "preparing": 1,
            "cooking": 2,
            "ready": 3,
            "delivering": 4,
            "served": 5,
        }
        timeline_to_rank = {
            "waiting": 1,
            "preparing": 2,
            "delivering": 4,
            "served": 5,
        }
        completed_rank = 5

    stored_rank = status_to_rank.get(stored_status, 0)
    derived_rank = completed_rank if timeline is None else timeline_to_rank.get(str(timeline.get("phase") or "").strip().lower(), 0)
    effective_rank = max(stored_rank, derived_rank)
    return rank_to_status.get(effective_rank, stored_status or rank_to_status[completed_rank])


def runtime_delivery_overdue_value(order: dict, now: datetime | None = None, *, effective_status: str | None = None) -> bool:
    if str((order or {}).get("order_type") or "").strip().lower() != "delivery":
        return False
    normalized_effective_status = str(effective_status or runtime_effective_status_value(order, now)).strip().lower()
    if normalized_effective_status in FINAL_EFFECTIVE_STATUSES:
        return False
    created_at = parse_iso_datetime_value((order or {}).get("created_at"))
    if created_at is None:
        return False
    eta_minutes = _safe_int((order or {}).get("delivery_eta_minutes"), 20)
    return created_at + timedelta(minutes=eta_minutes) < (now or current_time_value())


def build_persisted_status_fields_value(order: dict, now: datetime | None = None) -> dict:
    current = now or current_time_value()
    effective_status = runtime_effective_status_value(order, current)
    previous_effective_status = str((order or {}).get("effective_status") or "").strip().lower()
    previous_updated_at = str((order or {}).get("effective_status_updated_at") or "").strip()
    effective_status_updated_at = current.isoformat(timespec="seconds")
    if previous_effective_status == effective_status and previous_updated_at:
        effective_status_updated_at = previous_updated_at
    return {
        "effective_status": effective_status,
        "effective_status_updated_at": effective_status_updated_at,
        "is_delivery_overdue": runtime_delivery_overdue_value(order, current, effective_status=effective_status),
    }


def apply_persisted_status_fields_value(order: dict, now: datetime | None = None) -> dict:
    if not isinstance(order, dict):
        return order
    order.update(build_persisted_status_fields_value(order, now))
    return order


def read_effective_status_value(order: dict) -> str:
    return str((order or {}).get("effective_status") or (order or {}).get("status") or "").strip().lower()


def read_delivery_overdue_value(order: dict) -> bool:
    return bool((order or {}).get("is_delivery_overdue", False))
