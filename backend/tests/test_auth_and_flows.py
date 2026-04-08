import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from conftest import write_json


def get_csrf_token(client):
    client.get("/login")
    with client.session_transaction() as session_state:
        return session_state["csrf_token"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_user(app_module, *, password="1234", legacy_hash=False, balance=0, cards=None):
    password_hash = (
        hashlib.sha256(password.encode("utf-8")).hexdigest()
        if legacy_hash
        else app_module.hash_password(password)
    )
    return {
        "id": 1,
        "name": "Тестовый пользователь",
        "phone": "+79991234567",
        "password_hash": password_hash,
        "balance": balance,
        "cards": cards or [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def test_normalize_phone_converts_common_russian_formats_to_plus7(app_module):
    from routes.auth_routes import normalize_phone

    assert normalize_phone("+7 999 123-45-67") == "+79991234567"
    assert normalize_phone("8 (999) 123-45-67") == "+79991234567"
    assert normalize_phone("9991234567") == "+79991234567"


def test_normalize_phone_rejects_incomplete_or_non_russian_numbers(app_module):
    from routes.auth_routes import normalize_phone

    assert normalize_phone("+7 999 123-45") is None
    assert normalize_phone("+1 999 123 45 67") is None
    assert normalize_phone("abcdef") is None


def test_register_stores_modern_password_hash(app_module, client):
    csrf_token = get_csrf_token(client)

    response = client.post(
        "/register",
        data={
            "csrf_token": csrf_token,
            "name": "Новый пользователь",
            "phone": "+79991234567",
            "password": "1234",
        },
    )

    assert response.status_code == 200
    users = read_json(app_module.USERS_PATH)
    assert len(users) == 1
    stored_hash = users[0]["password_hash"]
    assert stored_hash.startswith("pbkdf2:sha256:")
    assert app_module.verify_password("1234", stored_hash) == (True, False)


def test_login_upgrades_legacy_sha256_hash(app_module, client):
    legacy_user = build_user(app_module, legacy_hash=True)
    original_hash = legacy_user["password_hash"]
    write_json(app_module.USERS_PATH, [legacy_user])

    csrf_token = get_csrf_token(client)
    response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "phone": legacy_user["phone"],
            "password": "1234",
        },
    )

    assert response.status_code == 200
    users = read_json(app_module.USERS_PATH)
    assert users[0]["password_hash"] != original_hash
    assert users[0]["password_hash"].startswith("pbkdf2:sha256:")
    with client.session_transaction() as session_state:
        assert session_state["user_id"] == 1


def test_auth_session_cookie_restores_session_for_first_load(app_module, client):
    user = build_user(app_module, balance=345)
    write_json(app_module.USERS_PATH, [user])

    auth_cookie = app_module.issue_auth_session_cookie(user["id"])
    client.set_cookie(app_module.AUTH_SESSION_COOKIE_NAME, auth_cookie)

    response = client.get("/api/index-summary")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["authenticated"] is True
    assert payload["points_balance"] == 345
    with client.session_transaction() as session_state:
        assert session_state["user_id"] == user["id"]

    profile_response = client.get("/profile")
    assert profile_response.status_code == 200


def test_public_pages_do_not_issue_session_cookie_without_csrf_need(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("Set-Cookie") is None
    assert response.headers.get("Vary") is None

    delivery_response = client.get("/delivery")
    assert delivery_response.status_code == 200
    assert delivery_response.headers.get("Set-Cookie") is None
    assert delivery_response.headers.get("Vary") is None


def test_popular_items_fill_up_to_limit_with_random_fallback(app_module):
    from routes.main_routes import _pick_popular_items_from_analytics

    items = [
        {"id": item_id, "name": f"Блюдо {item_id}", "popularity": item_id}
        for item_id in range(1, 13)
    ]

    def get_popular_analytics(_filters):
        return {
            "top_qty_items": [
                {"id": 2},
                {"id": 5},
                {"id": 9},
            ]
        }

    selected = _pick_popular_items_from_analytics(get_popular_analytics, items, 10)

    assert len(selected) == 10
    assert [item["id"] for item in selected[:3]] == [2, 5, 9]
    assert len({item["id"] for item in selected}) == 10


def test_menu_popularity_uses_analytics_ranking_for_all_items(app_module):
    from routes.menu_routes import _attach_menu_popularity

    items = [
        {"id": 1, "name": "Блюдо 1", "popularity": 0},
        {"id": 2, "name": "Блюдо 2", "popularity": 0},
        {"id": 3, "name": "Блюдо 3", "popularity": 0},
    ]

    def get_popular_analytics(_filters):
        return {
            "full_items": [
                {"id": 3, "qty_total": 17},
                {"id": 1, "qty_total": 4},
                {"id": 2, "qty_total": 9},
            ]
        }

    enriched = _attach_menu_popularity(items, get_popular_analytics)

    assert [item["popularity_sort"] for item in enriched] == [4, 9, 17]


def test_menu_page_uses_default_alpha_sort(client):
    response = client.get("/menu")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="sortValue">От А до Я<' in html
    assert 'class="sort-option is-active" type="button" data-sort="alpha"' in html
    assert 'data-sort="popular"' in html


def test_static_assets_do_not_issue_session_cookie(client):
    response = client.get("/static/css/style.css")

    assert response.status_code == 200
    assert response.headers.get("Set-Cookie") is None
    assert response.headers.get("Vary") is None


def test_static_assets_do_not_refresh_logged_in_session_cookie(app_module, client):
    user = build_user(app_module, legacy_hash=True)
    write_json(app_module.USERS_PATH, [user])

    csrf_token = get_csrf_token(client)
    login_response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "phone": user["phone"],
            "password": "1234",
        },
    )
    assert login_response.status_code == 200

    response = client.get("/static/css/style.css")

    assert response.status_code == 200
    assert response.headers.get("Set-Cookie") is None


