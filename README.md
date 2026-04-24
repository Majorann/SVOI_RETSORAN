# SVOI_RETSORAN

Учебный Flask-проект ресторана: публичный сайт, бронирование столов, меню, корзина, заказы, доставка, бонусы и служебная админ-панель.

Проект можно запускать локально на JSON-файлах или на деплое с Postgres. JSON-режим удобен для разработки и демонстрации, Postgres-режим нужен для админки и более полноценного хранения данных.

## Быстрый запуск

Из корня проекта:

```powershell
python run_local.py
```

Скрипт сам создаёт `backend/.venv`, ставит зависимости, читает `backend/.env.local`, генерирует `FLASK_SECRET_KEY`, если его нет, и запускает сайт на `http://127.0.0.1:5000`.

Полезные варианты:

```powershell
python run_local.py --port 8000
python run_local.py --install-deps
python run_local.py --install-only
```

## Ручной запуск

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m waitress --host 127.0.0.1 --port 5000 app:app
```

Для Linux/macOS команды такие же по смыслу, но путь к Python внутри окружения будет `.venv/bin/python`.

## Основные возможности

- публичный сайт ресторана с главной страницей, меню и профилем пользователя;
- бронирование столов со схемой зала;
- оформление заказов и доставки;
- история заказов, уведомления и бонусные баллы;
- промо-система для рекламы и акций;
- админ-панель для заказов, броней, доставки, меню, акций, пользователей, аналитики и audit log;
- два режима хранения: JSON для локальной разработки, Postgres для полноценного режима.

## Хранилище

Без `DATABASE_URL` приложение работает в JSON-режиме. Данные пишутся в файлы внутри `backend` или в папку из `APP_DATA_DIR`.

С `DATABASE_URL` приложение использует Postgres. В этом режиме хранятся пользователи, брони, заказы, меню, акции и служебные данные админки. Изображения остаются в `backend/static`, в БД хранится путь к файлу.

Админ-панель рассчитана на Postgres. В JSON-режиме публичная часть может работать, но админка будет ограничена или недоступна.

## Переменные окружения

Минимально нужна:

- `FLASK_SECRET_KEY` - секрет Flask-сессий. Для локального запуска `run_local.py` создаёт его автоматически.

Часто используемые:

- `APP_DATA_DIR` - папка для JSON-данных;
- `DATABASE_URL` - включает Postgres-режим;
- `REDIS_URL` - включает Redis-кэш меню, если Redis доступен;
- `PUBLIC_BASE_URL` - публичный URL деплоя;
- `TRUST_PROXY_HEADERS` - учитывать proxy-заголовки на хостинге;
- `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_PARTITIONED` - настройки cookie;
- `SECURITY_ALLOW_EMBEDDED_PREVIEW` - разрешить iframe-предпросмотр сайта на хостинге;
- `DEBUG_STORAGE_ENABLED`, `SESSION_DEBUG_ENABLED`, `LOGIN_DEBUG_ENABLED` - диагностические режимы, не включать публично без необходимости.

Шаблон находится в `backend/.env.example`.

## Безопасность

В проекте уже включены базовые меры:

- CSRF-защита для POST-запросов;
- logout работает только через `POST`;
- современные password hashes через Werkzeug;
- минимальная проверка сложности пароля при регистрации;
- rate limit входа в память процесса;
- security headers: CSP, Referrer-Policy, Permissions-Policy, X-Content-Type-Options, X-Frame-Options, HSTS для HTTPS;
- debug-роуты закрыты флагами и дополнительно требуют админ-доступ.

Ограничения учебного проекта:

- rate limit хранится в памяти процесса, поэтому сбрасывается после рестарта и не общий для нескольких инстансов;
- демо-оплата не является реальной платёжной интеграцией;
- для production-уровня лучше вынести rate limit в Redis и отдельно проверить CSP под реальные внешние домены.

## Тесты

Установка dev-зависимостей:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Адресная проверка публичных auth/user-flow сценариев:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\test_auth_and_flows.py
```

Последний адресный прогон в рабочей копии:

```text
29 passed
```

Полный набор тестов:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Часть админских тестов завязана на Postgres-режим и тестовые заглушки. Если полного окружения нет, для быстрой проверки пользовательских сценариев используйте адресный прогон выше.

## Деплой

В репозитории есть `render.yaml` для Render:

- `rootDir: backend`;
- build: `pip install -r requirements.txt`;
- start: `gunicorn app:app`;
- `FLASK_SECRET_KEY` генерируется на стороне Render.

Для деплоя с полноценной админкой добавьте `DATABASE_URL`. Для iframe-предпросмотров хостинга включите:

```env
SECURITY_ALLOW_EMBEDDED_PREVIEW=1
```

## Контент

Файловый контент лежит в `backend/static`:

- `menu_items` - блюда;
- `promo_items` - реклама и акции;
- `img`, `css`, `js` - интерфейсные ассеты.

В Postgres-режиме меню и акции синхронизируются в БД. Файлы на диске остаются источником для импорта и местом хранения изображений.

Документация по DSL акций:

- `backend/doc/CBO_SCRIPT_V1.md`;
- `backend/doc/CBO_SCRIPT_V2.md`.

## Структура

- `backend/app.py` - точка входа Flask;
- `backend/config.py` - конфигурация и константы;
- `backend/routes/` - HTTP-маршруты;
- `backend/services/` - бизнес-логика;
- `backend/storage/` - JSON/Postgres слой хранения;
- `backend/templates/` - Jinja-шаблоны;
- `backend/static/` - CSS, JS, изображения и файловый контент;
- `backend/sql/` - SQL-скрипты;
- `backend/tests/` - pytest-тесты;
- `backend/doc/CHANGELOG.md` - история изменений.

## Правила проекта

- Все текстовые файлы должны быть UTF-8.
- Секреты и реальные пользовательские данные не должны попадать в репозиторий.
- История изменений ведётся в `backend/doc/CHANGELOG.md`.
