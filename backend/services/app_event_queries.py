import json
from typing import Any


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_pagination(page: int | str | None, per_page: int | str | None, *, default_per_page: int = 25, max_per_page: int = 100):
    try:
        normalized_page = max(1, int(page or 1))
    except (TypeError, ValueError):
        normalized_page = 1
    try:
        normalized_per_page = int(per_page or default_per_page)
    except (TypeError, ValueError):
        normalized_per_page = default_per_page
    normalized_per_page = max(1, min(max_per_page, normalized_per_page))
    return normalized_page, normalized_per_page


def _build_pagination(total: int, page: int, per_page: int):
    total = max(0, int(total or 0))
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = min(max(1, page), total_pages)
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "offset": (page - 1) * per_page,
    }


def list_app_events(service, *, filters: dict | None = None, limit: int = 50, page: int = 1):
    filters = filters or {}
    normalized_page, normalized_per_page = _normalize_pagination(page, limit, default_per_page=limit, max_per_page=100)
    conditions = []
    params = []

    user_id = str(filters.get("user_id") or "").strip()
    if user_id:
        conditions.append("CAST(e.user_id AS TEXT) = %s")
        params.append(user_id)

    event_type = str(filters.get("event_type") or "").strip()
    if event_type:
        conditions.append("e.event_type = %s")
        params.append(event_type)

    entity_type = str(filters.get("entity_type") or "").strip()
    if entity_type:
        conditions.append("e.entity_type = %s")
        params.append(entity_type)

    method = str(filters.get("method") or "").strip().upper()
    if method:
        conditions.append("e.method = %s")
        params.append(method)

    status_code = str(filters.get("status_code") or "").strip()
    if status_code:
        conditions.append("CAST(e.status_code AS TEXT) = %s")
        params.append(status_code)

    path = str(filters.get("path") or "").strip()
    if path:
        conditions.append("e.path ILIKE %s")
        params.append(f"%{path}%")

    date_from = str(filters.get("date_from") or "").strip()
    if date_from:
        conditions.append("e.created_at::date >= %s::date")
        params.append(date_from)

    date_to = str(filters.get("date_to") or "").strip()
    if date_to:
        conditions.append("e.created_at::date <= %s::date")
        params.append(date_to)

    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
    count_row = service._fetch_one(
        f"""
        SELECT COUNT(*) AS count
        FROM app_events e
        {where_sql}
        """,
        tuple(params),
    ) or {"count": 0}
    pagination = _build_pagination(_safe_int(count_row.get("count")), normalized_page, normalized_per_page)
    rows = service._fetch_all(
        f"""
        SELECT e.*, u.name AS user_name, u.phone AS user_phone
        FROM app_events e
        LEFT JOIN users u ON u.id = e.user_id
        {where_sql}
        ORDER BY e.created_at DESC, e.id DESC
        LIMIT {pagination["per_page"]} OFFSET {pagination["offset"]}
        """,
        tuple(params),
    )
    for row in rows:
        payload_text = row.get("payload_json") or "{}"
        try:
            row["payload"] = json.loads(payload_text)
        except json.JSONDecodeError:
            row["payload"] = {"raw": payload_text}
    return rows, pagination


def app_event_filter_options(service):
    if service._app_event_filter_options_cache is not None:
        return service._app_event_filter_options_cache
    users = service._fetch_all(
        """
        SELECT DISTINCT u.id, u.name, u.phone
        FROM app_events e
        LEFT JOIN users u ON u.id = e.user_id
        WHERE e.user_id IS NOT NULL
        ORDER BY u.name NULLS LAST, u.id
        """
    )
    event_types = service._fetch_all("SELECT DISTINCT event_type FROM app_events ORDER BY event_type")
    entity_types = service._fetch_all("SELECT DISTINCT entity_type FROM app_events WHERE entity_type <> '' ORDER BY entity_type")
    methods = service._fetch_all("SELECT DISTINCT method FROM app_events WHERE method <> '' ORDER BY method")
    status_codes = service._fetch_all("SELECT DISTINCT status_code FROM app_events ORDER BY status_code")
    service._app_event_filter_options_cache = {
        "users": users,
        "event_types": event_types,
        "entity_types": entity_types,
        "methods": methods,
        "status_codes": status_codes,
    }
    return service._app_event_filter_options_cache
