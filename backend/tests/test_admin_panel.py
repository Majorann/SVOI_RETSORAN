from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask, session

from conftest import write_json
from services.auth_session import AuthSessionService
from services.menu_content import MenuContentService
from services.admin_service import AdminService


def seed_logged_in_session(client, user_id=1, user_name="Админ"):
    client.get("/")
    with client.session_transaction() as session_state:
        session_state["user_id"] = user_id
        session_state["user_name"] = user_name


def get_csrf_token(client):
    client.get("/")
    with client.session_transaction() as session_state:
        return session_state["csrf_token"]


def test_admin_pages_require_admin_membership(app_module, client, monkeypatch):
    write_json(
        app_module.USERS_PATH,
        [
            {
                "id": 1,
                "name": "Admin",
                "phone": "+79990000001",
                "password_hash": app_module.hash_password("1234"),
                "balance": 0,
                "cards": [],
                "created_at": "2026-03-19T10:00:00",
            }
        ],
    )
    seed_logged_in_session(client)

    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: False)
    denied = client.get("/admin/dashboard")
    assert denied.status_code == 403
    assert "admin_users" in denied.get_data(as_text=True)

    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(
        app_module.admin_service,
        "get_dashboard_data",
        lambda: {"kpis": {"active_orders": 0, "active_bookings": 0, "delivery_in_work": 0, "today_revenue": 0, "today_cancellations": 0, "overdue_deliveries": 0}, "attention": [], "nearest_bookings": [], "latest_actions": [], "today_orders": []},
    )
    allowed = client.get("/admin/dashboard")
    assert allowed.status_code == 200
    assert "Панель" in allowed.get_data(as_text=True)