def test_login_rate_limit_blocks_after_repeated_failures(app_module, client):
    user = build_user(app_module)
    write_json(app_module.USERS_PATH, [user])
    csrf_token = get_csrf_token(client)

    for _ in range(5):
        response = client.post(
            "/login",
            data={
                "csrf_token": csrf_token,
                "phone": user["phone"],
                "password": "wrong-password",
            },
        )
        assert response.status_code == 200

    blocked = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "phone": user["phone"],
            "password": "wrong-password",
        },
    )

    assert blocked.status_code == 200
    assert "Слишком много попыток входа" in blocked.get_data(as_text=True)


def test_profile_card_binding_accepts_only_prepared_last4(app_module, client):
    user = build_user(app_module)
    write_json(app_module.USERS_PATH, [user])
    csrf_token = get_csrf_token(client)
    client.post(
        "/login",
        data={"csrf_token": csrf_token, "phone": user["phone"], "password": "1234"},
    )

    response = client.post(
        "/cards/add",
        data={
            "csrf_token": csrf_token,
            "card_last4": "4242",
            "expiry": "12/30",
            "holder": "TEST USER",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    users = read_json(app_module.USERS_PATH)
    assert users[0]["cards"] == [
        {
            "brand": "MIR",
            "last4": "4242",
            "active": True,
            "holder": "TEST USER",
            "expiry": "12/30",
            "created_at": users[0]["cards"][0]["created_at"],
        }
    ]


def test_index_drops_unsafe_promo_links(app_module, client, monkeypatch):
    monkeypatch.setattr(app_module, "load_promo_items", lambda: [{"id": 1, "class": "reklama", "text": "Promo", "link": "javascript:alert(1)"}])
    monkeypatch.setattr(
        app_module,
        "promo_items_to_news_cards",
        lambda _items: [{"title": "Реклама", "text": "Promo", "accent": "Реклама", "photo": "", "link": "javascript:alert(1)"}],
    )

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "javascript:alert(1)" not in html
    assert 'data-link="' not in html


def test_booking_payment_and_delivery_flows(app_module, client):
    user = build_user(
        app_module,
        balance=120,
        cards=[
            {
                "id": 1,
                "brand": "MIR",
                "last4": "4242",
                "expiry": "12/30",
                "holder": "TEST USER",
                "active": True,
            }
        ],
    )
    write_json(app_module.USERS_PATH, [user])

    csrf_token = get_csrf_token(client)
    login_response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "phone": user["phone"],
            "password": "1234",
        },
    )
    assert login_response.status_code == 200

    menu_item = app_module.load_menu_items()[0]
    booking_dt = datetime.now() + timedelta(days=1)
    booking_response = client.post(
        "/book",
        json={
            "table_id": 1,
            "date": booking_dt.strftime("%Y-%m-%d"),
            "time": booking_dt.strftime("%H:%M"),
            "name": user["name"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert booking_response.status_code == 200
    assert booking_response.get_json()["ok"] is True

    checkout_response = client.get("/checkout")
    assert checkout_response.status_code == 200
    checkout_html = checkout_response.get_data(as_text=True)
    assert 'id="menuCatalogJson"' not in checkout_html

    items_json = json.dumps([{"id": menu_item["id"], "qty": 2}], ensure_ascii=False)
    payment_response = client.post(
        "/payment",
        data={
            "csrf_token": csrf_token,
            "items_json": items_json,
            "comment": "Без лука",
            "serve_mode": "booking_start",
            "use_points": "1",
        },
    )
    assert payment_response.status_code == 200
    payment_html = payment_response.get_data(as_text=True)
    preview_token_marker = 'name="preview_token" value="'
    assert preview_token_marker in payment_html
    payment_preview_token = payment_html.split(preview_token_marker, 1)[1].split('"', 1)[0]
    assert payment_preview_token

    payment_confirm_response = client.post(
        "/payment/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": payment_preview_token,
        },
        follow_redirects=False,
    )
    assert payment_confirm_response.status_code == 302
    assert "/orders/1" in payment_confirm_response.headers["Location"]

    duplicate_payment = client.post(
        "/payment/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": payment_preview_token,
        },
        follow_redirects=False,
    )
    assert duplicate_payment.status_code == 302
    assert len(read_json(app_module.ORDERS_PATH)) == 1

    orders = read_json(app_module.ORDERS_PATH)
    assert len(orders) == 1
    assert orders[0]["payable_total"] == max(0, menu_item["price"] * 2 - 120)
    assert orders[0]["bonus_earned"] == int(orders[0]["payable_total"] * 0.05)

    users_after_payment = read_json(app_module.USERS_PATH)
    assert users_after_payment[0]["balance"] >= 0

    delivery_response = client.post(
        "/delivery/payment",
        data={
            "csrf_token": csrf_token,
            "items_json": json.dumps([{"id": menu_item["id"], "qty": 1}], ensure_ascii=False),
            "delivery_name": user["name"],
            "delivery_phone": user["phone"],
            "delivery_street": "Советский проспект",
            "delivery_house": "10",
            "delivery_apartment": "5",
            "delivery_comment": "Позвонить за 5 минут",
        },
        follow_redirects=False,
    )
    assert delivery_response.status_code == 302
    delivery_location = delivery_response.headers["Location"]
    delivery_preview_token = parse_qs(urlparse(delivery_location).query)["preview_token"][0]

    delivery_confirm_response = client.post(
        "/delivery/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": delivery_preview_token,
        },
        follow_redirects=False,
    )
    assert delivery_confirm_response.status_code == 302
    assert "/orders/2" in delivery_confirm_response.headers["Location"]

    orders_after_delivery = read_json(app_module.ORDERS_PATH)
    assert len(orders_after_delivery) == 2
    assert orders_after_delivery[1]["order_type"] == "delivery"
    assert orders_after_delivery[1]["service_fee"] == 42
    assert orders_after_delivery[1]["payable_total"] == menu_item["price"] + 42
    assert orders_after_delivery[1]["bonus_earned"] == int((menu_item["price"] + 42) * 0.05)

    duplicate_delivery = client.post(
        "/delivery/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": delivery_preview_token,
        },
        follow_redirects=False,
    )
    assert duplicate_delivery.status_code == 302
    assert len(read_json(app_module.ORDERS_PATH)) == 2


