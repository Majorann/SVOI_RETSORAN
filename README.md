# SVOI_RETSORAN

Учебный веб-проект ресторана на Flask с главной страницей, бронированием столов, меню, корзиной, заказами, уведомлениями, профилем и доставкой.

## Возможности

- Главная страница с новостями, промо-блоками и подборкой популярных блюд
- Схема зала с интерактивными столами и бронированием по дате и времени
- Меню с фильтрацией, сортировкой, корзиной и адаптивными карточками блюд
- Checkout, экран оплаты и оплата доставки
- Уведомления о бронированиях и активных заказах
- Профиль пользователя с привязкой и удалением карт
- Авторизация и регистрация
- Cookie-only авторизация на Flask session
- Signed `auth_session` cookie для восстановления server-side session на первом запросе
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
- `backend/static/js/app.js` - лёгкая фронтенд-инициализация и подключение модулей страниц
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
cd "C:\*****\main\SVOI_RETSORAN-main\backend"
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
- `/delivery` - меню доставки
- `/delivery/checkout` - оформление доставки
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

Если `id` некорректный или конфликтует с другим блюдом, backend автоматически назначает следующий свободный числовой ID и сохраняет исправление обратно в `item.txt` в UTF-8.

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
- `PUBLIC_BASE_URL` - публичный URL сайта; если начинается с `https://`, secure-cookie включается по умолчанию
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
- `LOGIN_DEBUG_ENABLED` - включает логирование неудачных входов в файл JSONL
- `LOGIN_DEBUG_LOG_PATH` - путь к файлу лога неудачных входов; по умолчанию `backend/login_failed_attempts.jsonl` или файл в `APP_DATA_DIR`
- `SESSION_DEBUG_ENABLED` - включает диагностику сессии и эндпоинт `/debug/session`
- `SESSION_DEBUG_LOG_PATH` - путь к файлу session-debug лога; по умолчанию `backend/session_debug.jsonl` или файл в `APP_DATA_DIR`
- `AUTH_SESSION_COOKIE_NAME` - имя дополнительного signed cookie для восстановления server-side session
- `AUTH_SESSION_COOKIE_MAX_AGE_SECONDS` - срок жизни signed `auth_session` cookie
- `CHECKOUT_PREVIEW_MAX_AGE_SECONDS` - срок жизни подписанного preview-токена для подтверждения оплаты

### Подсказка по логину и cookie

- Если сайт открыт по `http://` в локальной сети, secure-cookie нужно отключить: `SESSION_COOKIE_SECURE=false`
- Если сайт открыт по `https://`, лучше использовать `PUBLIC_BASE_URL=https://...` или явно задать `SESSION_COOKIE_SECURE=true`
- Если сайт встроен в iframe или открывается в кросс-доменном контексте, обычно нужны `SESSION_COOKIE_SAMESITE=None` и `SESSION_COOKIE_SECURE=true`

## Диагностика

Эндпоинт:

- `GET /debug/storage`

Показывает активный backend, пути хранилищ и количество записей. По текущей логике доступен только при включении `DEBUG_STORAGE_ENABLED=true`.

Если включить `LOGIN_DEBUG_ENABLED=true`, backend будет записывать все неудачные входы в UTF-8 JSONL-файл.
В запись попадают причина отказа, телефон в введённом виде, нормализованный телефон, IP и `User-Agent`.
Пароли в debug-лог не записываются.

Если включить `SESSION_DEBUG_ENABLED=true`, станет доступен `GET /debug/session`, а backend начнёт писать ключевые события сессии в UTF-8 JSONL-файл.
Это полезно, когда логин формально успешен, но последующие запросы теряют `session`.

### Cookie-only авторизация и first-load

Текущая схема авторизации полностью опирается на cookie и не использует `localStorage`, query/form токены или `Authorization: Bearer`.

Что делает backend:

