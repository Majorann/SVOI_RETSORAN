import os
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _resolve_data_dir() -> Path:
    # Priority: explicit env -> HF persistent volume -> local backend dir.
    raw = (os.getenv("APP_DATA_DIR") or os.getenv("DATA_DIR") or "").strip()
    if raw:
        target = Path(raw)
    elif Path("/data").exists():
        target = Path("/data")
    else:
        target = BASE_DIR
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except OSError:
        fallback = BASE_DIR
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _ensure_seed_file(data_dir: Path, filename: str) -> Path:
    dst = data_dir / filename
    if dst.exists():
        return dst
    src = BASE_DIR / filename
    try:
        if src.exists():
            shutil.copy2(src, dst)
        else:
            dst.write_text("[]", encoding="utf-8")
        return dst
    except OSError:
        # Final safety: always keep app bootable even if data dir isn't writable.
        fallback = BASE_DIR / filename
        if not fallback.exists():
            fallback.write_text("[]", encoding="utf-8")
        return fallback


DATA_DIR = _resolve_data_dir()
BOOKINGS_PATH = _ensure_seed_file(DATA_DIR, "bookings.json")
USERS_PATH = _ensure_seed_file(DATA_DIR, "users.json")
ORDERS_PATH = _ensure_seed_file(DATA_DIR, "orders.json")
MENU_ITEMS_PATH = BASE_DIR / "static" / "menu_items"
PROMO_ITEMS_PATH = BASE_DIR / "static" / "promo_items"

BOOKING_DURATION_MINUTES = 60

NEWS_CARDS = []
POPULAR_MENU_LIMIT = 10

MENU_PHOTO_NAMES = ("photo.png", "photo.webp")
MENU_META_NAME = "item.txt"
PROMO_PHOTO_NAMES = ("photo.png", "photo.webp")
PROMO_META_NAME = "item.txt"

ORDER_STATUS_STEPS = (
    {"key": "preparing", "duration_seconds": 15 * 60},
    {"key": "delivering", "duration_seconds": 60},
    {"key": "served", "duration_seconds": 60},
)

TABLES = [
    {
        "id": 1,
        "label": "Стол 1",
        "seats": 5,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 12,
        "shape": "rect",
        "chairs": {"top": "Sofa", "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 2,
        "label": "Стол 2",
        "seats": 4,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 32,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 3,
        "label": "Стол 3",
        "seats": 4,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 4,
        "label": "Стол 4",
        "seats": 2,
        "window": False,
        "status": "free",
        "x": 36,
        "y": 32,
        "shape": "square",
        "chairs": {"top": 1, "bottom": 1, "left": 0, "right": 0},
    },
    {
        "id": 5,
        "label": "Стол 5",
        "seats": 2,
        "window": False,
        "status": "free",
        "x": 50,
        "y": 32,
        "shape": "square",
        "chairs": {"top": 1, "bottom": 1, "left": 0, "right": 0},
    },
    {
        "id": 6,
        "label": "Стол 6",
        "seats": 3,
        "window": False,
        "status": "free",
        "x": 90,
        "y": 28,
        "shape": "square",
        "chairs": {"top": 1, "bottom": 0, "left": 1, "right": 1},
    },
    {
        "id": 7,
        "label": "Стол 7",
        "seats": 5,
        "window": False,
        "status": "free",
        "x": 60,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 1, "right": 0},
    },
    {
        "id": 8,
        "label": "Стол 8",
        "seats": 4,
        "window": False,
        "status": "free",
        "x": 90,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": 2, "left": 0, "right": 0},
    },
    {
        "id": 9,
        "label": "Стол 9",
        "seats": 8,
        "window": False,
        "status": "free",
        "x": 36,
        "y": 69,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": "Sofa", "left": 0, "right": "Sofa"},
    },
    {
        "id": 10,
        "label": "Стол 10",
        "seats": 15,
        "window": False,
        "status": "free",
        "x": 80,
        "y": 89,
        "shape": "long",
        "chairs": {"top": 5, "bottom": "Sofa", "left": 1, "right": "Sofa"},
    },
    {
        "id": 11,
        "label": "Стол 11",
        "seats": 5,
        "window": True,
        "status": "free",
        "x": 12,
        "y": 89,
        "shape": "rect",
        "chairs": {"top": 2, "bottom": "Sofa", "left": 0, "right": 0},
    },
    {
        "id": 12,
        "label": "Стол 12",
        "seats": 9,
        "window": False,
        "status": "free",
        "x": 36,
        "y": 89,
        "shape": "rect",
        "chairs": {"top": "Sofa", "bottom": "Sofa", "left": 0, "right": "Sofa"},
    },
    {
        "id": 13,
        "label": "Стол 13",
        "seats": 6,
        "window": False,
        "status": "free",
        "x": 80,
        "y": 46,
        "shape": "long",
        "chairs": {"top": "Sofa", "bottom": "Sofa", "left": 1, "right": 1},
    },
]

WALLS = [
    {"class": "wall--wc-left"},
    {"class": "wall--wc-top"},
    {"class": "wall--left-upper"},
    {"class": "wall--left-lower"},
    {"class": "wall--mid-l"},
    {"class": "wall--mid-down"},
]
