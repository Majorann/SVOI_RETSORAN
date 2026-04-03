from pathlib import Path
import shutil
from typing import Any

from werkzeug.datastructures import FileStorage

from services.path_naming import ascii_slug, canonical_menu_photo_path, canonical_promo_photo_path
from services.promotions import build_dsl_text_from_promo_item, parse_and_validate_promo_source
from services.promotions.ast import PromotionDslError
from services.promotions.validator import PromotionValidationError


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_reward_mode(value: Any, *, require_default: bool) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"", "none", "нет"}:
        return "once" if require_default else ""
    if normalized in {"once", "per_match"}:
        return normalized
    return "once" if require_default else ""


def list_menu_items(service, filters: dict, items: list[dict] | None = None):
    items = list(items) if items is not None else service.menu_content.load_menu_items_admin()
    search = str(filters.get("search") or "").strip().lower()
    category = str(filters.get("category") or "").strip()
    featured = str(filters.get("featured") or "").strip()
    if search:
        items = [item for item in items if search in item.get("name", "").lower()]
    if category:
        items = [item for item in items if item.get("type") == category]
    if featured == "1":
        items = [item for item in items if item.get("featured")]
    return items


def list_promo_items(service, filters: dict, items: list[dict] | None = None):
    items = list(items) if items is not None else service.menu_content.load_promo_items(include_inactive=True)
    item_class = str(filters.get("class_name") or "").strip()
    if item_class:
        items = [item for item in items if item.get("class") == item_class]
    return items


def get_content_scaffold():
    return {
        "todo_blocks": [
            "Hero banner and homepage text are still hardcoded in Jinja templates.",
            "No separate content store has been introduced in this phase.",
            "Promo-backed homepage blocks are managed in /admin/promo.",
        ]
    }


def save_menu_item(service, *, form: dict, photo: FileStorage | None, admin_user_id: int, menu_items_path):
    reason = str(form.get("reason") or "").strip()
    if not reason:
        raise ValueError("Укажите причину изменения.")
    item_id = _safe_int(form.get("id"), 0)
    all_items = service.menu_content.load_menu_items_admin()
    existing = next((item for item in all_items if item["id"] == item_id), None) if item_id else None
    name = str(form.get("name") or "").strip()
    if not name:
        raise ValueError("Название блюда обязательно.")
    folder_name = ascii_slug(str(form.get("slug") or name))
    target_dir = menu_items_path / folder_name
    if existing and existing.get("photo"):
        target_dir = menu_items_path / Path(existing["photo"]).parts[1]
    if not existing:
        item_id = max([item.get("id", 0) for item in all_items] or [0]) + 1
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_photo = save_image(target_dir, photo)
    photo_path = str((existing or {}).get("photo") or "").strip()
    if saved_photo and photo is not None and photo.filename:
        photo_path = canonical_menu_photo_path(target_dir.name, photo.filename)
    menu_payload = {
        "id": item_id,
        "slug": target_dir.name,
        "name": name,
        "type": str(form.get("type") or "").strip(),
        "price": _safe_int(form.get("price"), 0),
        "portion_label": str(form.get("weight") or "").strip(),
        "lore": str(form.get("lore") or "").strip(),
        "featured": _safe_bool(form.get("featured")),
        "popularity": _safe_int(form.get("popularity"), 0),
        "active": _safe_bool(form.get("active"), True),
        "photo_path": photo_path,
        "created_by_admin_user_id": admin_user_id if not existing else None,
        "updated_by_admin_user_id": admin_user_id,
    }
    item_id = service._pg_store().upsert_menu_item(menu_payload)
    if existing:
        action_type = "menu_price_changed" if _safe_int(existing.get("price")) != menu_payload["price"] else "menu_item_updated"
    else:
        action_type = "menu_item_created"
    if existing and not menu_payload["active"]:
        action_type = "menu_item_hidden"
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type=action_type,
        entity_type="menu_item",
        entity_id=item_id,
        reason=reason,
        payload={"name": name, "folder": target_dir.name, "photo_saved": saved_photo},
    )
    invalidate_menu_cache(service)


