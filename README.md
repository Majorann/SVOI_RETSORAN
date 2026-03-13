# SVOI_RETSORAN

Учебный веб-проект ресторана на Flask с модульной архитектурой, корзиной, бронированием столов, заказами в зале и доставкой.

## Стек

- Python 3.12
- Flask
- Gunicorn
- JSON storage и/или Neon Postgres
- HTML/CSS/JS (ES modules)

## Структура

- `backend/app.py` - точка входа Flask, роуты, конфиг сессий.
- `backend/routes/` - HTTP-роуты по модулям.
- `backend/services/` - бизнес-логика.
- `backend/storage/json_store.py` - файловое хранилище JSON.
- `backend/storage/pg_store.py` - хранилище в Postgres (Neon).
- `backend/sql/neon_init.sql` - SQL-инициализация схемы Neon.
- `backend/ops/migrate_json_to_neon.py` - миграция JSON -> Neon.

## Локальный запуск

1. Установить зависимости:

```bash
pip install -r backend/requirements.txt
```

2. Запустить:

```bash
cd backend
python app.py
```

Или через gunicorn:

```bash
gunicorn app:app --bind 0.0.0.0:7860
```

## Переменные окружения

Минимально:

- `FLASK_SECRET_KEY` - секрет Flask-сессий.

Для Postgres (Neon):

- `DATABASE_URL` - строка подключения Postgres.

Рекомендуется для продакшена (HF Space/iframe):

- `SESSION_COOKIE_SAMESITE=None`
- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_PARTITIONED=true`
- `TRUST_PROXY_HEADERS=true`
- `APP_TIMEZONE=Europe/Kaliningrad`

Дополнительно:

- `APP_DATA_DIR` или `DATA_DIR` - каталог для JSON-файлов (`users.json`, `bookings.json`, `orders.json`).
- `ORDER_RETENTION_DAYS` - срок хранения неактивных заказов (по умолчанию `7`).
- `ORDER_PRUNE_INTERVAL_SECONDS` - интервал автоочистки заказов (по умолчанию `60`).

## Режимы хранения данных

### 1) JSON (по умолчанию)

Если `DATABASE_URL` не задан, используются файлы:

- `users.json`
- `bookings.json`
- `orders.json`

### 2) Postgres (Neon)

Если задан `DATABASE_URL`, приложение переключается на Postgres backend.

Шаги:

1. Выполнить SQL:

```sql
-- файл: backend/sql/neon_init.sql
```

2. (Опционально) Мигрировать текущие JSON-данные:

```bash
python backend/ops/migrate_json_to_neon.py
```

## Диагностика

Эндпоинт:

- `GET /debug/storage`

Показывает активный backend (`json` или `postgres`), пути хранилищ и количество записей.

## Важно

- `POST /release` сейчас заглушка и возвращает `501 Not Implemented`.
- В учебной версии пароли хешируются SHA-256 (без соли), для продакшена нужен более сильный механизм (например, `bcrypt`/`argon2`).
