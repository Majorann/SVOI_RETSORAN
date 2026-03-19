import hashlib
import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password, method: str):
    return generate_password_hash(password, method=method)


def hash_password_legacy(password):
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def is_legacy_password_hash(password_hash):
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(password_hash or "")))


def verify_password(password, password_hash):
    stored_hash = str(password_hash or "")
    if not stored_hash:
        return False, False
    if is_legacy_password_hash(stored_hash):
        return secrets.compare_digest(stored_hash, hash_password_legacy(password)), True
    try:
        return check_password_hash(stored_hash, password), False
    except (TypeError, ValueError):
        return False, False


def verify_and_upgrade_password(user, password, method: str):
    if not isinstance(user, dict):
        return False, False
    matches, needs_upgrade = verify_password(password, user.get("password_hash"))
    if not matches:
        return False, False
    if needs_upgrade:
        user["password_hash"] = hash_password(password, method)
        return True, True
    return True, False
