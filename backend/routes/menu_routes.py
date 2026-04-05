from flask import redirect, render_template, url_for


def _attach_menu_popularity(items, get_popular_analytics=None):
    menu_items = [dict(item or {}) for item in (items or [])]
    popularity_by_id = {}
    if callable(get_popular_analytics):
        try:
            analytics = get_popular_analytics({"period": "30d", "mode": "all"}) or {}
        except Exception:
            analytics = {}
        for entry in analytics.get("full_items") or []:
            try:
                item_id = int(entry.get("id") or 0)
            except (TypeError, ValueError):
                item_id = 0
            if item_id <= 0:
                continue
            try:
                popularity_by_id[item_id] = int(entry.get("qty_total") or 0)
            except (TypeError, ValueError):
                popularity_by_id[item_id] = 0
    for item in menu_items:
        try:
            item_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            item_id = 0
        fallback_popularity = item.get("orders_count", item.get("popularity", 0))
        try:
            fallback_popularity = int(fallback_popularity or 0)
        except (TypeError, ValueError):
            fallback_popularity = 0
        item["popularity_sort"] = popularity_by_id.get(item_id, fallback_popularity)
    return menu_items


def menu_item_route(item_id, load_menu_items):
    return redirect(url_for("menu"))


def menu_route(load_menu_items, get_popular_analytics=None):
    return render_template(
        "menu.html",
        items=_attach_menu_popularity(load_menu_items(), get_popular_analytics),
    )
