import os
import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path


class StorageFacade:
    def __init__(
        self,
        *,
        active_storage: str,
        bookings_path: Path,
        booking_duration_minutes: int,
        orders_path: Path,
        users_path: Path,
        order_retention_days: int,
        order_prune_interval_seconds: int,
        parse_datetime_fn,
        current_time_fn,
        parse_iso_datetime_fn,
        build_order_status_timeline_fn,
        store_load_bookings,
        store_load_bookings_raw,
        store_load_orders,
        store_load_users,
        store_next_order_id,
        store_next_user_id,
        store_save_bookings,
        store_save_orders,
        store_save_users,
    ):
        self.active_storage = active_storage
        self.bookings_path = bookings_path
        self.booking_duration_minutes = booking_duration_minutes
        self.orders_path = orders_path
        self.users_path = users_path
        self.order_retention_days = order_retention_days
        self.order_prune_interval_seconds = order_prune_interval_seconds
        self.parse_datetime_fn = parse_datetime_fn
        self.current_time_fn = current_time_fn
        self.parse_iso_datetime_fn = parse_iso_datetime_fn
        self.build_order_status_timeline_fn = build_order_status_timeline_fn
        self.store_load_bookings = store_load_bookings
        self.store_load_bookings_raw = store_load_bookings_raw
        self.store_load_orders = store_load_orders
        self.store_load_users = store_load_users
        self.store_next_order_id = store_next_order_id
        self.store_next_user_id = store_next_user_id
        self.store_save_bookings = store_save_bookings
        self.store_save_orders = store_save_orders
        self.store_save_users = store_save_users
        self._process_locks = {}
        self._process_locks_guard = threading.RLock()
        self._order_prune_lock = threading.RLock()
        self._last_order_prune_at = 0.0

    def load_bookings(self):
        return self.store_load_bookings(
            self.bookings_path,
            self.parse_datetime_fn,
            self.booking_duration_minutes,
        )

    def load_bookings_raw(self):
        return self.store_load_bookings_raw(self.bookings_path)

    def save_bookings(self, bookings):
        self.store_save_bookings(self.bookings_path, bookings)

    def load_orders(self):
        orders = self.store_load_orders(self.orders_path)
        return self.prune_orders(orders)

    def save_orders(self, orders):
        self.store_save_orders(self.orders_path, orders)

    def prune_orders(self, orders):
        if self.order_retention_days <= 0:
            return orders

        now_monotonic = time.monotonic()
        with self._order_prune_lock:
            if now_monotonic - self._last_order_prune_at < self.order_prune_interval_seconds:
                return orders
            self._last_order_prune_at = now_monotonic

        now_dt = self.current_time_fn()
        retention_delta = timedelta(days=self.order_retention_days)
        cleaned = []
        changed = False

        for order in orders:
            if not isinstance(order, dict):
                changed = True
                continue

            created_at = self.parse_iso_datetime_fn(order.get("created_at"))
            if created_at is None:
                cleaned.append(order)
                continue

            timeline = self.build_order_status_timeline_fn(order, now_dt)
            is_active = timeline is not None
            is_fresh = (now_dt - created_at) <= retention_delta

            if is_active or is_fresh:
                cleaned.append(order)
                continue
            changed = True

        if changed:
            try:
                self.store_save_orders(self.orders_path, cleaned)
            except Exception:
                return orders
            return cleaned
        return orders

    def load_users(self):
        return self.store_load_users(self.users_path)

    def save_users(self, users):
        self.store_save_users(self.users_path, users)

    def next_user_id(self, users):
        return self.store_next_user_id(users)

    def next_order_id(self, orders):
        return self.store_next_order_id(orders)

    @contextmanager
    def json_file_lock(self, path: Path, timeout_seconds: float = 5.0, poll_interval: float = 0.05):
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_key = str(path.resolve())
        with self._process_locks_guard:
            process_lock = self._process_locks.setdefault(lock_key, threading.RLock())

        with process_lock:
            started_at = time.monotonic()
            lock_fd = None
            while True:
                try:
                    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(lock_fd, f"{os.getpid()}:{threading.get_ident()}".encode("utf-8"))
                    os.close(lock_fd)
                    lock_fd = None
                    break
                except FileExistsError:
                    if time.monotonic() - started_at >= timeout_seconds:
                        raise TimeoutError(f"Timeout while waiting lock for {path.name}")
                    time.sleep(poll_interval)

            try:
                yield
            finally:
                if lock_fd is not None:
                    os.close(lock_fd)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass

    @contextmanager
    def storage_write_lock(self, path: Path, timeout_seconds: float = 5.0, poll_interval: float = 0.05):
        if self.active_storage == "json":
            with self.json_file_lock(
                path,
                timeout_seconds=timeout_seconds,
                poll_interval=poll_interval,
            ):
                yield
            return
        yield
