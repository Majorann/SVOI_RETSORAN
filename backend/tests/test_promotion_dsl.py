from datetime import datetime

import pytest

from services.promotions import (
    PromotionApplicationState,
    PromotionValidationError,
    apply_reward,
    apply_promotions_to_order,
    evaluate_condition,
    evaluate_promotion,
    parse_promotion,
    validate_promotion,
)


def build_order(*items):
    return {"items": list(items)}


def test_parse_valid_promotion_definition():
    promotion = parse_promotion(
        """
type=akciya
name=Snack bonus
condition=ID.закуски.QTY >= 2 AND ORDER.SUM >= 900
reward=POINTS(100)
notify=Начислены бонусы
reward_mode=once
limit_per_order=2
limit_per_user_per_day=5
start_at=2026-03-24T10:00:00
end_at=2026-03-30T23:59:59
"""
    )

    assert promotion.name == "Snack bonus"
    assert promotion.reward.kind == "POINTS"
    assert promotion.notify == "Начислены бонусы"
    assert promotion.reward_mode == "once"
    assert promotion.limit_per_order == 2
    assert promotion.limit_per_user_per_day == 5
    assert promotion.start_at == datetime(2026, 3, 24, 10, 0, 0)


@pytest.mark.parametrize(
    "dsl_text,error_part",
    [
        ("condition=GROUP().QTY >= 1\nreward=POINTS(10)", "GROUP\\(\\) must not be empty"),
        ("condition=ID.QTY >= 1\nreward=UNKNOWN(10)", "Unsupported reward syntax"),
        ("condition=ID.QTY >= -1\nreward=POINTS(10)", "Unknown token '-'"),
        ("condition=ID.QTY >= 1\nnotify=\nreward=POINTS(10)", "Field notify must not be empty"),
    ],
)
def test_parse_invalid_promotion_definition(dsl_text, error_part):
    with pytest.raises(ValueError, match=error_part):
        parse_promotion(dsl_text)


def test_validate_rejects_invalid_per_match_and_unknown_entities():
    promotion = parse_promotion(
        """
condition=ID(101).QTY >= 1 AND ID(205).QTY >= 1
reward=POINTS(50)
reward_mode=per_match
"""
    )

    with pytest.raises(PromotionValidationError, match="single comparison"):
        validate_promotion(
            promotion,
            known_item_ids={101, 205},
            active_item_ids={101, 205},
            known_types={"закуски"},
        )

    with pytest.raises(PromotionValidationError, match="Unknown menu item id"):
        validate_promotion(
            parse_promotion("condition=ID(999).QTY >= 1\nreward=POINTS(10)"),
            known_item_ids={101, 205},
            active_item_ids={101, 205},
            known_types={"закуски"},
        )


def test_evaluate_condition_matches_and_non_matches():
    promotion = parse_promotion("condition=ID.закуски.QTY >= 2 OR ORDER.SUM >= 1500\nreward=POINTS(25)")

    matching_order = build_order(
        {"id": 1, "type": "закуски", "price": 300, "qty": 2},
        {"id": 2, "type": "горячее", "price": 500, "qty": 1},
    )
    non_matching_order = build_order(
        {"id": 3, "type": "напитки", "price": 200, "qty": 1},
        {"id": 4, "type": "горячее", "price": 400, "qty": 1},
    )

    assert evaluate_condition(promotion.condition, matching_order) is True
    assert evaluate_condition(promotion.condition, non_matching_order) is False


def test_reward_mode_once_applies_only_once_when_condition_is_true():
    promotion = validate_promotion(
        """
condition=ID(101).QTY >= 2
reward=POINTS(50)
reward_mode=once
""",
        known_item_ids={101},
        active_item_ids={101},
        known_types={"закуски"},
    )
    order = build_order({"id": 101, "type": "закуски", "price": 200, "qty": 5})

    result = evaluate_promotion(promotion, order)

    assert result.matched is True
    assert result.base_count == 1
    assert result.applied_count == 1