def save_promo_item(service, *, form: dict, photo: FileStorage | None, admin_user_id: int, promo_items_path):
    reason = str(form.get("reason") or "").strip()
    if not reason:
        raise ValueError("Укажите причину изменения.")
    all_items = service.menu_content.load_promo_items(include_inactive=True)
    item_id = _safe_int(form.get("id"), 0)
    class_name = str(form.get("class_name") or "").strip()
    existing = next((item for item in all_items if item["id"] == item_id and item.get("class") == class_name), None) if item_id else None
    if class_name not in {"akciya", "reklama"}:
        raise ValueError("Недопустимый тип промо.")
    name = str(form.get("name") or form.get("text") or "").strip()
    folder_name = ascii_slug(str(form.get("slug") or name or f"{class_name}-{item_id or 'new'}"))
    target_dir = promo_items_path / class_name / folder_name
    if existing and existing.get("photo"):
        photo_parts = Path(existing["photo"]).parts
        if len(photo_parts) >= 3:
            target_dir = promo_items_path / photo_parts[1] / photo_parts[2]
    existing_dir = find_promo_dir(service, class_name=class_name, item_id=item_id, promo_items_path=promo_items_path) if existing and class_name == "reklama" else None
    if existing_dir is not None:
        target_dir = existing_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_photo = save_image(target_dir, photo)

    if class_name == "akciya":
        payload = validate_promo_form(service, form)
        photo_path = None
        current_photo = str((existing or {}).get("photo") or "").strip()
        if saved_photo and photo is not None and photo.filename:
            photo_path = canonical_promo_photo_path(class_name, target_dir.name, photo.filename)
        elif current_photo:
            photo_path = current_photo
        promotion_payload = {
            "id": item_id or None,
            "slug": target_dir.name,
            "name": payload["name"],
            "lore": payload["lore"],
            "active": _safe_bool(form.get("active"), True),
            "priority": _safe_int(form.get("priority"), 100),
            "condition": payload["condition"],
            "reward": payload["reward"],
            "notify": payload["notify"],
            "reward_mode": payload["reward_mode"],
            "limit_per_order": payload["limit_per_order"],
            "limit_per_user_per_day": payload["limit_per_user_per_day"],
            "start_at": payload["start_at"],
            "end_at": payload["end_at"],
            "photo_path": photo_path or "",
            "created_by_admin_user_id": admin_user_id if not existing else None,
            "updated_by_admin_user_id": admin_user_id,
        }
        item_id = service._pg_store().upsert_promotion(promotion_payload)
    else:
        if not existing:
            item_id = max([item.get("id", 0) for item in all_items] or [0]) + 1
        text = str(form.get("text") or "").strip()
        if not text:
            raise ValueError("Укажите текст рекламы.")
        current_photo = str((existing or {}).get("photo") or "").strip()
        photo_path = current_photo
        if saved_photo and photo is not None and photo.filename:
            photo_path = canonical_promo_photo_path(class_name, target_dir.name, photo.filename)
        promotion_payload = {
            "id": item_id,
            "class": class_name,
            "slug": target_dir.name,
            "name": str((existing or {}).get("name") or f"reklama-{item_id}").strip() or f"reklama-{item_id}",
            "lore": "",
            "text": text,
            "link": str(form.get("link") or "").strip(),
            "active": _safe_bool(form.get("active"), True),
            "priority": _safe_int(form.get("priority"), 100),
            "condition": "",
            "reward": "",
            "notify": "",
            "reward_mode": "",
            "limit_per_order": None,
            "limit_per_user_per_day": None,
            "start_at": str(form.get("start_at") or "").strip(),
            "end_at": str(form.get("end_at") or "").strip(),
            "photo_path": photo_path or "",
            "created_by_admin_user_id": admin_user_id if not existing else None,
            "updated_by_admin_user_id": admin_user_id,
        }
        item_id = service._pg_store().upsert_promotion(promotion_payload)
    action_type = "promo_created" if not existing else "promo_updated"
    is_active = _safe_bool(form.get("active"), True)
    if existing and not is_active:
        action_type = "promo_disabled"
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type=action_type,
        entity_type="promo_item",
        entity_id=item_id,
        reason=reason,
        payload={"class": class_name, "folder": target_dir.name, "photo_saved": saved_photo},
    )
    invalidate_menu_cache(service)


def validate_promo_form(service, form: dict):
    promo_payload = {
        "class": "akciya",
        "name": str(form.get("name") or "").strip(),
        "lore": str(form.get("lore") or "").strip(),
        "active": _safe_bool(form.get("active"), True),
        "priority": _safe_int(form.get("priority"), 100),
        "condition": str(form.get("condition") or "").strip(),
        "reward": str(form.get("reward") or "").strip(),
        "notify": str(form.get("notify") or "").strip(),
        "reward_mode": _normalize_reward_mode(
            form.get("reward_mode"),
            require_default=bool(str(form.get("condition") or "").strip() or str(form.get("reward") or "").strip()),
        ),
        "limit_per_order": str(form.get("limit_per_order") or "").strip(),
        "limit_per_user_per_day": str(form.get("limit_per_user_per_day") or "").strip(),
        "start_at": str(form.get("start_at") or "").strip(),
        "end_at": str(form.get("end_at") or "").strip(),
    }
    if not promo_payload["name"]:
        raise ValueError("Укажите название акции.")
    if not promo_payload["lore"]:
        raise ValueError("Укажите описание акции.")
    if promo_payload["condition"] or promo_payload["reward"]:
        try:
            parse_and_validate_promo_source(
                promo_payload,
                menu_items=service.menu_content.load_menu_items_admin(),
            )
        except (PromotionDslError, PromotionValidationError) as exc:
            raise ValueError(f"DSL акции невалиден: {exc}") from exc
    return {
        "name": promo_payload["name"],
        "lore": promo_payload["lore"],
        "condition": promo_payload["condition"],
        "reward": promo_payload["reward"],
        "notify": promo_payload["notify"],
        "reward_mode": promo_payload["reward_mode"],
        "limit_per_order": promo_payload["limit_per_order"],
        "limit_per_user_per_day": promo_payload["limit_per_user_per_day"],
        "start_at": promo_payload["start_at"],
        "end_at": promo_payload["end_at"],
    }