def test_admin_api_returns_403_for_non_admin(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    csrf_token = get_csrf_token(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: False)
    response = client.post(
        "/admin/api/orders/1/status",
        json={"status": "served", "reason": "test"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 403
    assert response.get_json()["ok"] is False


def test_admin_api_runs_content_autosync(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    csrf_token = get_csrf_token(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(
        app_module.admin_service,
        "sync_content_from_host",
        lambda admin_user_id, reason: {
            "menu_items_synced": 12,
            "menu_items_deleted": 5,
            "promotions_synced": 4,
            "promotions_deleted": 1,
            "reklama_found": 2,
        },
    )

    response = client.post(
        "/admin/api/content/autosync",
        json={"reason": "manual sync"},
        headers={"X-CSRF-Token": csrf_token},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert "меню 12" in payload["toast"]
    assert "удалено 5" in payload["toast"]


def test_admin_orders_filter_renders_all_status_options(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(app_module.admin_service, "list_orders", lambda filters: [])

    response = client.get("/admin/orders")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Все статусы" in html
    assert "Принят" in html
    assert "Готовится" in html
    assert "Готов" in html
    assert "Выдача" in html
    assert "Завершён" in html
    assert "Отменён" in html


def test_admin_menu_route_reads_admin_menu_items_once(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    app_module.admin_service.active_storage = "postgres"
    calls = {"count": 0}

    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)

    def fake_load_menu_items_admin():
        calls["count"] += 1
        return [
            {"id": 1, "name": "Борщ", "type": "Супы", "featured": True},
            {"id": 2, "name": "Паста", "type": "Горячее", "featured": False},
        ]

    monkeypatch.setattr(app_module.admin_service.menu_content, "load_menu_items_admin", fake_load_menu_items_admin)

    response = client.get("/admin/menu")

    assert response.status_code == 200
    assert calls["count"] == 1


def test_admin_users_route_renders_pagination(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(
        app_module.admin_service,
        "list_users",
        lambda search, page=1, per_page=25: (
            [{"id": 1, "name": "Админ", "phone": "+7999", "balance": 0, "orders_count": 2, "bookings_count": 1, "created_at": "2026-03-20T10:00:00", "is_admin": True}],
            {"page": 2, "per_page": 25, "total": 60, "total_pages": 3, "has_prev": True, "has_next": True, "prev_page": 1, "next_page": 3, "offset": 25},
        ),
    )

    response = client.get("/admin/users?search=test&page=2")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Страница 2 из 3" in html
    assert "search=test" in html


def test_admin_users_route_preserves_per_page(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(
        app_module.admin_service,
        "list_users",
        lambda search, page=1, per_page=25: (
            [],
            {"page": 1, "per_page": per_page, "total": 80, "total_pages": 4, "has_prev": False, "has_next": True, "prev_page": 1, "next_page": 2, "offset": 0},
        ),
    )

    response = client.get("/admin/users?search=test&per_page=10")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "10 на странице" in html
    assert "per_page=10" in html


def test_menu_content_active_flag_is_backward_compatible(tmp_path, monkeypatch):
    menu_root = tmp_path / "menu_items"
    item_dir = menu_root / "Тест блюдо"
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "photo.png").write_bytes(b"png")
    (item_dir / "item.txt").write_text(
        "\n".join(
            [
                "id=101",
                "name=Тест блюдо",
                "type=Горячие блюда",
                "price=440",
                "weight=320 г",
                "lore=Описание",
                "featured=false",
                "active=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    import services.menu_content as menu_content_module

    monkeypatch.setattr(menu_content_module, "MENU_ITEMS_PATH", menu_root)
    service = MenuContentService(
        menu_cache_enabled=False,
        menu_cache_key="menu:test",
        menu_cache_ttl_seconds=60,
        redis_module=None,
        redis_url="",
    )
    public_items = service.load_menu_items_from_disk(include_inactive=False)
    admin_items = service.load_menu_items_from_disk(include_inactive=True)

    assert public_items == []
    assert len(admin_items) == 1
    assert admin_items[0]["active"] is False


def test_admin_service_marks_completed_delivery_as_served_instead_of_overdue(monkeypatch):
    service = AdminService(active_storage="postgres", menu_content=None)
    now = datetime(2026, 3, 20, 10, 0, 0)
    order = {
        "id": 77,
        "order_type": "delivery",
        "status": "cooking",
        "created_at": "2026-03-20T09:00:00",
        "delivery_eta_minutes": 20,
    }

    monkeypatch.setattr(
        "services.admin_service.current_time_value",
        lambda: now.replace(hour=10, minute=0, second=0, microsecond=0),
    )

    effective_status = service.resolve_effective_order_status(order)

    assert effective_status == "served"
    assert service.is_delivery_overdue(order) is False


def test_admin_list_orders_uses_effective_status_from_timeline(monkeypatch):
    service = AdminService(active_storage="postgres", menu_content=None)
    order = {
        "id": 15,
        "user_id": 1,
        "order_type": "dine_in",
        "status": "preparing",
        "created_at": "2026-03-20T09:00:00",
        "booking_table_id": 4,
        "items_total": 1000,
        "points_applied": 0,
        "payable_total": 1000,
        "bonus_earned": 50,
        "booking_date": "2026-03-20",
        "booking_time": "09:30:00",
    }

    monkeypatch.setattr("services.admin_service.current_time_value", lambda: datetime(2026, 3, 20, 10, 30, 0))
    monkeypatch.setattr(service, "_fetch_all", lambda query, params=(): [dict(order)])

    orders = service.list_orders({})

    assert len(orders) == 1
    assert orders[0]["status"] == "served"
    assert orders[0]["status_label"] == "Выдан"


def test_admin_analytics_uses_sql_aggregates(monkeypatch):
    class MenuContentStub:
        def load_menu_items_admin(self):
            return [
                {"id": 1, "name": "Борщ", "type": "Супы", "price": 450},
                {"id": 2, "name": "Паста", "type": "Горячее", "price": 520},
            ]

    service = AdminService(active_storage="postgres", menu_content=MenuContentStub())

    def fake_fetch_one(query, params=()):
        if "COUNT(*) AS count FROM bookings" in query:
            return {"count": 4}
        if "COUNT(*) AS orders_count" in query:
            return {
                "orders_count": 3,
                "cancellations": 1,
                "points_applied": 100,
                "bonus_earned": 55,
                "revenue": 1100,
                "dine_in_revenue": 500,
                "delivery_revenue": 600,
            }
        return {}

    def fake_fetch_all(query, params=()):
        if "GROUP BY created_at::date" in query:
            return [
                {
                    "label": "2026-03-19",
                    "orders_count": 2,
                    "cancellations": 1,
                    "revenue": 500,
                    "dine_in_orders": 1,
                    "delivery_orders": 1,
                },
                {
                    "label": "2026-03-20",
                    "orders_count": 1,
                    "cancellations": 0,
                    "revenue": 600,
                    "dine_in_orders": 0,
                    "delivery_orders": 1,
                },
            ]
        if "FROM order_items oi" in query:
            return [{"item_id": 1, "name": "Борщ", "qty_total": 3, "revenue_total": 1350}]
        return []

    monkeypatch.setattr("services.admin_service.datetime", type("FixedDateTime", (), {"now": staticmethod(lambda: datetime(2026, 3, 20, 12, 0, 0))}))
    monkeypatch.setattr(service, "_fetch_one", fake_fetch_one)
    monkeypatch.setattr(service, "_fetch_all", fake_fetch_all)

    analytics = service.get_analytics({"period": "7d", "mode": "all"})

    assert analytics["metrics"]["orders_count"] == 3
    assert analytics["metrics"]["revenue"] == 1100
    assert analytics["metrics"]["cancellations"] == 1
    assert analytics["metrics"]["average_check"] == 366
    assert analytics["charts"]["revenue_by_day"][-2:] == [
        {"label": "2026-03-19", "value": 500},
        {"label": "2026-03-20", "value": 600},
    ]
    assert analytics["charts"]["channels_by_day"][-2:] == [
        {"label": "2026-03-19", "dine_in": 1, "delivery": 1},
        {"label": "2026-03-20", "dine_in": 0, "delivery": 1},
    ]
    assert analytics["top_items"][0]["name"] == "Борщ"
    assert analytics["no_sales_items"][0]["name"] == "Паста"


def test_menu_content_admin_and_promo_use_memory_cache(tmp_path, monkeypatch):
    service = MenuContentService(
        menu_cache_enabled=False,
        menu_cache_key="menu:test",
        menu_cache_ttl_seconds=60,
        redis_module=None,
        redis_url="",
    )
    calls = {"menu": 0, "promo": 0}
    promo_root = tmp_path / "promo_items" / "akciya" / "spring"
    promo_root.mkdir(parents=True, exist_ok=True)
    (promo_root / "item.txt").write_text("id=1\nclass=akciya\nname=Акция\nlore=Описание\npriority=10\nactive=true\n", encoding="utf-8")
    (promo_root / "photo.png").write_bytes(b"png")

    def fake_load_menu(include_inactive=False):
        calls["menu"] += 1
        return [{"id": 1 if include_inactive else 2, "name": "Тест"}]

    def fake_parse(meta, slug, photo):
        calls["promo"] += 1
        return {"id": 1, "class": "akciya", "name": "Акция", "priority": 10, "active": True}

    monkeypatch.setattr(service, "load_menu_items_from_disk", fake_load_menu)
    monkeypatch.setattr(service, "parse_promo_item", fake_parse)
    monkeypatch.setattr("services.menu_content.PROMO_ITEMS_PATH", tmp_path / "promo_items")
    monkeypatch.setattr(service, "parse_menu_meta", lambda meta_path: {"id": "1", "class": "akciya", "name": "Акция", "lore": "Описание"})
    monkeypatch.setattr(service, "resolve_photo_name", lambda item_dir, photo_names: "photo.png")

    first_admin = service.load_menu_items_admin()
    second_admin = service.load_menu_items_admin()
    first_promo = service.load_promo_items()
    second_promo = service.load_promo_items()

    assert first_admin == second_admin
    assert first_promo == second_promo
    assert calls["menu"] == 1
    assert calls["promo"] == 1


def test_auth_session_caches_users_and_bookings_within_request():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    calls = {"users": 0, "bookings": 0}

    def load_users():
        calls["users"] += 1
        return [{"id": 7, "name": "Тест"}]

    def load_bookings():
        calls["bookings"] += 1
        return [{"id": 1, "user_id": 7}, {"id": 2, "user_id": 99}]

    service = AuthSessionService(
        app=app,
        auth_session_cookie_name="auth_session",
        auth_session_cookie_max_age_seconds=3600,
        auth_session_serializer=None,
        checkout_preview_max_age_seconds=3600,
        checkout_preview_serializer=None,
        login_debug_enabled=False,
        login_debug_log_path=None,
        login_debug_lock=None,
        session_debug_enabled=False,
        session_debug_log_path=None,
        session_debug_lock=None,
        load_users=load_users,
        load_bookings=load_bookings,
        get_user_preparing_orders=lambda user_id: [{"id": 10, "user_id": user_id}],
    )

    with app.test_request_context("/"):
        session["user_id"] = 7
        assert service.get_request_user() == {"id": 7, "name": "Тест"}
        assert service.get_request_user() == {"id": 7, "name": "Тест"}
        bookings, preparing = service.get_request_notification_data()
        bookings_again, preparing_again = service.get_request_notification_data()

    assert bookings == [{"id": 1, "user_id": 7}]
    assert preparing == [{"id": 10, "user_id": 7}]
    assert bookings_again == bookings
    assert preparing_again == preparing
    assert calls["users"] == 1
    assert calls["bookings"] == 1


def test_admin_audit_filter_options_are_cached():
    service = AdminService(active_storage="postgres", menu_content=None)
    calls = {"count": 0}

    def fake_fetch_all(query, params=()):
        calls["count"] += 1
        if "SELECT DISTINCT u.id, u.name" in query:
            return [{"id": 1, "name": "Админ"}]
        if "SELECT DISTINCT action_type" in query:
            return [{"action_type": "order_status_changed"}]
        if "SELECT DISTINCT entity_type" in query:
            return [{"entity_type": "order"}]
        return []

    service._fetch_all = fake_fetch_all

    first = service.audit_filter_options()
    second = service.audit_filter_options()

    assert first == second
    assert calls["count"] == 3


def test_admin_api_validates_promo_dsl(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    csrf_token = get_csrf_token(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(
        app_module.admin_service.menu_content,
        "load_menu_items_admin",
        lambda: [{"id": 101, "name": "Закуска", "type": "закуски", "price": 300, "active": True}],
    )

    response = client.post(
        "/admin/api/promo/validate",
        json={
            "name": "Snack bonus",
            "lore": "За 2 закуски начислим бонусы",
            "condition": "ID(101).QTY >= 2",
            "reward": "POINTS(100)",
            "notify": "Начислены бонусы",
            "reward_mode": "once",
            "priority": 10,
            "active": "1",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["summary"]["reward_kind"] == "POINTS"


def test_admin_promo_page_renders_dsl_helper(app_module, client, monkeypatch):
    seed_logged_in_session(client)
    app_module.admin_service.active_storage = "postgres"
    monkeypatch.setattr(app_module.admin_service, "is_admin_user", lambda user_id: True)
    monkeypatch.setattr(app_module.admin_service.menu_content, "load_promo_items", lambda include_inactive=True: [])
    monkeypatch.setattr(
        app_module.admin_service.menu_content,
        "load_menu_items_admin",
        lambda: [
            {"id": 101, "name": "Закуска", "type": "закуски", "price": 300, "active": True},
            {"id": 205, "name": "Суп", "type": "супы", "price": 400, "active": True},
        ],
    )

    response = client.get("/admin/promo")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "DSL helper для akciya" in html
    assert "Конструктор условия" in html
    assert "Конструктор награды" in html
    assert "закуски" in html
    assert "205" in html


def test_admin_service_rejects_invalid_promo_dsl_before_save(app_module, monkeypatch):
    monkeypatch.setattr(
        app_module.admin_service.menu_content,
        "load_menu_items_admin",
        lambda: [{"id": 101, "name": "Закуска", "type": "закуски", "price": 300, "active": True}],
    )

    with pytest.raises(ValueError, match="DSL акции невалиден"):
        app_module.admin_service.save_promo_item(
            form={
                "class_name": "akciya",
                "name": "Broken promo",
                "lore": "Некорректная акция",
                "condition": "ID(999).QTY >= 2",
                "reward": "POINTS(100)",
                "notify": "",
                "reward_mode": "once",
                "priority": "10",
                "reason": "test",
                "active": "1",
            },
            photo=None,
            admin_user_id=1,
        )


def test_admin_service_save_promo_item_stores_akciya_in_postgres(tmp_path, monkeypatch):
    promo_root = tmp_path / "promo_items"
    captured = {}

    class MenuContentStub:
        def __init__(self):
            self.invalidated = 0

        def load_promo_items(self, include_inactive=True):
            return []

        def load_menu_items_admin(self):
            return [{"id": 74, "name": "FPV-Друн", "type": "закуски", "price": 300, "active": True}]

        def parse_menu_meta(self, path):
            return {}

        def invalidate_local_cache(self):
            self.invalidated += 1

        def get_redis_client(self):
            return None

    service = AdminService(active_storage="postgres", menu_content=MenuContentStub())
    monkeypatch.setattr("services.admin_service.PROMO_ITEMS_PATH", promo_root)
    monkeypatch.setattr(service, "log_admin_action", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "_pg_store",
        lambda: type(
            "PgStoreStub",
            (),
            {
                "upsert_promotion": staticmethod(
                    lambda payload: (captured.setdefault("payload", dict(payload)), 1)[1]
                )
            },
        )(),
    )

    service.save_promo_item(
        form={
            "class_name": "akciya",
            "slug": "test-fpv-74-bonus",
            "name": "Тест FPV 74",
            "lore": "Тестовая акция",
            "condition": "ID(74).QTY >= 1",
            "reward": "POINTS(100)",
            "notify": "Начислены 100 бонусов",
            "reward_mode": "once",
            "priority": "100",
            "reason": "test",
            "active": "1",
        },
        photo=None,
        admin_user_id=1,
    )

    meta_path = promo_root / "akciya" / "test-fpv-74-bonus" / "item.txt"
    assert meta_path.exists() is False
    assert captured["payload"]["slug"] == "test-fpv-74-bonus"
    assert captured["payload"]["name"] == "Тест FPV 74"
    assert captured["payload"]["condition"] == "ID(74).QTY >= 1"
    assert captured["payload"]["reward"] == "POINTS(100)"
    assert captured["payload"]["updated_by_admin_user_id"] == 1
    assert service.menu_content.invalidated == 1


def test_menu_content_loads_menu_items_from_postgres(monkeypatch):
    service = MenuContentService(
        active_storage="postgres",
        menu_cache_enabled=False,
        menu_cache_key="menu:test",
        menu_cache_ttl_seconds=60,
        redis_module=None,
        redis_url="",
    )

    class PgStoreStub:
        @staticmethod
        def load_menu_items(include_inactive=False):
            assert include_inactive is False
            return [
                {
                    "id": 12,
                    "slug": "borsh",
                    "name": "Борщ",
                    "lore": "Горячий",
                    "type": "Супы",
                    "price": 450,
                    "photo_path": "menu_items/borsh/photo.webp",
                    "portion_label": "320",
                    "popularity": 5,
                    "featured": True,
                    "active": True,
                }
            ]

    monkeypatch.setattr(
        "services.menu_content.importlib.import_module",
        lambda name: PgStoreStub if name == "storage.pg_store" else None,
    )

    items = service.load_menu_items()

    assert len(items) == 1
    assert items[0]["id"] == 12
    assert items[0]["photo"] == "menu_items/borsh/photo.webp"
    assert items[0]["portion_label"] == "320 г"
    assert items[0]["featured"] is True
    assert items[0]["active"] is True


def test_menu_content_syncs_host_content_to_postgres(monkeypatch):
    service = MenuContentService(
        active_storage="postgres",
        menu_cache_enabled=False,
        menu_cache_key="menu:test",
        menu_cache_ttl_seconds=60,
        redis_module=None,
        redis_url="",
    )
    invalidated = {"count": 0}

    class PgStoreStub:
        @staticmethod
        def sync_menu_items_from_disk():
            return {"synced": 7, "deleted": 2}

        @staticmethod
        def sync_promotions_from_disk():
            return {"synced": 3, "deleted": 1}

    monkeypatch.setattr(
        service,
        "_load_disk_promo_items",
        lambda include_inactive, allowed_classes: [{"id": 1}, {"id": 2}] if allowed_classes == {"reklama"} else [],
    )
    monkeypatch.setattr(
        "services.menu_content.importlib.import_module",
        lambda name: PgStoreStub if name == "storage.pg_store" else None,
    )
    monkeypatch.setattr(service, "invalidate_local_cache", lambda *keys: invalidated.__setitem__("count", invalidated["count"] + 1))

    summary = service.sync_host_content_to_storage()

    assert summary == {
        "storage": "postgres",
        "menu_items_synced": 7,
        "menu_items_deleted": 2,
        "promotions_synced": 3,
        "promotions_deleted": 1,
        "reklama_found": 2,
    }
    assert invalidated["count"] == 1


def test_admin_service_allows_info_only_akciya_without_dsl(tmp_path, monkeypatch):
    promo_root = tmp_path / "promo_items"
    captured = {}

    class MenuContentStub:
        def __init__(self):
            self.invalidated = 0

        def load_promo_items(self, include_inactive=True):
            return []

        def load_menu_items_admin(self):
            return []

        def parse_menu_meta(self, path):
            return {}

        def invalidate_local_cache(self):
            self.invalidated += 1

        def get_redis_client(self):
            return None

    service = AdminService(active_storage="postgres", menu_content=MenuContentStub())
    monkeypatch.setattr("services.admin_service.PROMO_ITEMS_PATH", promo_root)
    monkeypatch.setattr(service, "log_admin_action", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "_pg_store",
        lambda: type(
            "PgStoreStub",
            (),
            {
                "upsert_promotion": staticmethod(
                    lambda payload: (captured.setdefault("payload", dict(payload)), 15)[1]
                )
            },
        )(),
    )

    service.save_promo_item(
        form={
            "class_name": "akciya",
            "slug": "info-promo",
            "name": "Инфо акция",
            "lore": "Только описание без DSL",
            "condition": "",
            "reward": "",
            "notify": "",
            "reward_mode": "",
            "priority": "100",
            "reason": "test",
            "active": "1",
        },
        photo=None,
        admin_user_id=1,
    )

    assert captured["payload"]["name"] == "Инфо акция"
    assert captured["payload"]["condition"] == ""
    assert captured["payload"]["reward"] == ""
    assert captured["payload"]["reward_mode"] == ""
    assert service.menu_content.invalidated == 1


def test_admin_service_save_menu_item_stores_menu_in_postgres(tmp_path, monkeypatch):
    menu_root = tmp_path / "menu_items"
    captured = {}

    class MenuContentStub:
        def __init__(self):
            self.invalidated = 0

        def load_menu_items_admin(self):
            return []

        def invalidate_local_cache(self):
            self.invalidated += 1

        def get_redis_client(self):
            return None

    service = AdminService(active_storage="postgres", menu_content=MenuContentStub())
    monkeypatch.setattr("services.admin_service.MENU_ITEMS_PATH", menu_root)
    monkeypatch.setattr(service, "log_admin_action", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "_pg_store",
        lambda: type(
            "PgStoreStub",
            (),
            {
                "upsert_menu_item": staticmethod(
                    lambda payload: (captured.setdefault("payload", dict(payload)), 33)[1]
                )
            },
        )(),
    )

    service.save_menu_item(
        form={
            "slug": "borsh",
            "name": "Борщ",
            "type": "Супы",
            "price": "450",
            "weight": "320",
            "lore": "Горячий",
            "featured": "1",
            "popularity": "7",
            "active": "1",
            "reason": "test",
        },
        photo=None,
        admin_user_id=1,
    )

    assert captured["payload"]["slug"] == "borsh"
    assert captured["payload"]["name"] == "Борщ"
    assert captured["payload"]["type"] == "Супы"
    assert captured["payload"]["price"] == 450
    assert captured["payload"]["portion_label"] == "320"
    assert captured["payload"]["featured"] is True
    assert captured["payload"]["popularity"] == 7
    assert captured["payload"]["updated_by_admin_user_id"] == 1
    assert service.menu_content.invalidated == 1


def test_admin_service_deletes_promo_from_postgres(tmp_path, monkeypatch):
    promo_root = tmp_path / "promo_items"
    deleted = []

    class MenuContentStub:
        def __init__(self):
            self.invalidated = 0

        def load_promo_items(self, include_inactive=True):
            return [{"id": 77, "class": "akciya", "name": "Manual promo", "photo": None}]

        def invalidate_local_cache(self):
            self.invalidated += 1

        def get_redis_client(self):
            return None

    service = AdminService(active_storage="postgres", menu_content=MenuContentStub())
    monkeypatch.setattr("services.admin_service.PROMO_ITEMS_PATH", promo_root)
    monkeypatch.setattr(service, "log_admin_action", lambda **kwargs: None)
    monkeypatch.setattr(
        service,
        "_pg_store",
        lambda: type(
            "PgStoreStub",
            (),
            {"delete_promotion": staticmethod(lambda promo_id: deleted.append(promo_id))},
        )(),
    )

    service.delete_promo_item(
        admin_user_id=1,
        class_name="akciya",
        item_id=77,
        reason="cleanup",
    )

    assert deleted == [77]
    assert service.menu_content.invalidated == 1