def test_reward_mode_per_match_counts_floor_division():
    promotion = validate_promotion(
        """
condition=ID(101).QTY >= 2
reward=POINTS(50)
reward_mode=per_match
""",
        known_item_ids={101},
        active_item_ids={101},
        known_types={"закуски"},
    )
    order = build_order({"id": 101, "type": "закуски", "price": 200, "qty": 5})

    result = evaluate_promotion(promotion, order)

    assert result.base_count == 2
    assert result.applied_count == 2


def test_limits_reduce_applied_count():
    promotion = validate_promotion(
        """
condition=ID(101).QTY >= 2
reward=POINTS(50)
reward_mode=per_match
limit_per_order=3
limit_per_user_per_day=2
""",
        known_item_ids={101},
        active_item_ids={101},
        known_types={"закуски"},
    )
    order = build_order({"id": 101, "type": "закуски", "price": 200, "qty": 8})

    result = evaluate_promotion(promotion, order, user_day_applied_count=1)

    assert result.base_count == 4
    assert result.applied_count == 1


def test_apply_promotions_uses_application_history_counts():
    promo_items = [
        {
            "id": 501,
            "class": "akciya",
            "name": "Day limit",
            "lore": "Один раз в день",
            "priority": 10,
            "active": True,
            "condition": "ID(101).QTY >= 1",
            "reward": "POINTS(25)",
            "notify": "Начислены бонусы",
            "reward_mode": "once",
            "limit_per_order": "",
            "limit_per_user_per_day": "1",
            "start_at": "",
            "end_at": "",
            "dsl_valid": True,
        }
    ]
    menu_items = [{"id": 101, "name": "Закуска", "type": "закуски", "price": 300, "active": True}]
    order = build_order({"id": 101, "type": "закуски", "price": 300, "qty": 1})

    result = apply_promotions_to_order(
        order=order,
        promo_items=promo_items,
        menu_items=menu_items,
        prior_application_counts={501: 1},
        user_id=1,
    )

    assert result["awarded_points"] == 0
    assert result["applied_promotions"] == []


def test_notify_and_gift_application_ignore_gifts_in_follow_up_evaluation():
    promotion = validate_promotion(
        """
name=Gift promo
condition=ID.горячее.QTY >= 1 AND ID.алкоголь.QTY >= 1
reward=GIFT(777, 1)
notify=Добавлен подарок
""",
        known_item_ids={10, 20, 777},
        active_item_ids={10, 20, 777},
        known_types={"горячее", "алкоголь"},
    )
    order = build_order(
        {"id": 10, "type": "горячее", "price": 900, "qty": 1},
        {"id": 20, "type": "алкоголь", "price": 500, "qty": 1},
    )

    evaluation = evaluate_promotion(promotion, order)
    state = apply_reward(promotion, order, applied_count=evaluation.applied_count)

    assert evaluation.notify == "Добавлен подарок"
    assert state.notifications == ["Добавлен подарок"]
    assert state.order["items"][-1]["id"] == 777
    assert state.order["items"][-1]["is_gift"] is True
    assert state.order["items"][-1]["price"] == 0

    follow_up = parse_promotion("condition=ID(777).QTY >= 1\nreward=POINTS(10)")
    assert evaluate_condition(follow_up.condition, state.order) is False


def test_discount_priority_keeps_only_highest_priority_discount():
    low_priority = validate_promotion(
        "name=Low\npriority=1\ncondition=ORDER.SUM >= 1000\nreward=DISCOUNT_RUB(100)",
        known_item_ids={1},
        active_item_ids={1},
        known_types={"горячее"},
    )
    high_priority = validate_promotion(
        "name=High\npriority=5\ncondition=ORDER.SUM >= 1000\nreward=DISCOUNT_PERCENT(10)",
        known_item_ids={1},
        active_item_ids={1},
        known_types={"горячее"},
    )
    order = build_order({"id": 1, "type": "горячее", "price": 1200, "qty": 1})

    state = PromotionApplicationState(order=order)
    state = apply_reward(low_priority, order, applied_count=1, state=state)
    state = apply_reward(high_priority, order, applied_count=1, state=state)

    assert state.best_discount["promotion_name"] == "High"
    assert state.best_discount["kind"] == "DISCOUNT_PERCENT"


