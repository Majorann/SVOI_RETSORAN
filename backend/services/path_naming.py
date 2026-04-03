import os
import re
from pathlib import Path


_CYRILLIC_TO_ASCII = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

_VALID_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def decode_filesystem_text(value: str) -> str:
    text = str(value or "").strip().strip("/\\")
    if not text:
        return ""
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        raw_bytes = os.fsencode(text)
        for encoding in ("utf-8", "cp1251", "cp866", "latin-1"):
            try:
                decoded = raw_bytes.decode(encoding)
                decoded.encode("utf-8")
                return decoded
            except (UnicodeDecodeError, UnicodeEncodeError):
                continue
        return raw_bytes.decode("utf-8", errors="ignore")


def ascii_slug(value: str, *, default: str = "item") -> str:
    text = decode_filesystem_text(value).lower()
    if not text:
        return default

    chunks = []
    for char in text:
        if char in _CYRILLIC_TO_ASCII:
            chunks.append(_CYRILLIC_TO_ASCII[char])
            continue
        if char.isascii() and char.isalnum():
            chunks.append(char)
            continue
        if char in {" ", "-", "_", "/", "\\"}:
            chunks.append("-")
            continue
        chunks.append("-")

    slug = "".join(chunks)
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or default


def image_extension(*values: str, default: str = "") -> str:
    for value in values:
        suffix = Path(str(value or "")).suffix.lower()
        if suffix in _VALID_IMAGE_EXTENSIONS:
            return suffix
    return default


def canonical_menu_photo_path(slug: str, *values: str) -> str:
    normalized_slug = ascii_slug(slug, default="item")
    extension = image_extension(*values)
    if not extension:
        return ""
    return f"menu_items/{normalized_slug}/photo{extension}"


def canonical_promo_photo_path(class_name: str, slug: str, *values: str) -> str:
    normalized_class = ascii_slug(class_name, default="promo")
    normalized_slug = ascii_slug(slug, default="item")
    extension = image_extension(*values)
    if not extension:
        return ""
    return f"promo_items/{normalized_class}/{normalized_slug}/photo{extension}"
