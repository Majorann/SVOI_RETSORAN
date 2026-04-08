import json
import os
import threading
import time
from pathlib import Path


class OneTimeTokenStore:
    def __init__(self, path: Path, *, ttl_seconds: int = 24 * 60 * 60):
        self.path = Path(path)
        self.ttl_seconds = max(300, int(ttl_seconds))
        self._thread_lock = threading.RLock()

    def _load_entries(self) -> dict[str, float]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        entries = payload.get("used_tokens")
        if not isinstance(entries, dict):
            return {}
        normalized = {}
        for token_id, used_at in entries.items():
            try:
                normalized[str(token_id)] = float(used_at)
            except (TypeError, ValueError):
                continue
        return normalized

    def _save_entries(self, entries: dict[str, float]):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"used_tokens": entries}, ensure_ascii=False, indent=2)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, self.path)

    def _lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def _cleanup_entries(self, entries: dict[str, float], now_monotonic: float) -> dict[str, float]:
        threshold = now_monotonic - self.ttl_seconds
        return {
            token_id: used_at
            for token_id, used_at in entries.items()
            if used_at >= threshold
        }

    def consume(self, token_id: str) -> bool:
        normalized_token_id = str(token_id or "").strip()
        if not normalized_token_id:
            return False

        lock_path = self._lock_path()
        started_at = time.monotonic()
        lock_fd = None

        with self._thread_lock:
            while True:
                try:
                    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(lock_fd, f"{os.getpid()}:{threading.get_ident()}".encode("utf-8"))
                    os.close(lock_fd)
                    lock_fd = None
                    break
                except FileExistsError:
                    if time.monotonic() - started_at >= 5.0:
                        return False
                    time.sleep(0.05)

            try:
                now_monotonic = time.monotonic()
                entries = self._cleanup_entries(self._load_entries(), now_monotonic)
                if normalized_token_id in entries:
                    self._save_entries(entries)
                    return False
                entries[normalized_token_id] = now_monotonic
                self._save_entries(entries)
                return True
            finally:
                if lock_fd is not None:
                    os.close(lock_fd)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
