from conftest import write_json
from services.menu_content import MenuContentService


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
    assert "Dashboard" in allowed.get_data(as_text=True)


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