def preview_promo_dsl(service, form: dict):
    payload = validate_promo_form(service, form)
    promo_payload = {
        "class": "akciya",
        "name": payload["name"],
        "active": _safe_bool(form.get("active"), True),
        "priority": _safe_int(form.get("priority"), 100),
        **payload,
    }
    if not promo_payload["condition"] and not promo_payload["reward"]:
        return {
            "ok": True,
            "dsl_text": build_dsl_text_from_promo_item(promo_payload),
            "summary": {
                "name": promo_payload["name"],
                "reward_kind": "",
                "reward_mode": promo_payload["reward_mode"],
                "priority": promo_payload["priority"],
                "notify": promo_payload["notify"] or "",
            },
        }
    definition = parse_and_validate_promo_source(
        promo_payload,
        menu_items=service.menu_content.load_menu_items_admin(),
    )
    return {
        "ok": True,
        "dsl_text": build_dsl_text_from_promo_item(promo_payload),
        "summary": {
            "name": definition.name,
            "reward_kind": definition.reward.kind,
            "reward_mode": definition.reward_mode,
            "priority": definition.priority,
            "notify": definition.notify or "",
        },
    }


def delete_promo_item(service, *, admin_user_id: int, class_name: str, item_id: int, reason: str, promo_items_path):
    if not reason:
        raise ValueError("Укажите причину удаления.")
    items = service.menu_content.load_promo_items(include_inactive=True)
    item = next((entry for entry in items if entry.get("class") == class_name and entry.get("id") == int(item_id)), None)
    if item is None:
        raise ValueError("Промо-элемент не найден.")
    target_dir = None
    if item.get("photo"):
        parts = Path(item["photo"]).parts
        if len(parts) >= 3:
            target_dir = promo_items_path / parts[1] / parts[2]
    if class_name in {"akciya", "reklama"}:
        service._pg_store().delete_promotion(int(item_id))
    else:
        if target_dir is None:
            target_dir = find_promo_dir(service, class_name=class_name, item_id=item_id, promo_items_path=promo_items_path)
        if target_dir is None:
            raise ValueError("Промо-элемент не найден.")
        if target_dir.exists():
            shutil.rmtree(target_dir)
    service.log_admin_action(
        admin_user_id=admin_user_id,
        action_type="promo_deleted",
        entity_type="promo_item",
        entity_id=item_id,
        reason=reason,
        payload={"class": class_name, "folder": target_dir.name if target_dir is not None else ""},
    )
    invalidate_menu_cache(service)


def find_promo_dir(service, *, class_name: str, item_id: int, promo_items_path) -> Path | None:
    promo_class_dir = promo_items_path / class_name
    if not promo_class_dir.exists():
        return None
    normalized_item_id = int(item_id)
    for meta_path in sorted(promo_class_dir.rglob("item.txt")):
        meta = service.menu_content.parse_menu_meta(meta_path)
        if str(meta.get("class") or "").strip() != class_name:
            continue
        if _safe_int(meta.get("id"), 0) != normalized_item_id:
            continue
        return meta_path.parent
    return None


def save_image(target_dir: Path, upload: FileStorage | None):
    if upload is None or not upload.filename:
        return False
    extension = Path(upload.filename).suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        raise ValueError("Поддерживаются только PNG, JPG и WEBP.")
    for child in target_dir.iterdir():
        if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
            child.unlink()
    upload.save(target_dir / f"photo{extension}")
    return True


def invalidate_menu_cache(service):
    if hasattr(service.menu_content, "invalidate_local_cache"):
        service.menu_content.invalidate_local_cache()
    client = service.menu_content.get_redis_client()
    if client is None:
        return
    try:
        client.delete(service.menu_content.menu_cache_key)
    except Exception:
        return
