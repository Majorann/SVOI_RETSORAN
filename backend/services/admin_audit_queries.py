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


def list_audit_actions(service, *, entity_type: str | None = None, entity_id: str | int | None = None, filters: dict | None = None, limit: int = 50, page: int = 1):
    filters = filters or {}
    normalized_page, normalized_per_page = _normalize_pagination(page, limit, default_per_page=limit, max_per_page=100)
    conditions = []
    params = []
    if entity_type:
        conditions.append("a.entity_type = %s")
        params.append(entity_type)
    if entity_id is not None:
        conditions.append("a.entity_id = %s")
        params.append(str(entity_id))
    admin_user_id = str(filters.get("admin_user_id") or "").strip()
    if admin_user_id:
        conditions.append("CAST(a.admin_user_id AS TEXT) = %s")
        params.append(admin_user_id)
    action_type = str(filters.get("action_type") or "").strip()
    if action_type:
        conditions.append("a.action_type = %s")
        params.append(action_type)
    entity_type_filter = str(filters.get("entity_type") or "").strip()
    if entity_type_filter:
        conditions.append("a.entity_type = %s")
        params.append(entity_type_filter)
    date_from = str(filters.get("date_from") or "").strip()
    if date_from:
        conditions.append("a.created_at::date >= %s::date")
        params.append(date_from)
    date_to = str(filters.get("date_to") or "").strip()
    if date_to:
        conditions.append("a.created_at::date <= %s::date")
        params.append(date_to)
    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
    count_row = service._fetch_one(
        f"""
        SELECT COUNT(*) AS count
        FROM admin_actions a
        {where_sql}
        """,
        tuple(params),
    ) or {"count": 0}
    pagination = _build_pagination(_safe_int(count_row.get("count")), normalized_page, normalized_per_page)
    rows = service._fetch_all(
        f"""
        SELECT a.*, u.name AS admin_name
        FROM admin_actions a
        LEFT JOIN users u ON u.id = a.admin_user_id
        {where_sql}
        ORDER BY a.created_at DESC, a.id DESC
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
    if entity_type is not None or entity_id is not None:
        return rows
    return rows, pagination


def audit_filter_options(service):
    if service._audit_filter_options_cache is not None:
        return service._audit_filter_options_cache
    admins = service._fetch_all(
        """
        SELECT DISTINCT u.id, u.name
        FROM admin_actions a
        LEFT JOIN users u ON u.id = a.admin_user_id
        WHERE a.admin_user_id IS NOT NULL
        ORDER BY u.name NULLS LAST, u.id
        """
    )
    actions = service._fetch_all("SELECT DISTINCT action_type FROM admin_actions ORDER BY action_type")
    entities = service._fetch_all("SELECT DISTINCT entity_type FROM admin_actions ORDER BY entity_type")
    service._audit_filter_options_cache = {"admins": admins, "actions": actions, "entities": entities}
    return service._audit_filter_options_cache