def test_v2_condition_supports_not_neq_and_type_selector():
    promotion = parse_promotion(
        """
dsl_version=2
condition=NOT TYPE(напитки).QTY > 0 AND ID(101).QTY != 0
reward=POINTS(10)
"""
    )
    order = build_order({"id": 101, "type": "горячее", "price": 500, "qty": 1})
    assert evaluate_condition(promotion.condition, order) is True


def test_v2_rejects_legacy_equals_and_legacy_type_metric():
    with pytest.raises(ValueError, match="Unsupported operator '='"):
        parse_promotion(
            """
dsl_version=2
condition=ID(101).QTY = 1
reward=POINTS(10)
"""
        )

    with pytest.raises(ValueError, match="ID.<type> metric is not supported in DSL v2"):
        parse_promotion(
            """
dsl_version=2
condition=ID.закуски.QTY >= 1
reward=POINTS(10)
"""
        )


def test_v2_discount_target_group_limits_discount_to_group_sum():
    promotion = validate_promotion(
        """
dsl_version=2
condition=GROUP(101,205).QTY >= 2
reward=DISCOUNT_PERCENT(50, TARGET=GROUP(101,205))
reward_mode=once
""",
        known_item_ids={101, 205, 999},
        active_item_ids={101, 205, 999},
        known_types={"закуски", "горячее"},
    )
    order = build_order(
        {"id": 101, "type": "закуски", "price": 200, "qty": 1},
        {"id": 205, "type": "горячее", "price": 100, "qty": 1},
        {"id": 999, "type": "горячее", "price": 700, "qty": 1},
    )

    evaluation = evaluate_promotion(promotion, order)
    state = apply_reward(promotion, order, applied_count=evaluation.applied_count)

    assert state.best_discount is not None
    assert state.best_discount["amount"] == 150
    assert state.best_discount["target_kind"] == "GROUP"


def test_v2_cheapest_free_from_group():
    promotion = validate_promotion(
        """
dsl_version=2
condition=GROUP(10,11,12).QTY >= 2
reward=CHEAPEST_FREE_FROM_GROUP(10,11,12)
reward_mode=once
""",
        known_item_ids={10, 11, 12, 13},
        active_item_ids={10, 11, 12, 13},
        known_types={"закуски"},
    )
    order = build_order(
        {"id": 10, "type": "закуски", "price": 350, "qty": 1},
        {"id": 11, "type": "закуски", "price": 280, "qty": 2},
        {"id": 12, "type": "закуски", "price": 280, "qty": 1},
        {"id": 13, "type": "закуски", "price": 500, "qty": 1},
    )

    evaluation = evaluate_promotion(promotion, order)
    state = apply_reward(promotion, order, applied_count=evaluation.applied_count)

    assert state.best_discount is not None
    assert state.best_discount["kind"] == "CHEAPEST_FREE_FROM_GROUP"
    assert state.best_discount["amount"] == 280


def test_v2_unique_qty_metric_and_order_subtotal_alias():
    promotion = parse_promotion(
        """
dsl_version=2
condition=GROUP(1,2,3).UNIQUE_QTY >= 2 AND ORDER.SUM == 900
reward=POINTS(5)
"""
    )
    order = build_order(
        {"id": 1, "type": "закуски", "price": 200, "qty": 2},
        {"id": 2, "type": "закуски", "price": 500, "qty": 1},
    )
    assert evaluate_condition(promotion.condition, order) is True


def test_v1_backward_compatibility_is_preserved():
    promotion = parse_promotion(
        """
condition=ID.закуски.QTY >= 2 AND ORDER.SUM >= 900
reward=DISCOUNT_RUB(100)
"""
    )
    order = build_order(
        {"id": 1, "type": "закуски", "price": 300, "qty": 2},
        {"id": 2, "type": "горячее", "price": 500, "qty": 1},
    )
    assert evaluate_condition(promotion.condition, order) is True


def test_v1_rejects_not_operator():
    with pytest.raises(ValueError, match="NOT operator is supported only in DSL v2"):
        parse_promotion(
            """
condition=NOT ID.QTY >= 1
reward=POINTS(10)
"""
        )