- после входа или регистрации поднимает обычную Flask session;
- дополнительно выставляет signed `auth_session` cookie;
- на следующем запросе может восстановить `session["user_id"]` из `auth_session`, даже если Flask session по какой-то причине не доехала стабильно;
- очищает `auth_session` cookie, если она стала невалидной.

Что делает frontend:

- для главной страницы один раз вызывает `/api/index-summary`, чтобы баллы и status bar не зависели только от первого HTML-рендера;
- использует polling `/api/order-statuses` только когда действительно есть активный заказ.

### Рекомендованные настройки для Hugging Face Spaces

Для рабочего домена `https://mayaran-mdk2.hf.space` рекомендуется:

- `PUBLIC_BASE_URL=https://mayaran-mdk2.hf.space`
- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_SAMESITE=None`
- `SESSION_COOKIE_PARTITIONED=true`
- `TRUST_PROXY_HEADERS=true`

### Оплата и подтверждение заказа

Для обычной оплаты и оплаты доставки используется не только server-side session preview, но и подписанный preview-токен.
Это нужно для случаев, когда между шагом предпросмотра и шагом подтверждения часть сессии теряется.

Сейчас flow такой:

- `/payment` и `/delivery/payment` формируют preview заказа;
- в форму подтверждения вкладывается подписанный `preview_token`;
- `/payment/confirm` и `/delivery/confirm` умеют восстановить preview либо из session, либо из signed token;
- это снижает риск ошибок вида `Оплата не прошла` из-за пропавшего preview между шагами.

## Frontend-модули

Тяжёлая клиентская логика разнесена по page-specific модулям, чтобы не грузить весь код на каждой странице.

Ключевые модули:

- `backend/static/js/modules/menuCatalog.js` - фильтрация, сортировка и анимации каталога меню
- `backend/static/js/modules/cartDrawer.js` - корзина, mobile drawer и синхронизация кнопок `В корзину`
- `backend/static/js/modules/checkoutPaymentFlow.js` - checkout и экран оплаты
- `backend/static/js/modules/formEnhancements.js` - маски и валидация карты, срока действия, держателя и телефона
- `backend/static/js/modules/authToken.js` - тонкая обёртка навигации без token-логики

`backend/static/js/app.js` теперь выполняет только безопасную инициализацию страницы и подключает нужные блоки через lazy import.

## Что оптимизировано

- На backend добавлен request-scoped cache для текущего пользователя и уведомлений, чтобы не читать одни и те же данные несколько раз в рамках одного запроса.
- `backend/static/js/app.js` разрезан на page-specific модули:
  - `menuCatalog.js`
  - `cartDrawer.js`
  - `checkoutPaymentFlow.js`
  - `formEnhancements.js`
  - `indexSummaryHydration.js`
- Главная страница не полагается только на первый server-render для баллов и status bar:
  - `/api/index-summary` вызывается один раз после загрузки;
  - постоянный polling `/api/order-statuses` работает только когда реально есть активный заказ.

## Проверка auth

После изменений имеет смысл проверять на рабочем домене `https://mayaran-mdk2.hf.space`:

1. login и первый заход на `/`;
2. профиль и баллы;
3. бронирование;
4. checkout и оплата;
5. доставка;
6. logout/login;
7. мобильные браузеры;
8. `GET /debug/session` при включённом `SESSION_DEBUG_ENABLED=true`.

- На backend текущий пользователь и данные уведомлений кэшируются в рамках одного запроса, чтобы не читать одни и те же данные несколько раз.
- На frontend основной `app.js` уменьшен и превращён в orchestration-layer вместо монолитного файла.
- Каталог меню, корзина, checkout и form-enhancements вынесены в отдельные модули без смены пользовательского поведения.

## Примечания

- Корзина хранится в `localStorage` браузера.
- Пароли в учебной версии хранятся как SHA-256 без соли.
- Для production нужен более сильный механизм хеширования.
- История изменений ведётся в `backend/CHANGELOG.md`.
