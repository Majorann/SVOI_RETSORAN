import json
import os
import re
import threading
from pathlib import Path

from config import MENU_ITEMS_PATH, MENU_META_NAME, MENU_PHOTO_NAMES, PROMO_ITEMS_PATH, PROMO_META_NAME, PROMO_PHOTO_NAMES
from models import MenuItem, PromoItem


class MenuContentService:
    def __init__(
        self,
        *,
        menu_cache_enabled: bool,
        menu_cache_key: str,
        menu_cache_ttl_seconds: int,
        redis_module,
        redis_url: str,
    ):
        self.menu_cache_enabled = menu_cache_enabled
        self.menu_cache_key = menu_cache_key
        self.menu_cache_ttl_seconds = menu_cache_ttl_seconds
        self.redis_module = redis_module
        self.redis_url = redis_url
        self._redis_client = None
        self._redis_client_lock = threading.Lock()

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
        raw_text = self.read_text_with_fallback(meta_path, ("utf-8", "utf-8-sig", "cp1251"))
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
        client = self.get_redis_client()
        if client is not None:
            try:
                cached_payload = client.get(self.menu_cache_key)
                if cached_payload:
                    items = json.loads(cached_payload)
                    if isinstance(items, list):
                        return items
            except Exception as exc:
                print(f"[cache] redis menu read failed ({exc}), fallback=disk")

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
        return items

    def load_menu_items_admin(self):
        return self.load_menu_items_from_disk(include_inactive=True)

    def load_promo_items(self, include_inactive: bool = False):
        items = []
        if not PROMO_ITEMS_PATH.exists():
            return items

        meta_paths = sorted(PROMO_ITEMS_PATH.rglob(PROMO_META_NAME))
        for meta_path in meta_paths:
            item_dir = meta_path.parent
            relative_slug = item_dir.relative_to(PROMO_ITEMS_PATH).as_posix()
            photo_name = self.resolve_photo_name(item_dir, PROMO_PHOTO_NAMES)

            meta = self.parse_menu_meta(meta_path)
            promo_item = self.parse_promo_item(meta, relative_slug, photo_name)
            if promo_item is None:
                continue
            if not include_inactive and not promo_item.get("active", True):
                continue
            items.append(promo_item)

        items.sort(key=lambda item: (item.get("priority", 100), item["id"]))
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
        raw_text = self.read_text_with_fallback(meta_path, ("utf-8", "utf-8-sig", "cp1251"))
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            normalized_key = key.strip().lower().lstrip("\ufeff")
            data[normalized_key] = value.strip()
        return data

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
                return photo_name
        for extension in ("*.webp", "*.png", "*.jpg", "*.jpeg"):
            candidates = sorted(item_dir.glob(extension))
            if candidates:
                return candidates[0].name
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
        item = MenuItem(
            id=item_id,
            name=name,
            lore=lore,
            type=dish_type,
            price=price,
            photo=f"menu_items/{slug}/{photo_name}",
            portion_label=portion_label,
            portion_tone_rgb=portion_tone_rgb,
            popularity=popularity,
            featured=featured,
            active=active,
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
        photo = f"promo_items/{slug}/{photo_name}" if photo_name else None

        if item_class == "reklama":
            text = (meta.get("text", "") or "").strip()
            link = (meta.get("link", "") or "").strip()
            if not text:
                return None
            item = PromoItem(
                id=item_id,
                class_name=item_class,
                priority=priority,
                active=active,
                photo=photo,
                text=text,
                link=link,
            )
            return item.to_dict()

        name = (meta.get("name", "") or "").strip()
        lore = (meta.get("lore", "") or "").strip()
        if not name or not lore:
            return None
        item = PromoItem(
            id=item_id,
            class_name=item_class,
            priority=priority,
            active=active,
            photo=photo,
            name=name,
            lore=lore,
        )
        return item.to_dict()

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