def test_order_totals_helper_reuses_same_rules_for_points_and_delivery(app_module):
    from services.order_totals import calculate_order_totals, summarize_saved_order_totals

    items = [
        {"id": 1, "price": 100, "qty": 2},
        {"id": 2, "price": 50, "qty": 1},
    ]

    totals = calculate_order_totals(items, service_fee=42, points_balance=180, use_points=True)
    assert totals == {
        "items_total": 250,
        "service_fee": 42,
        "gross_total": 292,
        "points_applied": 180,
        "payable_total": 112,
        "bonus_earned": 5,
    }

    restored = summarize_saved_order_totals(
        {
            "order_type": "delivery",
            "items": items,
            "items_total": 250,
            "payable_total": 292,
            "points_applied": 0,
            "bonus_earned": 0,
        },
        recompute_zero_bonus=True,
    )
    assert restored["service_fee"] == 42
    assert restored["bonus_earned"] == 14

    fully_paid = summarize_saved_order_totals(
        {
            "items_total": 250,
            "payable_total": 0,
            "points_applied": 250,
            "bonus_earned": 0,
        },
        recompute_zero_bonus=True,
    )
    assert fully_paid["bonus_earned"] == 0


def test_booking_time_checks_use_app_timezone_helpers(app_module, monkeypatch, tmp_path):
    from services import business_logic
    from storage import json_store

    bookings_path = tmp_path / "bookings.json"
    booking = {
        "user_id": 1,
        "table_id": 7,
        "date": "2026-03-19",
        "time": "12:00",
        "name": "Тест",
        "created_at": "2026-03-19T08:00:00",
    }
    write_json(bookings_path, [booking])

    active_now = business_logic.parse_datetime_value("2026-03-19", "13:59")
    monkeypatch.setattr(business_logic, "current_time_value", lambda: active_now)
    monkeypatch.setattr(json_store, "current_time_value", lambda: active_now)

    active_bookings = json_store.load_bookings(
        bookings_path,
        business_logic.parse_datetime_value,
        120,
    )
    assert active_bookings == [booking]

    active_status = business_logic.latest_user_booking_status_value(
        1,
        lambda: [booking],
        business_logic.parse_datetime_value,
        120,
    )
    assert active_status["state"] == "active"

    expired_now = business_logic.parse_datetime_value("2026-03-19", "14:00")
    monkeypatch.setattr(business_logic, "current_time_value", lambda: expired_now)
    monkeypatch.setattr(json_store, "current_time_value", lambda: expired_now)

    expired_status = business_logic.latest_user_booking_status_value(
        1,
        lambda: [booking],
        business_logic.parse_datetime_value,
        120,
    )
    assert expired_status["state"] == "expired_booking"

    pruned_bookings = json_store.load_bookings(
        bookings_path,
        business_logic.parse_datetime_value,
        120,
    )
    assert pruned_bookings == []


