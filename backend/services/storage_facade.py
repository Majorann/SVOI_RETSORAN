import importlib
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

    def _pg_method(self, name: str):
        if self.active_storage != "postgres":
            return None
        try:
            pg_store = importlib.import_module("storage.pg_store")
        except Exception:
            return None
        method = getattr(pg_store, name, None)
        return method if callable(method) else None

    def _phone_digits(self, value):
        return "".join(ch for ch in str(value or "") if ch.isdigit())

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

    def filter_orders_by_retention(self, orders):
        if self.order_retention_days <= 0:
            return [order for order in orders if isinstance(order, dict)]

        now_dt = self.current_time_fn()
        retention_delta = timedelta(days=self.order_retention_days)
        cleaned = []

        for order in orders:
            if not isinstance(order, dict):
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

        return cleaned

    def load_users(self):
        return self.store_load_users(self.users_path)

    def get_user_by_id(self, user_id):
        normalized_user_id = int(user_id)
        pg_method = self._pg_method("get_user_by_id")
        if pg_method is not None:
            return pg_method(normalized_user_id)
        return next((user for user in self.load_users() if user.get("id") == normalized_user_id), None)

    def get_user_by_phone(self, phone):
        normalized_digits = self._phone_digits(phone)
        if not normalized_digits:
            return None
        pg_method = self._pg_method("get_user_by_phone")
        if pg_method is not None:
            return pg_method(str(phone or ""))
        for user in self.load_users():
            if self._phone_digits(user.get("phone")) == normalized_digits:
                return user
        return None

    def list_user_bookings(self, user_id, *, include_expired: bool = False):
        normalized_user_id = int(user_id)
        pg_method = self._pg_method("list_user_bookings")
        if pg_method is not None:
            return pg_method(
                normalized_user_id,
                include_expired=include_expired,
                booking_duration_minutes=self.booking_duration_minutes,
            )
        bookings = self.load_bookings_raw() if include_expired else self.load_bookings()
        filtered = [booking for booking in bookings if booking.get("user_id") == normalized_user_id]
        filtered.sort(
            key=lambda booking: (
                booking.get("date", ""),
                booking.get("time", ""),
                booking.get("created_at", ""),
            ),
            reverse=True,
        )
        return filtered

    def get_latest_user_booking(self, user_id):
        bookings = self.list_user_bookings(user_id, include_expired=True)
        return bookings[0] if bookings else None

    def list_user_orders(self, user_id):
        normalized_user_id = int(user_id)
        refresh_method = self._pg_method("refresh_persisted_order_fields")
        if refresh_method is not None:
            refresh_method(user_id=normalized_user_id, active_only=True)
        pg_method = self._pg_method("list_user_orders")
        if pg_method is not None:
            orders = pg_method(normalized_user_id)
            return self.filter_orders_by_retention(orders)
        orders = [order for order in self.load_orders() if order.get("user_id") == normalized_user_id]
        orders.sort(key=lambda order: (order.get("created_at", ""), order.get("id", 0)), reverse=True)
        return orders

    def get_user_order(self, user_id, order_id):
        normalized_user_id = int(user_id)
        normalized_order_id = int(order_id)
        refresh_method = self._pg_method("refresh_persisted_order_fields")
        if refresh_method is not None:
            refresh_method(order_ids=[normalized_order_id])
        pg_method = self._pg_method("get_user_order")
        if pg_method is not None:
            return pg_method(normalized_user_id, normalized_order_id)
        return next(
            (
                order
                for order in self.list_user_orders(normalized_user_id)
                if order.get("id") == normalized_order_id
            ),
            None,
        )

    def create_user(self, *, name, phone, password_hash, created_at):
        pg_method = self._pg_method("create_user")
        if pg_method is not None:
            return pg_method(
                {
                    "name": str(name or "").strip(),
                    "phone": str(phone or "").strip(),
                    "password_hash": str(password_hash or ""),
                    "created_at": str(created_at or ""),
                    "balance": 0,
                    "cards": [],
                }
            )
        with self.storage_write_lock(self.users_path):
            users = self.load_users()
            user = {
                "id": self.next_user_id(users),
                "name": str(name or "").strip(),
                "phone": str(phone or "").strip(),
                "password_hash": str(password_hash or ""),
                "balance": 0,
                "cards": [],
                "created_at": str(created_at or ""),
            }
            users.append(user)
            self.save_users(users)
            return dict(user)

    def update_user_password_hash(self, user_id, password_hash):
        normalized_user_id = int(user_id)
        pg_method = self._pg_method("update_user_password_hash")
        if pg_method is not None:
            return pg_method(normalized_user_id, str(password_hash or ""))
        with self.storage_write_lock(self.users_path):
            users = self.load_users()
            user = next((entry for entry in users if entry.get("id") == normalized_user_id), None)
            if user is None:
                return None
            user["password_hash"] = str(password_hash or "")
            self.save_users(users)
            return dict(user)

    def add_user_card(self, user_id, card: dict):
        normalized_user_id = int(user_id)
        pg_method = self._pg_method("add_user_card")
        if pg_method is not None:
            return pg_method(normalized_user_id, dict(card or {}))
        with self.storage_write_lock(self.users_path):
            users = self.load_users()
            user = next((entry for entry in users if entry.get("id") == normalized_user_id), None)
            if user is None:
                return None
            cards = list(user.get("cards") or [])
            for existing_card in cards:
                existing_card["active"] = False
            cards.append(dict(card or {}))
            user["cards"] = cards
            self.save_users(users)
            return dict(user)

    def remove_user_card(self, user_id, *, created_at: str = "", last4: str = ""):
        normalized_user_id = int(user_id)
        pg_method = self._pg_method("remove_user_card")
        if pg_method is not None:
            return pg_method(normalized_user_id, created_at=created_at, last4=last4)
        with self.storage_write_lock(self.users_path):
            users = self.load_users()
            user = next((entry for entry in users if entry.get("id") == normalized_user_id), None)
            if user is None:
                return {"user": None, "removed": False}
            cards = list(user.get("cards") or [])
            removed_index = None
            for idx, card in enumerate(cards):
                if created_at and card.get("created_at") == created_at:
                    removed_index = idx
                    break
            if removed_index is None and last4:
                for idx, card in enumerate(cards):
                    if card.get("last4") == last4:
                        removed_index = idx
                        break
            if removed_index is None:
                return {"user": dict(user), "removed": False}
            removed_card = cards.pop(removed_index)
            if removed_card.get("active") and cards and not any(card.get("active") for card in cards):
                cards[-1]["active"] = True
            user["cards"] = cards
            self.save_users(users)
            return {"user": dict(user), "removed": True}

    def list_reserved_table_ids(self, date_str, time_str):
        pg_method = self._pg_method("list_reserved_table_ids")
        if pg_method is not None:
            return pg_method(date_str, time_str, booking_duration_minutes=self.booking_duration_minutes)
        selected_dt = self.parse_datetime_fn(date_str, time_str)
        if selected_dt is None:
            return []
        return [
            booking.get("table_id")
            for booking in self.load_bookings()
            if booking.get("table_id") is not None and self._booking_overlaps(booking, selected_dt)
        ]

    def _booking_overlaps(self, booking, selected_dt):
        booking_dt = self.parse_datetime_fn(booking.get("date"), booking.get("time"))
        if booking_dt is None or selected_dt is None:
            return False
        booking_end = booking_dt + timedelta(minutes=self.booking_duration_minutes)
        selected_end = selected_dt + timedelta(minutes=self.booking_duration_minutes)
        return booking_dt < selected_end and selected_dt < booking_end

    def create_booking_if_available(self, *, user_id, table_id, date_str, time_str, name, created_at):
        normalized_user_id = int(user_id)
        normalized_table_id = int(table_id)
        pg_method = self._pg_method("create_booking_if_available")
        if pg_method is not None:
            return pg_method(
                {
                    "user_id": normalized_user_id,
                    "table_id": normalized_table_id,
                    "date": str(date_str or ""),
                    "time": str(time_str or ""),
                    "name": str(name or "").strip(),
                    "created_at": str(created_at or ""),
                },
                booking_duration_minutes=self.booking_duration_minutes,
            )
        booking_dt = self.parse_datetime_fn(date_str, time_str)
        if booking_dt is None:
            return False
        with self.storage_write_lock(self.bookings_path):
            bookings = self.load_bookings()
            if any(
                booking.get("table_id") == normalized_table_id and self._booking_overlaps(booking, booking_dt)
                for booking in bookings
            ):
                return False
            bookings.append(
                {
                    "table_id": normalized_table_id,
                    "date": str(date_str or ""),
                    "time": str(time_str or ""),
                    "name": str(name or "").strip(),
                    "user_id": normalized_user_id,
                    "created_at": str(created_at or ""),
                }
            )
            self.save_bookings(bookings)
            return True

    def cancel_user_booking(self, *, user_id, table_id, date_str, time_str):
        normalized_user_id = int(user_id)
        normalized_table_id = int(table_id)
        pg_method = self._pg_method("delete_user_booking")
        if pg_method is not None:
            return pg_method(normalized_user_id, normalized_table_id, str(date_str or ""), str(time_str or ""))
        with self.storage_write_lock(self.bookings_path):
            bookings = self.load_bookings()
            remaining = []
            removed = False
            for booking in bookings:
                if (
                    not removed
                    and booking.get("user_id") == normalized_user_id
                    and booking.get("table_id") == normalized_table_id
                    and booking.get("date") == date_str
                    and booking.get("time") == time_str
                ):
                    removed = True
                    continue
                remaining.append(booking)
            if removed:
                self.save_bookings(remaining)
            return removed

    def cancel_booking_with_orders(self, *, user_id, table_id, date_str, time_str, cancelled_at):
        normalized_user_id = int(user_id)
        normalized_table_id = int(table_id)
        pg_method = self._pg_method("cancel_booking_with_orders")
        if pg_method is not None:
            return pg_method(
                normalized_user_id,
                normalized_table_id,
                str(date_str or ""),
                str(time_str or ""),
                str(cancelled_at or ""),
            )
        booking_removed = self.cancel_user_booking(
            user_id=normalized_user_id,
            table_id=normalized_table_id,
            date_str=date_str,
            time_str=time_str,
        )
        if not booking_removed:
            return False
        with self.storage_write_lock(self.orders_path):
            orders = self.load_orders()
            changed = False
            for order in orders:
                if order.get("user_id") != normalized_user_id:
                    continue
                if str(order.get("order_type") or "").strip().lower() == "delivery":
                    continue
                status_value = str(order.get("status") or "").strip().lower()
                if status_value in {"cancelled", "canceled"}:
                    continue
                booking = order.get("booking") or {}
                if (
                    booking.get("table_id") == normalized_table_id
                    and booking.get("date") == date_str
                    and booking.get("time") == time_str
                ):
                    order["status"] = "cancelled"
                    order["cancelled_at"] = str(cancelled_at or "")
                    changed = True
            if changed:
                self.save_orders(orders)
        return True

    def create_order(self, order: dict):
        pg_method = self._pg_method("create_order")
        if pg_method is not None:
            return pg_method(dict(order or {}))
        with self.storage_write_lock(self.orders_path):
            orders = self.load_orders()
            new_order = dict(order or {})
            new_order["id"] = self.next_order_id(orders)
            orders.append(new_order)
            self.save_orders(orders)
            return dict(new_order)

    def apply_user_balance_delta(self, user_id, delta):
        normalized_user_id = int(user_id)
        normalized_delta = int(delta)
        pg_method = self._pg_method("apply_user_balance_delta")
        if pg_method is not None:
            return pg_method(normalized_user_id, normalized_delta)
        with self.storage_write_lock(self.users_path):
            users = self.load_users()
            user = next((entry for entry in users if entry.get("id") == normalized_user_id), None)
            if user is None:
                return None
            user["balance"] = max(0, int(user.get("balance", 0) or 0) + normalized_delta)
            self.save_users(users)
            return dict(user)

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
