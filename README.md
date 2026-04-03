# SVOI_RETSORAN

Учебный Flask-проект ресторана с бронированием, меню, корзиной, заказами, доставкой, бонусами и desktop-first admin panel.

## Что есть

- главная страница, уведомления, профиль и история заказов;
- бронирование столов со схемой зала;
- меню и доставка с корзиной;
- checkout и экран оплаты;
- популярные блюда на главной с hover-overlay;
- promo-система для `reklama` и `akciya`;
- admin panel на `/admin`;
- работа через JSON или Postgres.

## Хранилище

- Без `DATABASE_URL` приложение работает на JSON:
  - `backend/users.json`
  - `backend/bookings.json`
  - `backend/orders.json`
- С `DATABASE_URL` приложение работает через Postgres.

В Postgres-режиме:

- пользователи, брони, заказы и карты лежат в БД;
- `menu_items` и `promotions` тоже лежат в БД;
- изображения блюд и акций остаются в `backend/static/...`, в БД хранится только путь;
- при старте backend выполняется автосогласование контента с хоста:
  - меню и акции читаются из файлов;
  - записи в БД обновляются через `upsert`;
  - если записи больше нет среди файлов, она не удаляется, а отключается через `active = false`.

`reklama` и `akciya` в Postgres-режиме читаются из БД. Файлы на диске используются как источник для sync/import и для медиа.

## Быстрый запуск

Из корня репозитория:

```powershell
python run_local.py
```

На macOS/Linux:

```bash
python3 run_local.py
```

`run_local.py` сам:

- создаёт `backend/.venv`, если нужно;
- ставит зависимости;
- подхватывает `backend/.env.local`;
- генерирует `FLASK_SECRET_KEY`, если его нет;
- запускает backend локально.
- использует UTF-8 при работе с локальными служебными файлами.

## Ручной запуск

Windows:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m waitress --host 127.0.0.1 --port 5000 app:app
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m waitress --host 127.0.0.1 --port 5000 app:app
```

## Переменные окружения

Минимально:

- `FLASK_SECRET_KEY`

Для Postgres:

- `DATABASE_URL`

Полезные дополнительные:

- `APP_DATA_DIR`
- `PUBLIC_BASE_URL`
- `SESSION_COOKIE_SAMESITE`
- `SESSION_COOKIE_SECURE`
- `SESSION_COOKIE_PARTITIONED`
- `TRUST_PROXY_HEADERS`
- `APP_TIMEZONE`
- `REDIS_URL`
- `MENU_CACHE_ENABLED`

Шаблон: `backend/.env.example`

## Автотесты

Установка dev-зависимостей:

```powershell
cd backend
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Запуск:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests -q
```

Из корня репозитория:

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend)
backend\.venv\Scripts\python -m pytest backend\tests -q
```

Последний адресный regression-check в рабочей копии: `16 passed`.

## Основные пути

- `/` - главная
- `/reserve` - бронирование
- `/menu` - меню
- `/menu/<id>` - отдельный preview блюда отключён, route редиректит обратно в `/menu`
- `/delivery` - меню доставки
- `/checkout` - оформление заказа
- `/delivery/checkout` - оформление доставки
- `/orders` - история заказов
- `/notifications` - уведомления
- `/profile` - профиль
- `/admin` - админка

## Контент

### Блюда

Файлы-источник:

- `backend/static/menu_items/<slug>/item.txt`
- `backend/static/menu_items/<slug>/<photo>`

Минимальный формат:

```txt
id=101
name=Брускетта
type=Закуски
price=390
lore=Описание
featured=true
active=true
weight=250 г
```

Примечание:

- значение `weight` / `portion` нормализуется в `portion_label` и используется в интерфейсе как граммовка или объём блюда.

### Промо

Файлы-источник:

- `backend/static/promo_items/reklama/...`
- `backend/static/promo_items/akciya/...`

Поддерживаются:

- `reklama`:

```txt
id=1
class=reklama
text=Текст рекламы
link=https://example.com
```

- `akciya` как информационная акция:

```txt
id=2
class=akciya
name=Пройди опрос
lore=Описание акции
```

- `akciya` как исполняемая акция:

```txt
id=3
class=akciya
name=FPV бонус
lore=За 2 блюда начислим баллы
condition=ID(74).QTY >= 2
reward=POINTS(100)
reward_mode=once
```

Полная DSL-документация: `backend/doc/CBO_SCRIPT_V1.md`

## Admin panel

Admin panel доступна только при работе через Postgres.

Основные разделы:

- dashboard;
- заказы, брони и доставка;
- меню;
- акции и реклама;
- пользователи;
- аналитика;
- audit log.

На dashboard есть кнопка `Автосогласование`, которая вручную запускает синхронизацию меню и акций с хоста в БД без перезапуска сайта.

После последних правок:

- detail-страница брони после отмены возвращает в общий список броней;
- в `Заказах` и `Доставке` выровнены toolbar-фильтры и `per_page`;
- автосогласование отключает отсутствующие блюда и акции, а не удаляет их.

## UI и UX

- логин и регистрация используют единый телефонный формат с маской `+7`;
- checkout устойчив к длинным promo-блокам и различиям рендера между локалкой и хостом;
- фон страницы `reserve` усилен для сценариев с маленькой высотой окна и сильным zoom;
- detail-preview блюда по маршруту `/menu/<id>` больше не используется в пользовательском потоке.

## Структура проекта

- `backend/app.py` - точка входа Flask
- `backend/config.py` - конфиг и константы
- `backend/routes/` - маршруты
- `backend/services/` - бизнес-логика
- `backend/storage/` - JSON/Postgres storage
- `backend/templates/` - Jinja-шаблоны
- `backend/static/` - CSS, JS, изображения и файловый контент
- `backend/sql/` - SQL-файлы для Postgres
- `backend/doc/CHANGELOG.md` - история изменений

## Примечания

- Все файлы проекта должны быть в UTF-8.
- История изменений ведётся в `backend/doc/CHANGELOG.md`.
