import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from conftest import write_json


def get_csrf_token(client):
    client.get("/")
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
    preview_token = payment_html.split(preview_token_marker, 1)[1].split('"', 1)[0]
    assert preview_token

    payment_confirm_response = client.post(
        "/payment/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": preview_token,
        },
        follow_redirects=False,
    )
    assert payment_confirm_response.status_code == 302
    assert "/orders/1" in payment_confirm_response.headers["Location"]

    orders = read_json(app_module.ORDERS_PATH)
    assert len(orders) == 1
    assert orders[0]["payable_total"] == max(0, menu_item["price"] * 2 - 120)

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
    preview_token = parse_qs(urlparse(delivery_location).query)["preview_token"][0]

    delivery_confirm_response = client.post(
        "/delivery/confirm",
        data={
            "csrf_token": csrf_token,
            "preview_token": preview_token,
        },
        follow_redirects=False,
    )
    assert delivery_confirm_response.status_code == 302
    assert "/orders/2" in delivery_confirm_response.headers["Location"]

    orders_after_delivery = read_json(app_module.ORDERS_PATH)
    assert len(orders_after_delivery) == 2
    assert orders_after_delivery[1]["order_type"] == "delivery"