def test_payment_flow_applies_dsl_promotion_and_stores_application(app_module, client, monkeypatch):
    user = build_user(
        app_module,
        balance=0,
        cards=[
            {
                "id": 1,
                "brand": "MIR",
                "last4": "4242",
                "expiry": "12/30",
                "holder": "TEST USER",
                "active": True,
            }
        ],
    )
    write_json(app_module.USERS_PATH, [user])

    menu_items = [
        {
            "id": 101,
            "name": "Закуска",
            "type": "закуски",
            "price": 300,
            "photo": "menu_items/test/photo.png",
            "active": True,
        }
    ]
    promo_items = [
        {
            "id": 900,
            "class": "akciya",
            "name": "Snack bonus",
            "lore": "За 2 закуски начислим бонусы",
            "priority": 10,
            "active": True,
            "condition": "ID(101).QTY >= 2",
            "reward": "POINTS(50)",
            "notify": "Начислены бонусы",
            "reward_mode": "once",
            "limit_per_order": "",
            "limit_per_user_per_day": "",
            "start_at": "",
            "end_at": "",
            "dsl_valid": True,
        }
    ]
    saved_applications = []
    monkeypatch.setattr(app_module, "load_menu_items", lambda: menu_items)
    monkeypatch.setattr(app_module, "load_promo_items", lambda: promo_items)
    monkeypatch.setattr(app_module, "load_promo_application_counts", lambda **kwargs: {})
    monkeypatch.setattr(
        app_module,
        "save_promotion_applications",
        lambda **kwargs: saved_applications.append(kwargs),
    )

    csrf_token = get_csrf_token(client)
    login_response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "phone": user["phone"],
            "password": "1234",
        },
    )
    assert login_response.status_code == 200

    booking_dt = datetime.now() + timedelta(days=1)
    booking_response = client.post(
        "/book",
        json={
            "table_id": 1,
            "date": booking_dt.strftime("%Y-%m-%d"),
            "time": booking_dt.strftime("%H:%M"),
            "name": user["name"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert booking_response.status_code == 200

    payment_response = client.post(
        "/payment",
        data={
            "csrf_token": csrf_token,
            "items_json": json.dumps([{"id": 101, "qty": 2}], ensure_ascii=False),
            "comment": "Тест акции",
            "serve_mode": "booking_start",
        },
    )
    assert payment_response.status_code == 200
    payment_html = payment_response.get_data(as_text=True)
    preview_token_marker = 'name="preview_token" value="'
    preview_token = payment_html.split(preview_token_marker, 1)[1].split('"', 1)[0]

    confirm_response = client.post(
        "/payment/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": preview_token,
        },
        follow_redirects=False,
    )
    assert confirm_response.status_code == 302

    orders = read_json(app_module.ORDERS_PATH)
    assert len(orders) == 1
    assert orders[0]["promo_points"] == 50
    assert orders[0]["promotions_applied"] == [
        {
            "promo_id": 900,
            "name": "Snack bonus",
            "reward_kind": "POINTS",
            "applied_count": 1,
            "priority": 10,
            "notify": "Начислены бонусы",
        }
    ]
    assert saved_applications[0]["order_id"] == 1
    assert saved_applications[0]["user_id"] == user["id"]
    assert saved_applications[0]["applied_promotions"][0]["promo_id"] == 900

    users = read_json(app_module.USERS_PATH)
    assert users[0]["balance"] == orders[0]["bonus_earned"] + 50


def test_checkout_preview_token_is_bound_to_user(app_module):
    token = app_module.issue_checkout_preview_token({"payable_total": 123}, user_id=1)

    assert app_module.verify_checkout_preview_token(token, expected_user_id=1) == {"payable_total": 123}
    assert app_module.verify_checkout_preview_token(token, expected_user_id=2) is None


def test_payment_confirm_recomputes_promotions_at_confirmation(app_module, client, monkeypatch):
    user = build_user(
        app_module,
        balance=0,
        cards=[
            {
                "id": 1,
                "brand": "MIR",
                "last4": "4242",
                "expiry": "12/30",
                "holder": "TEST USER",
                "active": True,
            }
        ],
    )
    write_json(app_module.USERS_PATH, [user])

    menu_items = [
        {
            "id": 101,
            "name": "Закуска",
            "type": "закуски",
            "price": 300,
            "photo": "menu_items/test/photo.png",
            "active": True,
        }
    ]
    promo_items = [
        {
            "id": 901,
            "class": "akciya",
            "name": "Transient bonus",
            "lore": "За 2 закуски начислим бонусы",
            "priority": 10,
            "active": True,
            "condition": "ID(101).QTY >= 2",
            "reward": "POINTS(50)",
            "notify": "Начислены бонусы",
            "reward_mode": "once",
            "limit_per_order": "",
            "limit_per_user_per_day": "",
            "start_at": "",
            "end_at": "",
            "dsl_valid": True,
        }
    ]
    monkeypatch.setattr(app_module, "load_menu_items", lambda: menu_items)
    monkeypatch.setattr(app_module, "load_promo_items", lambda: promo_items)

    csrf_token = get_csrf_token(client)
    login_response = client.post(
        "/login",
        data={
            "csrf_token": csrf_token,
            "phone": user["phone"],
            "password": "1234",
        },
    )
    assert login_response.status_code == 200

    booking_dt = datetime.now() + timedelta(days=1)
    booking_response = client.post(
        "/book",
        json={
            "table_id": 1,
            "date": booking_dt.strftime("%Y-%m-%d"),
            "time": booking_dt.strftime("%H:%M"),
            "name": user["name"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert booking_response.status_code == 200

    payment_response = client.post(
        "/payment",
        data={
            "csrf_token": csrf_token,
            "items_json": json.dumps([{"id": 101, "qty": 2}], ensure_ascii=False),
            "comment": "Тест пересчёта",
            "serve_mode": "booking_start",
        },
    )
    assert payment_response.status_code == 200
    payment_html = payment_response.get_data(as_text=True)
    preview_token_marker = 'name="preview_token" value="'
    preview_token = payment_html.split(preview_token_marker, 1)[1].split('"', 1)[0]

    monkeypatch.setattr(app_module, "load_promo_items", lambda: [])

    confirm_response = client.post(
        "/payment/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": preview_token,
        },
        follow_redirects=False,
    )
    assert confirm_response.status_code == 302

    orders = read_json(app_module.ORDERS_PATH)
    assert len(orders) == 1
    assert orders[0]["promo_points"] == 0
    assert orders[0]["promotions_applied"] == []


def test_delivery_does_not_apply_akciya_promotions(app_module, client, monkeypatch):
    user = build_user(app_module, balance=0)
    write_json(app_module.USERS_PATH, [user])

    promo_item = {
        "id": 901,
        "class": "akciya",
        "name": "Delivery blocked",
        "lore": "Не должна применяться на доставке",
        "priority": 10,
        "active": True,
        "condition": "ORDER.SUM >= 100",
        "reward": "POINTS(50)",
        "notify": "Начислены бонусы",
        "reward_mode": "once",
        "limit_per_order": "",
        "limit_per_user_per_day": "",
        "start_at": "",
        "end_at": "",
        "dsl_valid": True,
    }
    monkeypatch.setattr(app_module, "load_promo_items", lambda: [promo_item])
    csrf_token = get_csrf_token(client)
    client.post(
        "/login",
        data={"csrf_token": csrf_token, "phone": user["phone"], "password": "1234"},
    )
    menu_item = app_module.load_menu_items()[0]

    delivery_response = client.post(
        "/delivery/payment",
        data={
            "csrf_token": csrf_token,
            "items_json": json.dumps([{"id": menu_item["id"], "qty": 1}], ensure_ascii=False),
            "delivery_name": user["name"],
            "delivery_phone": user["phone"],
            "delivery_street": "Советский проспект",
            "delivery_house": "10",
        },
        follow_redirects=False,
    )

    assert delivery_response.status_code == 302
    with client.session_transaction() as session_state:
        preview = session_state["delivery_checkout_preview"]
    assert preview["promo_points"] == 0
    assert preview["promotions_applied"] == []


def test_notifications_show_only_one_promo_item(app_module, client, monkeypatch):
    user = build_user(app_module, balance=0)
    write_json(app_module.USERS_PATH, [user])
    csrf_token = get_csrf_token(client)
    client.post(
        "/login",
        data={"csrf_token": csrf_token, "phone": user["phone"], "password": "1234"},
    )
    monkeypatch.setattr(
        app_module,
        "load_promo_items",
        lambda: [
            {"id": 1, "class": "reklama", "text": "Реклама 1", "active": True},
            {"id": 2, "class": "akciya", "name": "Акция 2", "lore": "Описание", "active": True},
        ],
    )
    monkeypatch.setattr(
        app_module.menu_content,
        "load_promo_items",
        lambda include_inactive=False: [
            {"id": 1, "class": "reklama", "text": "Реклама 1", "active": True},
            {"id": 2, "class": "akciya", "name": "Акция 2", "lore": "Описание", "active": True},
        ],
    )

    response = client.get("/notifications")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert html.count("notice--promo") == 1
