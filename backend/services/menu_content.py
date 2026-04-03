import json
import importlib
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path, PurePosixPath

from config import MENU_ITEMS_PATH, MENU_META_NAME, MENU_PHOTO_NAMES, PROMO_ITEMS_PATH, PROMO_META_NAME, PROMO_PHOTO_NAMES
from models import MenuItem, PromoItem
from services.business_logic import current_local_datetime_value
from services.promotions import parse_and_validate_promo_source
from services.promotions.ast import PromotionDslError
from services.promotions.validator import PromotionValidationError


class MenuContentService:
    def __init__(
        self,
        *,
        active_storage: str = "json",
        menu_cache_enabled: bool,
        menu_cache_key: str,
        menu_cache_ttl_seconds: int,
        redis_module,
        redis_url: str,
    ):
        self.active_storage = active_storage
        self.menu_cache_enabled = menu_cache_enabled
        self.menu_cache_key = menu_cache_key
        self.menu_cache_ttl_seconds = menu_cache_ttl_seconds
        self.redis_module = redis_module
        self.redis_url = redis_url
        self._redis_client = None
        self._redis_client_lock = threading.Lock()
        self._memory_cache = {}
        self._memory_cache_lock = threading.Lock()
        self._disk_menu_photo_cache = None
        self._disk_menu_photo_cache_lock = threading.Lock()
        self._disk_promo_photo_cache = None
        self._disk_promo_photo_cache_lock = threading.Lock()

    def _memory_cache_get(self, key: str):
        now = time.monotonic()
        with self._memory_cache_lock:
            entry = self._memory_cache.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at <= now:
                self._memory_cache.pop(key, None)
                return None
            return value

    def _memory_cache_set(self, key: str, value):
        ttl = max(1, int(self.menu_cache_ttl_seconds or 0))
        with self._memory_cache_lock:
            self._memory_cache[key] = (time.monotonic() + ttl, value)
        return value

    def invalidate_local_cache(self, *keys: str):
        with self._memory_cache_lock:
            if not keys:
                self._memory_cache.clear()
            else:
                for key in keys:
                    self._memory_cache.pop(key, None)
        with self._disk_menu_photo_cache_lock:
            self._disk_menu_photo_cache = None
        with self._disk_promo_photo_cache_lock:
            self._disk_promo_photo_cache = None

    def _build_disk_menu_photo_cache(self):
        cache = {}
        if not MENU_ITEMS_PATH.exists():
            return cache

        for item_dir in sorted(MENU_ITEMS_PATH.iterdir()):
            if not item_dir.is_dir():
                continue
            meta_path = item_dir / MENU_META_NAME
            photo_name = self.resolve_photo_name(item_dir, MENU_PHOTO_NAMES)
            if not meta_path.exists() or not photo_name:
                continue
            try:
                meta = self.parse_menu_meta(meta_path)
                item_id = int(meta.get("id", 0))
            except (TypeError, ValueError):
                continue
            if item_id <= 0:
                continue
            cache[item_id] = f"menu_items/{item_dir.name}/{photo_name}"

        return cache

    def _get_disk_menu_photo_cache(self):
        with self._disk_menu_photo_cache_lock:
            if self._disk_menu_photo_cache is None:
                self._disk_menu_photo_cache = self._build_disk_menu_photo_cache()
            return self._disk_menu_photo_cache

    def _build_disk_promo_photo_cache(self):
        cache = {}
        if not PROMO_ITEMS_PATH.exists():
            return cache

        for meta_path in sorted(PROMO_ITEMS_PATH.rglob(PROMO_META_NAME)):
            item_dir = meta_path.parent
            photo_name = self.resolve_photo_name(item_dir, PROMO_PHOTO_NAMES)
            if not photo_name:
                continue
            try:
                meta = self.parse_menu_meta(meta_path)
                item_id = int(meta.get("id", 0))
            except (TypeError, ValueError):
                continue
            if item_id <= 0:
                continue
            try:
                relative_slug = item_dir.relative_to(PROMO_ITEMS_PATH).as_posix()
            except ValueError:
                relative_slug = item_dir.name
            cache[item_id] = self.normalize_static_path(f"promo_items/{relative_slug}/{photo_name}")

        return cache

    def _get_disk_promo_photo_cache(self):
        with self._disk_promo_photo_cache_lock:
            if self._disk_promo_photo_cache is None:
                self._disk_promo_photo_cache = self._build_disk_promo_photo_cache()
            return self._disk_promo_photo_cache

    def _normalize_path_component(self, value: str) -> str:
        text = str(value or "").strip().strip("/\\")
        if not text:
            return ""
        try:
            text.encode("utf-8")
            return text
        except UnicodeEncodeError:
            raw_bytes = os.fsencode(text)
            for encoding in ("utf-8", "cp1251", "latin-1"):
                try:
                    decoded = raw_bytes.decode(encoding)
                    decoded.encode("utf-8")
                    return decoded
                except (UnicodeDecodeError, UnicodeEncodeError):
                    continue
            return raw_bytes.decode("utf-8", errors="ignore")

    def normalize_static_path(self, value: str) -> str:
        text = str(value or "").strip().replace("\\", "/")
        if not text:
            return ""
        parts = []
        for part in PurePosixPath(text).parts:
            if part in {"", ".", "/"}:
                continue
            normalized = self._normalize_path_component(part)
            if normalized:
                parts.append(normalized)
        return "/".join(parts)

    def resolve_menu_photo_path(self, item_id: int, photo_path: str):
        normalized = self.normalize_static_path(photo_path)
        if normalized:
            candidate = MENU_ITEMS_PATH.parent / normalized
            if candidate.exists():
                return normalized

        return self._get_disk_menu_photo_cache().get(item_id, normalized)

    def resolve_promo_photo_path(self, item_id: int, photo_path: str):
        normalized = self.normalize_static_path(photo_path)
        if normalized:
            candidate = PROMO_ITEMS_PATH.parent / normalized
            if candidate.exists():
                return normalized

        return self._get_disk_promo_photo_cache().get(item_id, normalized)

    def get_redis_client(self):
        if not self.menu_cache_enabled or not self.redis_url or self.redis_module is None:
            return None

        with self._redis_client_lock:
            if self._redis_client is not None:
                return self._redis_client
            try:
                client = self.redis_module.Redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                client.ping()
            except Exception as exc:
                print(f"[cache] redis connect failed ({exc}), menu cache disabled")
                return None
            self._redis_client = client
            print(
                "[cache] redis menu cache enabled ttl={0}s key={1}".format(
                    self.menu_cache_ttl_seconds,
                    self.menu_cache_key,
                )
            )
            return self._redis_client

    def _load_pg_store(self):
        try:
            return importlib.import_module("storage.pg_store")
        except Exception as exc:
            raise RuntimeError(f"Postgres content storage import failed: {exc}") from exc

    def verify_storage_readiness(self):
        if self.active_storage != "postgres":
            return
        self.load_menu_items_from_db(include_inactive=True)
        self.load_promotions_from_db(include_inactive=True)

    def load_menu_items_from_disk(self, include_inactive: bool = False):
        items_with_meta = []
        if not MENU_ITEMS_PATH.exists():
            return []

        for item_dir in sorted(MENU_ITEMS_PATH.iterdir()):
            if not item_dir.is_dir():
                continue
            meta_path = item_dir / MENU_META_NAME
            photo_name = self.resolve_photo_name(item_dir, MENU_PHOTO_NAMES)
            if not meta_path.exists() or not photo_name:
                continue

            meta = self.parse_menu_meta(meta_path)
            menu_item = self.parse_menu_item(meta, item_dir.name, photo_name)
            if menu_item is None:
                continue
            if not include_inactive and not menu_item.get("active", True):
                continue
            items_with_meta.append((menu_item, meta_path))

        items = self.ensure_unique_menu_item_ids(items_with_meta)
        items.sort(key=lambda item: item["id"])
        return items

    def update_menu_meta_id(self, meta_path: Path, new_id: int):
        raw_text = self.read_text_utf8(meta_path)
        lines = raw_text.splitlines(keepends=True)
        updated = False

        for index, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue
            key, _value = raw_line.split("=", 1)
            normalized_key = key.strip().lower().lstrip("\ufeff")
            if normalized_key != "id":
                continue
            line_ending = "\n" if raw_line.endswith("\n") else ""
            lines[index] = f"id={int(new_id)}{line_ending}"
            updated = True
            break

        if not updated:
            lines.insert(0, f"id={int(new_id)}\n")

        payload = "".join(lines)
        if payload == raw_text:
            return

        tmp_path = meta_path.with_suffix(meta_path.suffix + ".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, meta_path)

    def ensure_unique_menu_item_ids(self, items_with_meta):
        items = [item for item, _meta_path in items_with_meta]
        used_ids = set()
        max_id = max(
            (
                item_id
                for item, _meta_path in items_with_meta
                for item_id in [item.get("id")]
                if isinstance(item_id, int) and item_id > 0
            ),
            default=0,
        )

        for item, meta_path in items_with_meta:
            item_id = item.get("id")
            if isinstance(item_id, int) and item_id > 0 and item_id not in used_ids:
                used_ids.add(item_id)
                continue

            new_id = max_id + 1
            while new_id in used_ids:
                new_id += 1

            if isinstance(item_id, int) and item_id > 0:
                message = "[menu] duplicate item id detected for '{0}': {1} -> {2}"
            else:
                message = "[menu] invalid item id detected for '{0}': {1} -> {2}"

            print(
                message.format(
                    item.get("name", "unknown"),
                    item_id,
                    new_id,
                )
            )
            item["id"] = new_id
            try:
                self.update_menu_meta_id(meta_path, new_id)
            except OSError as exc:
                print(
                    "[menu] failed to persist item id for '{0}' in {1} ({2})".format(
                        item.get("name", "unknown"),
                        meta_path,
                        exc,
                    )
                )
            used_ids.add(new_id)
            max_id = new_id

        return items

    def load_menu_items(self):
        memory_key = "menu:public"
        memory_items = self._memory_cache_get(memory_key)
        if memory_items is not None:
            return memory_items

        client = self.get_redis_client()
        if client is not None:
            try:
                cached_payload = client.get(self.menu_cache_key)
                if cached_payload:
                    items = json.loads(cached_payload)
                    if isinstance(items, list):
                        return self._memory_cache_set(memory_key, items)
            except Exception as exc:
                print(f"[cache] redis menu read failed ({exc}), fallback=origin")

        if self.active_storage == "postgres":
            items = self.load_menu_items_from_db(include_inactive=False)
        else:
            items = self.load_menu_items_from_disk(include_inactive=False)

        if client is not None:
            try:
                client.setex(
                    self.menu_cache_key,
                    self.menu_cache_ttl_seconds,
                    json.dumps(items, ensure_ascii=False),
                )
            except Exception as exc:
                print(f"[cache] redis menu write failed ({exc})")
        return self._memory_cache_set(memory_key, items)

    def load_menu_items_admin(self):
        memory_key = "menu:admin"
        memory_items = self._memory_cache_get(memory_key)
        if memory_items is not None:
            return memory_items
        if self.active_storage == "postgres":
            items = self.load_menu_items_from_db(include_inactive=True)
        else:
            items = self.load_menu_items_from_disk(include_inactive=True)
        with self._disk_menu_photo_cache_lock:
            self._disk_menu_photo_cache = None
        with self._disk_promo_photo_cache_lock:
            self._disk_promo_photo_cache = None
        return self._memory_cache_set(memory_key, items)

    def load_menu_items_from_db(self, include_inactive: bool = False):
        try:
            pg_store = self._load_pg_store()
            rows = pg_store.load_menu_items(include_inactive=include_inactive)
        except Exception as exc:
            raise RuntimeError(f"Postgres menu read failed: {exc}") from exc

        items = []
        for row in rows:
            menu_item = self.parse_menu_row(row)
            if menu_item is None:
                continue
            if not include_inactive and not menu_item.get("active", True):
                continue
            items.append(menu_item)
        items.sort(key=lambda item: item["id"])
        return items

    def sync_host_content_to_storage(self):
        reklama_items = self._load_disk_promo_items(include_inactive=True, allowed_classes={"reklama"})
        if self.active_storage != "postgres":
            self.invalidate_local_cache()
            return {
                "storage": self.active_storage,
                "menu_items_synced": 0,
                "promotions_synced": 0,
                "reklama_found": len(reklama_items),
            }

        pg_store = importlib.import_module("storage.pg_store")
        menu_result = pg_store.sync_menu_items_from_disk()
        promotion_result = pg_store.sync_promotions_from_disk()
        self.invalidate_local_cache()
        client = self.get_redis_client()
        if client is not None:
            try:
                client.delete(self.menu_cache_key)
            except Exception:
                pass
        return {
            "storage": self.active_storage,
            "menu_items_synced": int((menu_result or {}).get("synced", 0)),
            "menu_items_disabled": int((menu_result or {}).get("disabled", (menu_result or {}).get("deleted", 0))),
            "menu_items_deleted": int((menu_result or {}).get("disabled", (menu_result or {}).get("deleted", 0))),
            "promotions_synced": int((promotion_result or {}).get("synced", 0)),
            "promotions_disabled": int((promotion_result or {}).get("disabled", (promotion_result or {}).get("deleted", 0))),
            "promotions_deleted": int((promotion_result or {}).get("disabled", (promotion_result or {}).get("deleted", 0))),
            "reklama_found": len(reklama_items),
        }

    def load_promo_items(self, include_inactive: bool = False):
        memory_key = "promo:admin" if include_inactive else "promo:public"
        memory_items = self._memory_cache_get(memory_key)
        if memory_items is not None:
            return memory_items

        if self.active_storage == "postgres":
            items = self.load_promotions_from_db(include_inactive=include_inactive)
        else:
            items = []
            items.extend(self._load_disk_promo_items(include_inactive=include_inactive, allowed_classes={"reklama"}))
            items.extend(self._load_disk_promo_items(include_inactive=include_inactive, allowed_classes={"akciya"}))

        items.sort(key=lambda item: (-int(item.get("priority", 100) or 100), int(item["id"])))
        try:
            print(
                "[promo] load include_inactive={0} ids={1}".format(
                    include_inactive,
                    [
                        {
                            "id": item.get("id"),
                            "class": item.get("class"),
                            "name": item.get("name") or item.get("text") or "",
                            "priority": item.get("priority"),
                            "dsl_valid": item.get("dsl_valid"),
                        }
                        for item in items
                    ],
                )
            )
        except Exception:
            pass
        return self._memory_cache_set(memory_key, items)

    def _load_disk_promo_items(self, *, include_inactive: bool, allowed_classes: set[str]):
        items = []
        if not PROMO_ITEMS_PATH.exists():
            return items

        meta_paths = sorted(PROMO_ITEMS_PATH.rglob(PROMO_META_NAME))
        for meta_path in meta_paths:
            item_dir = meta_path.parent
            relative_slug = item_dir.relative_to(PROMO_ITEMS_PATH).as_posix()
            item_class = relative_slug.split("/", 1)[0] if relative_slug else ""
            if item_class not in allowed_classes:
                continue
            photo_name = self.resolve_photo_name(item_dir, PROMO_PHOTO_NAMES)
            meta = self.parse_menu_meta(meta_path)
            promo_item = self.parse_promo_item(meta, relative_slug, photo_name)
            if promo_item is None:
                continue
            if not include_inactive and not promo_item.get("active", True):
                continue
            if not include_inactive and not self.is_promo_in_active_window(promo_item):
                continue
            if not include_inactive and promo_item.get("class") == "akciya" and not promo_item.get("dsl_valid", True):
                continue
            items.append(promo_item)
        return items

    def load_promotions_from_db(self, include_inactive: bool = False):
        try:
            pg_store = self._load_pg_store()
            promotions = pg_store.load_promotions()
        except Exception as exc:
            raise RuntimeError(f"Postgres promotions read failed: {exc}") from exc

        items = []
        for promotion in promotions:
            promo_item = self.parse_promo_row(promotion)
            if promo_item is None:
                continue
            if not include_inactive and not promo_item.get("active", True):
                continue
            if not include_inactive and not self.is_promo_in_active_window(promo_item):
                continue
            if not include_inactive and not promo_item.get("dsl_valid", True):
                continue
            items.append(promo_item)
        return items

    def is_placeholder_promo(self, meta: dict) -> bool:
        item_class = (meta.get("class", "") or "").strip().lower()
        if item_class == "reklama":
            text = (meta.get("text", "") or "").strip()
            link = (meta.get("link", "") or "").strip()
            return text == "Текст рекламного блока." and link == "https://example.com"
        if item_class == "akciya":
            name = (meta.get("name", "") or "").strip()
            lore = (meta.get("lore", "") or "").strip()
            return name == "Название акции" and lore == "Описание акции и условия."
        return False

    def parse_menu_meta(self, meta_path: Path):
        data = {}
        raw_text = self.read_text_utf8(meta_path)
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            normalized_key = key.strip().lower().lstrip("\ufeff")
            data[normalized_key] = value.strip()
        return data

    def read_text_utf8(self, path: Path):
        for encoding in ("utf-8", "utf-8-sig"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")

    def read_text_with_fallback(self, path: Path, encodings):
        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")

    def resolve_photo_name(self, item_dir: Path, photo_names):
        for photo_name in photo_names:
            if (item_dir / photo_name).exists():
                return self._normalize_path_component(photo_name)
        for extension in ("*.webp", "*.png", "*.jpg", "*.jpeg"):
            candidates = sorted(item_dir.glob(extension))
            if candidates:
                return self._normalize_path_component(candidates[0].name)
        return None

    def normalize_portion_label(self, raw_value: str) -> str:
        value = (raw_value or "").strip()
        if not value:
            return ""

        numeric_match = re.fullmatch(r"(\d{2,4})(?:[.,]\d+)?", value)
        if numeric_match:
            return f"{numeric_match.group(1)} г"

        unit_match = re.fullmatch(r"(\d{2,4})(?:[.,]\d+)?\s*(г|гр|g|мл|ml)", value, re.IGNORECASE)
        if unit_match:
            unit = unit_match.group(2).lower()
            normalized_unit = "мл" if unit in {"ml", "мл"} else "г"
            return f"{unit_match.group(1)} {normalized_unit}"

        return value

    def resolve_menu_portion_label(self, meta: dict) -> str:
        for key in ("portion", "weight", "grams", "gram", "volume", "serving", "yield"):
            value = self.normalize_portion_label(meta.get(key, ""))
            if value:
                return value
        return ""

    def extract_portion_amount(self, portion_label: str) -> float | None:
        match = re.search(r"(\d{2,4})(?:[.,]\d+)?", portion_label or "")
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    def build_portion_tone_rgb(self, portion_label: str) -> str:
        amount = self.extract_portion_amount(portion_label)
        if amount is None:
            return "194, 168, 144"

        min_amount = 160.0
        max_amount = 420.0
        t = max(0.0, min(1.0, (amount - min_amount) / (max_amount - min_amount)))

        start = (194, 168, 144)
        end = (214, 112, 74)
        rgb = tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3))
        return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"

    def parse_menu_item(self, meta: dict, slug: str, photo_name: str):
        try:
            price = int(meta.get("price", ""))
        except ValueError:
            return None
        try:
            item_id = int(meta.get("id", ""))
            if item_id <= 0:
                item_id = None
        except ValueError:
            item_id = None
        try:
            popularity = int(meta.get("popularity", meta.get("orders_count", "0")))
        except ValueError:
            popularity = 0

        name = meta.get("name", "")
        lore = meta.get("lore", "")
        dish_type = meta.get("type", "")
        if not all([name, lore, dish_type]):
            return None

        featured_value = meta.get("featured", "false").lower()
        featured = featured_value in {"1", "true", "yes", "y", "on"}
        active_value = meta.get("active", meta.get("available", "true")).lower()
        active = active_value in {"1", "true", "yes", "y", "on"}
        portion_label = self.resolve_menu_portion_label(meta)
        portion_tone_rgb = self.build_portion_tone_rgb(portion_label) if portion_label else ""
        slug = self._normalize_path_component(slug)
        photo_name = self._normalize_path_component(photo_name)
        item = MenuItem(
            id=item_id,
            name=name,
            lore=lore,
            type=dish_type,
            price=price,
            photo=self.normalize_static_path(f"menu_items/{slug}/{photo_name}"),
            portion_label=portion_label,
            portion_tone_rgb=portion_tone_rgb,
            popularity=popularity,
            featured=featured,
            active=active,
        )
        return item.to_dict()

    def parse_menu_row(self, row: dict):
        try:
            item_id = int(row.get("id", 0))
            price = int(row.get("price", 0))
        except (TypeError, ValueError):
            return None
        if item_id <= 0:
            return None

        name = (row.get("name", "") or "").strip()
        lore = (row.get("lore", "") or "").strip()
        dish_type = (row.get("type", "") or "").strip()
        if not all([name, lore, dish_type]):
            return None

        portion_label = self.normalize_portion_label((row.get("portion_label", "") or "").strip())
        portion_tone_rgb = self.build_portion_tone_rgb(portion_label) if portion_label else ""
        item = MenuItem(
            id=item_id,
            name=name,
            lore=lore,
            type=dish_type,
            price=price,
            photo=self.normalize_static_path(
                self.resolve_menu_photo_path(
                item_id,
                (row.get("photo") or row.get("photo_path") or "").strip(),
                )
            ),
            portion_label=portion_label,
            portion_tone_rgb=portion_tone_rgb,
            popularity=int(row.get("popularity", 0) or 0),
            featured=bool(row.get("featured", False)),
            active=bool(row.get("active", True)),
        )
        return item.to_dict()

    def parse_promo_item(self, meta: dict, slug: str, photo_name):
        try:
            item_id = int(meta.get("id", ""))
        except ValueError:
            return None

        item_class = (meta.get("class", "") or "").strip().lower()
        if item_class not in {"reklama", "akciya"}:
            return None
        if self.is_placeholder_promo(meta):
            return None

        try:
            priority = int(meta.get("priority", "100"))
        except ValueError:
            priority = 100

        active_value = (meta.get("active", "true") or "").lower()
        active = active_value in {"1", "true", "yes", "y", "on"}
        slug = self._normalize_path_component(slug)
        photo_name = self._normalize_path_component(photo_name)
        photo = self.normalize_static_path(f"promo_items/{slug}/{photo_name}") if photo_name else None

        if item_class == "reklama":
            text = (meta.get("text", "") or "").strip()
            link = (meta.get("link", "") or "").strip()
            if not text:
                return None
            item = self._build_promo_item(
                id=item_id,
                class_name=item_class,
                priority=priority,
                active=active,
                photo=photo,
                text=text,
                link=link,
                start_at=(meta.get("start_at", "") or "").strip(),
                end_at=(meta.get("end_at", "") or "").strip(),
            )
            return item.to_dict()

        name = (meta.get("name", "") or "").strip()
        lore = (meta.get("lore", "") or "").strip()
        if not name or not lore:
            return None
        item = self._build_promo_item(
            id=item_id,
            class_name=item_class,
            priority=priority,
            active=active,
            photo=photo,
            name=name,
            lore=lore,
            condition=(meta.get("condition", "") or "").strip(),
            reward=(meta.get("reward", "") or "").strip(),
            notify=(meta.get("notify", "") or "").strip(),
            reward_mode=(meta.get("reward_mode", "once") or "once").strip(),
            limit_per_order=(meta.get("limit_per_order", "") or "").strip(),
            limit_per_user_per_day=(meta.get("limit_per_user_per_day", "") or "").strip(),
            start_at=(meta.get("start_at", "") or "").strip(),
            end_at=(meta.get("end_at", "") or "").strip(),
        )
        validation = self.validate_promo_dsl(item.to_dict())
        item.dsl_valid = validation["valid"]
        item.dsl_error = validation["error"]
        if not item.dsl_valid:
            print(
                "[promo] invalid dsl id={0} slug={1} error={2}".format(
                    item_id,
                    slug,
                    item.dsl_error,
                )
            )
        return item.to_dict()

    def parse_promo_row(self, promotion: dict):
        try:
            item_id = int(promotion.get("id", 0))
        except (TypeError, ValueError):
            return None
        if item_id <= 0:
            return None
        class_name = str(promotion.get("class") or promotion.get("class_name") or "akciya").strip().lower()
        priority = int(promotion.get("priority", 100) or 100)
        active = bool(promotion.get("active", True))
        photo = self.normalize_static_path(
            self.resolve_promo_photo_path(
                item_id,
                promotion.get("photo") or promotion.get("photo_path") or "",
            )
        )
        start_at = (promotion.get("start_at", "") or "").strip()
        end_at = (promotion.get("end_at", "") or "").strip()

        if class_name == "reklama":
            text = (promotion.get("text", "") or "").strip()
            link = (promotion.get("link", "") or "").strip()
            if not text:
                return None
            item = self._build_promo_item(
                id=item_id,
                class_name=class_name,
                priority=priority,
                active=active,
                photo=photo,
                text=text,
                link=link,
                start_at=start_at,
                end_at=end_at,
            )
            return item.to_dict()

        name = (promotion.get("name", "") or "").strip()
        lore = (promotion.get("lore", "") or "").strip()
        if not name or not lore:
            return None
        item = self._build_promo_item(
            id=item_id,
            class_name="akciya",
            priority=priority,
            active=active,
            photo=photo,
            name=name,
            lore=lore,
            condition=(promotion.get("condition", "") or "").strip(),
            reward=(promotion.get("reward", "") or "").strip(),
            notify=(promotion.get("notify", "") or "").strip(),
            reward_mode=(promotion.get("reward_mode", "once") or "once").strip(),
            limit_per_order=str(promotion.get("limit_per_order", "") or "").strip(),
            limit_per_user_per_day=str(promotion.get("limit_per_user_per_day", "") or "").strip(),
            start_at=start_at,
            end_at=end_at,
        )
        validation = self.validate_promo_dsl(item.to_dict())
        item.dsl_valid = validation["valid"]
        item.dsl_error = validation["error"]
        return item.to_dict()

    def _build_promo_item(self, **payload):
        try:
            return PromoItem(**payload)
        except TypeError:
            base_kwargs = {
                "id": payload.get("id"),
                "class_name": payload.get("class_name"),
                "priority": payload.get("priority"),
                "active": payload.get("active"),
                "photo": payload.get("photo"),
                "text": payload.get("text", ""),
                "link": payload.get("link", ""),
                "name": payload.get("name", ""),
                "lore": payload.get("lore", ""),
            }
            item = PromoItem(**base_kwargs)
            for key, value in payload.items():
                if key in base_kwargs:
                    continue
                setattr(item, key, value)
            return item

    def validate_promo_dsl(self, promo_item: dict):
        if str(promo_item.get("class") or "").strip().lower() != "akciya":
            return {"valid": True, "error": ""}
        condition = str(promo_item.get("condition") or "").strip()
        reward = str(promo_item.get("reward") or "").strip()
        if not condition and not reward:
            return {"valid": True, "error": ""}
        try:
            parse_and_validate_promo_source(
                promo_item,
                menu_items=self.load_menu_items_admin(),
            )
            return {"valid": True, "error": ""}
        except (PromotionValidationError, PromotionDslError) as exc:
            return {"valid": False, "error": str(exc)}

    def is_promo_in_active_window(self, promo_item: dict, now: datetime | None = None) -> bool:
        current = now or current_local_datetime_value()
        start_at = self.parse_iso_datetime(promo_item.get("start_at"))
        end_at = self.parse_iso_datetime(promo_item.get("end_at"))
        if start_at and current < start_at:
            return False
        if end_at and current > end_at:
            return False
        return True

    def parse_iso_datetime(self, value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def promo_items_to_news_cards(self, items):
        cards = []
        for item in items:
            if item.get("class") == "reklama":
                cards.append(
                    {
                        "title": "Реклама",
                        "text": item.get("text", ""),
                        "accent": "Реклама",
                        "photo": item.get("photo"),
                        "link": item.get("link"),
                    }
                )
                continue
            cards.append(
                {
                    "title": item.get("name", ""),
                    "text": item.get("lore", ""),
                    "accent": "Акция",
                    "photo": item.get("photo"),
                    "link": "",
                }
            )
        return cards[:3]
