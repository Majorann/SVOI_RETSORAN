from urllib.parse import urlsplit


def normalize_public_link(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any(ch in text for ch in {"\r", "\n", "\x00"}):
        return ""

    if text.startswith("/"):
        return text if not text.startswith("//") else ""

    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"}:
        return ""
    if not parts.netloc:
        return ""
    return text
