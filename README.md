# SVOI_RETSORAN

Учебный веб-проект ресторана на Flask с главной страницей, бронированием столов, меню, корзиной, заказами, уведомлениями, профилем и доставкой.

## Возможности

- Главная страница с новостями, промо-блоками и подборкой популярных блюд
- Схема зала с интерактивными столами и бронированием по дате и времени
- Меню с фильтрацией, сортировкой, корзиной и адаптивными карточками блюд
- Checkout и экран оплаты
- Уведомления о бронированиях и активных заказах
- Профиль пользователя с привязкой и удалением карт
- Авторизация и регистрация
- Работа через JSON-хранилища или Neon Postgres
- Опциональный Redis-кэш для меню

## Стек

- Python 3.12
- Flask
- Gunicorn
- HTML / CSS / JavaScript
- JSON storage и/или Neon Postgres
- Redis для кэша меню

## Структура проекта

- `backend/app.py` - точка входа Flask, загрузка меню и промо, конфигурация приложения
- `backend/config.py` - настройки, пути к данным, схема столов и константы
- `backend/routes/` - HTTP-маршруты по доменам
- `backend/services/` - бизнес-логика
- `backend/storage/json_store.py` - файловое JSON-хранилище
- `backend/storage/pg_store.py` - хранилище Postgres
- `backend/models/` - dataclass-модели
- `backend/templates/` - HTML-шаблоны страниц
- `backend/static/css/style.css` - стили интерфейса
- `backend/static/js/app.js` - фронтенд-инициализация
- `backend/static/js/modules/` - JS-модули интерфейса
- `backend/static/menu_items/` - карточки блюд (`item.txt` + изображение)
- `backend/static/promo_items/` - промо и акции (`item.txt` + изображение)
- `backend/static/img/` - иконки и декоративные изображения
- `backend/sql/neon_init.sql` - инициализация схемы Postgres
- `backend/ops/migrate_json_to_neon.py` - миграция JSON -> Postgres
- `backend/CHANGELOG.md` - история изменений

## Локальный запуск

```powershell
cd "C:\Users\almaz\OneDrive\Рабочий стол\main\SVOI_RETSORAN-main\backend"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Приложение откроется на `http://127.0.0.1:5000`.

Запуск через Gunicorn:

```powershell
cd "C:\Users\almaz\OneDrive\Рабочий стол\main\SVOI_RETSORAN-main\backend"
gunicorn app:app --bind 0.0.0.0:7860
```

## Docker

В родительской папке `main` лежат файлы для контейнерного запуска:

- `Dockerfile`
- `docker-compose.yml`
- `docker.yml`

## Основные страницы

- `/` - главная
- `/reserve` - бронирование
- `/menu` - меню
- `/checkout` - оформление заказа
- `/payment` - предпросмотр оплаты
- `/notifications` - уведомления
- `/orders` - история заказов
- `/orders/<id>` - детали заказа
- `/profile` - профиль
- `/login` - вход
- `/register` - регистрация

## Формат блюд

Каждое блюдо хранится в отдельной папке:

- `backend/static/menu_items/<slug>/item.txt`
- `backend/static/menu_items/<slug>/<photo>`

Пример `item.txt`:

```txt
id=101
name=Брускетта с томатами
type=Закуски
price=390
weight=250 г
lore=Поджаренный багет, томаты, базилик и оливковое масло.
featured=true
```

Поддерживаются поля:

- `id` - идентификатор блюда
- `name` - название
- `type` - категория
- `price` - цена
- `lore` - описание
- `featured` - попадание в блок популярных блюд
- `weight`, `portion`, `grams`, `volume`, `serving`, `yield` - источник бейджа порции на карточке

Если `id` некорректный или конфликтует с другим блюдом, backend автоматически назначает следующий свободный числовой ID.

## Формат промо-блоков

Промо хранится в:

- `backend/static/promo_items/<slug>/item.txt`
- `backend/static/promo_items/<slug>/<photo>`

Поддерживаются классы:

- `reklama`
- `akciya`

Шаблонные заглушки для промо backend автоматически отфильтровывает и не показывает на сайте.

## Хранилища данных

### JSON

Если `DATABASE_URL` не задан, используются локальные файлы:

- `backend/users.json`
- `backend/bookings.json`
- `backend/orders.json`

### Postgres

Если задан `DATABASE_URL`, приложение работает через Postgres backend.

Для инициализации схемы используется:

```sql
-- backend/sql/neon_init.sql
```

Для переноса существующих JSON-данных:

```powershell
python backend/ops/migrate_json_to_neon.py
```

## Переменные окружения

Минимально:

- `FLASK_SECRET_KEY` - секрет Flask-сессий

Для Postgres:

- `DATABASE_URL` - строка подключения к Neon/Postgres

Полезные дополнительные переменные:

- `APP_DATA_DIR` или `DATA_DIR` - каталог для JSON-файлов
- `SESSION_COOKIE_SAMESITE`
- `SESSION_COOKIE_SECURE`
- `SESSION_COOKIE_PARTITIONED`
- `TRUST_PROXY_HEADERS`
- `APP_TIMEZONE`
- `DB_KEEPALIVE_ENABLED`
- `DB_KEEPALIVE_INTERVAL_SECONDS`
- `REDIS_URL`
- `MENU_CACHE_ENABLED`
- `MENU_CACHE_TTL_SECONDS`
- `MENU_CACHE_KEY`
- `POSTGRES_STARTUP_RETRIES`
- `POSTGRES_STARTUP_RETRY_DELAY_SECONDS`
- `DB_OPERATION_RETRIES`
- `DB_RETRY_DELAY_SECONDS`
- `DEBUG_STORAGE_ENABLED`

## Диагностика

Эндпоинт:

- `GET /debug/storage`

Показывает активный backend, пути хранилищ и количество записей. По текущей логике доступен только при включении `DEBUG_STORAGE_ENABLED=true`.

## Примечания

- Корзина хранится в `localStorage` браузера.
- Пароли в учебной версии хранятся как SHA-256 без соли.
- Для production нужен более сильный механизм хеширования.
- История изменений ведётся в `backend/CHANGELOG.md`.
