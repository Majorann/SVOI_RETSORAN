from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.business_logic import APP_TIMEZONE, UTC, current_local_datetime_value, parse_iso_datetime_value

from .applier import PromotionApplicationState, apply_reward
from .evaluator import evaluate_promotion
from .parser import parse_promotion
from .ast import PromotionDslError
from .validator import PromotionValidationError, validate_promotion


@dataclass(frozen=True)
class PromotionRuntimeEntry:
    source: dict
    definition: object


def build_validation_context(menu_items: list[dict]) -> dict[str, set]:
    known_item_ids = set()
    active_item_ids = set()
    known_types = set()
    for item in menu_items or []:
        if not isinstance(item, dict):
            continue
        item_id = _safe_int(item.get("id"))
        if item_id > 0:
            known_item_ids.add(item_id)
            if bool(item.get("active", True)):
                active_item_ids.add(item_id)
        item_type = str(item.get("type") or "").strip()
        if item_type:
            known_types.add(item_type)
    return {
        "known_item_ids": known_item_ids,
        "active_item_ids": active_item_ids,
        "known_types": known_types,
    }


def parse_and_validate_promo_source(promo_item: dict, *, menu_items: list[dict]):
    definition = parse_promotion(build_dsl_text_from_promo_item(promo_item))
    return validate_promotion(definition, **build_validation_context(menu_items))


def build_dsl_text_from_promo_item(promo_item: dict) -> str:
    promotion_class = str(promo_item.get("class") or promo_item.get("type") or "akciya").strip() or "akciya"
    lines = [
        f"class={promotion_class}",
        f"name={str(promo_item.get('name') or '').strip()}",
        f"active={'true' if bool(promo_item.get('active', True)) else 'false'}",
        f"priority={_safe_int(promo_item.get('priority'), 0)}",
        f"condition={str(promo_item.get('condition') or '').strip()}",
        f"reward={str(promo_item.get('reward') or '').strip()}",
    ]
    optional_fields = (
        "dsl_version",
        "notify",
        "reward_mode",
        "limit_per_order",
        "limit_per_user_per_day",
        "start_at",
        "end_at",
    )
    for field_name in optional_fields:
        value = str(promo_item.get(field_name) or "").strip()
        if value:
            lines.append(f"{field_name}={value}")
    return "\n".join(lines)


def collect_runtime_promotions(promo_items: list[dict], *, menu_items: list[dict]) -> list[PromotionRuntimeEntry]:
    runtime_entries: list[PromotionRuntimeEntry] = []
    for promo_item in promo_items or []:
        if not isinstance(promo_item, dict) or str(promo_item.get("class") or "").strip().lower() != "akciya":
            continue
        if not str(promo_item.get("condition") or "").strip() and not str(promo_item.get("reward") or "").strip():
            continue
        try:
            definition = parse_and_validate_promo_source(promo_item, menu_items=menu_items)
        except (PromotionValidationError, PromotionDslError):
            continue
        runtime_entries.append(PromotionRuntimeEntry(source=promo_item, definition=definition))
    runtime_entries.sort(key=lambda entry: (-int(entry.source.get("priority", 0) or 0), int(entry.source.get("id", 0) or 0)))
    return runtime_entries


def apply_promotions_to_order(
    *,
    order: dict,
    promo_items: list[dict],
    menu_items: list[dict],
    prior_orders: list[dict] | None = None,
    prior_application_counts: dict[int, int] | None = None,
    user_id: int | None = None,
    at: datetime | None = None,
) -> dict:
    runtime_entries = collect_runtime_promotions(promo_items, menu_items=menu_items)
    state = PromotionApplicationState(order={"items": [dict(item) for item in (order or {}).get("items", [])]})
    applied_promotions = []

    for entry in runtime_entries:
        promo_id = _safe_int(entry.source.get("id"))
        if prior_application_counts is not None:
            prior_count = _safe_int((prior_application_counts or {}).get(promo_id), 0)
        else:
            prior_count = count_user_day_applications(
                prior_orders or [],
                user_id=user_id,
                promo_id=promo_id,
                at=at,
            )
        evaluation = evaluate_promotion(
            entry.definition,
            state.order,
            user_day_applied_count=prior_count,
            at=at,
        )
        if evaluation.applied_count <= 0:
            continue
        state = apply_reward(entry.definition, state.order, applied_count=evaluation.applied_count, state=state)
        applied_promotions.append(
            {
                "promo_id": promo_id,
                "name": entry.source.get("name") or "Акция",
                "reward_kind": entry.definition.reward.kind,
                "applied_count": evaluation.applied_count,
                "priority": entry.definition.priority,
                "notify": evaluation.notify or "",
            }
        )

    return {
        "items": state.order.get("items", []),
        "awarded_points": state.awarded_points,
        "notifications": state.notifications,
        "best_discount": state.best_discount,
        "applied_promotions": applied_promotions,
    }


def count_user_day_applications(orders: list[dict], *, user_id: int | None, promo_id: int, at: datetime | None) -> int:
    if not user_id or promo_id <= 0:
        return 0
    current = at or current_local_datetime_value()
    if current.tzinfo is not None:
        target_date = current.astimezone(APP_TIMEZONE).date()
    else:
        target_date = current.date()
    count = 0
    for order in orders or []:
        if not isinstance(order, dict) or _safe_int(order.get("user_id")) != user_id:
            continue
        created_at = parse_iso_datetime_value(order.get("created_at"))
        if created_at is None:
            continue
        created_local_date = created_at.replace(tzinfo=UTC).astimezone(APP_TIMEZONE).date()
        if created_local_date != target_date:
            continue
        for applied in order.get("promotions_applied", []) or []:
            if _safe_int((applied or {}).get("promo_id")) != promo_id:
                continue
            count += max(0, _safe_int((applied or {}).get("applied_count")))
    return count


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default
