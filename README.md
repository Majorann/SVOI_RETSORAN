# SVOI_RETSORAN

Учебный веб-проект ресторана на Flask с главной страницей, бронированием столов, меню, корзиной, заказами, уведомлениями, профилем, доставкой и отдельной desktop-first admin panel.

## Возможности

- Главная страница с новостями, промо-блоками и подборкой популярных блюд
- Схема зала с интерактивными столами и бронированием по дате и времени
- Бронирование с единым timezone-aware расчётом активности и проверкой слотов до `22:00`
- Меню с фильтрацией, сортировкой, корзиной и адаптивными карточками блюд
- Checkout, экран оплаты и оплата доставки с бонусами и списанием баллов
- Доставка с сервисным сбором `42 ₽`, ETA и отдельным флоу подтверждения
- Уведомления о бронированиях, активных заказах и promo-рекламе
- Профиль пользователя с привязкой и удалением карт, анимированным accordion-блоком и live-валидацией карты
- Desktop-first admin panel под `/admin` с dashboard, заказами, бронями, доставкой, меню, promo, аналитикой, пользователями и audit log
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

- `backend/app.py` - точка входа Flask, сборка приложения, конфигурация и регистрация маршрутов
- `backend/config.py` - настройки, пути к данным, схема столов и константы
- `backend/routes/` - HTTP-маршруты по доменам
- `backend/services/business_logic.py` - timezone-aware логика бронирований, заказов и статусов
- `backend/services/order_totals.py` - единый расчёт сумм, бонусов, баллов и сервисного сбора
- `backend/services/auth_session.py` - signed cookie, восстановление session, CSRF и request-scoped auth helpers
- `backend/services/menu_content.py` - загрузка меню и promo, чтение `item.txt` и Redis-кэш меню
- `backend/services/storage_facade.py` - storage facade, prune заказов и file-locking
- `backend/services/passwords.py` - password hashing и мягкая миграция legacy hash
- `backend/storage/json_store.py` - файловое JSON-хранилище
- `backend/storage/pg_store.py` - хранилище Postgres
- `backend/models/` - dataclass-модели
- `backend/templates/` - HTML-шаблоны страниц
- `backend/templates/admin/` - HTML-шаблоны admin panel
- `backend/static/css/style.css` - стили интерфейса
- `backend/static/css/admin.css` - стили admin panel
- `backend/static/js/app.js` - лёгкая фронтенд-инициализация и подключение модулей страниц
- `backend/static/js/admin.js` - фронтенд-логика admin panel
- `backend/static/js/modules/` - JS-модули интерфейса
- `backend/static/menu_items/` - карточки блюд (`item.txt` + изображение)
- `backend/static/promo_items/` - промо и акции (`item.txt` + изображение)
- `backend/static/img/` - иконки и декоративные изображения
- `backend/sql/neon_init.sql` - инициализация схемы Postgres
- `backend/ops/migrate_json_to_neon.py` - миграция JSON -> Postgres
- `backend/CHANGELOG.md` - история изменений

## Локальный запуск

Универсальный способ запуска из корня репозитория:

```powershell
python run_local.py
```

На macOS/Linux:

```bash
python3 run_local.py
```

Что делает `run_local.py`:

- сам находит корень проекта и `backend/`;
- создаёт `backend/.venv`, если его ещё нет;
- устанавливает зависимости из `backend/requirements.txt`;
- подхватывает переменные из `backend/.env.local`, если файл существует;
- при отсутствии `FLASK_SECRET_KEY` генерирует его и сохраняет в `backend/.env.local`;
- для локального `http://127.0.0.1` выставляет безопасные dev-defaults:
  - `SESSION_COOKIE_SECURE=0`
  - `SESSION_COOKIE_SAMESITE=Lax`
  - `SESSION_COOKIE_PARTITIONED=0`
  - `TRUST_PROXY_HEADERS=0`
- запускает backend через `waitress` на `http://127.0.0.1:5000`.

Для локальной настройки можно взять шаблон:

```powershell
copy backend\.env.example backend\.env.local
```

Примеры:

```powershell
python run_local.py --host 0.0.0.0 --port 8000
python run_local.py --install-deps
python run_local.py --install-only
```

Windows PowerShell-обёртка:

```powershell
.\backend\ops\start_app.ps1
```

Windows `.bat`-обёртка:

```bat
backend\start_up\local\start_site.bat
```

Если нужен полностью ручной запуск из любого каталога:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m waitress --host 127.0.0.1 --port 5000 app:app
```

На macOS/Linux вручную:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m waitress --host 127.0.0.1 --port 5000 app:app
```

Запуск через Gunicorn:

```powershell
cd backend
gunicorn app:app --bind 0.0.0.0:7860
```

## Автотесты

Для тестов добавлен отдельный dev-набор зависимостей, чтобы не тащить `pytest` в продовый `requirements.txt`.

Установка:

```powershell
cd backend
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Запуск:

```powershell
cd ..
backend\.venv\Scripts\python -m pytest backend\tests -q
```

Что покрыто сейчас:

- регистрация с сохранением современного password hash;
- вход со старым SHA-256 hash и его автоматический апгрейд;
- восстановление авторизации только по `auth_session` cookie;
- бронирование, обычная оплата и доставка через реальные HTTP-сценарии Flask `test_client`;
- расчёт бонусов, баллов и сервисного сбора;
- timezone-aware логика активности брони.

После рефакторинга backend-структуры актуальный прогон даёт `6 passed`.

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
- `/delivery/payment` - подтверждение и оплата доставки
- `/notifications` - уведомления
- `/orders` - история заказов
- `/orders/<id>` - детали заказа
- `/profile` - профиль
- `/admin` - вход в админ-зону
- `/admin/dashboard` - dashboard
- `/admin/orders` - список заказов
- `/admin/orders/<id>` - детали заказа
- `/admin/bookings` - список броней
- `/admin/bookings/<id>` - детали брони
- `/admin/delivery` - доставка
- `/admin/menu` - управление меню
- `/admin/promo` - акции и реклама
- `/admin/analytics` - аналитика
- `/admin/users` - пользователи
- `/admin/users/<id>` - карточка пользователя
- `/admin/content` - scaffold контента
- `/admin/audit-log` - журнал действий
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
- `active` - безопасное скрытие блюда без ломки текущего parser/public menu
- `weight`, `portion`, `grams`, `volume`, `serving`, `yield` - источник бейджа порции на карточке

Если `id` некорректный или конфликтует с другим блюдом, backend автоматически назначает следующий свободный числовой ID и сохраняет исправление обратно в `item.txt` в UTF-8.

## Формат промо-блоков

Промо хранится в:

- `backend/static/promo_items/<slug>/item.txt`
- `backend/static/promo_items/<slug>/<photo>`

Поддерживаются классы:

- `reklama`
- `akciya`

Дополнительно поддерживаются:

- `priority`
- `active`
- `start_at`
- `end_at`

Шаблонные заглушки для промо backend автоматически отфильтровывает и не показывает на сайте.

## Хранилища данных

### JSON

Если `DATABASE_URL` не задан, используются локальные файлы:

- `backend/users.json`
- `backend/bookings.json`
- `backend/orders.json`

### Postgres

Если задан `DATABASE_URL`, приложение работает через Postgres backend.

Admin panel использует Postgres как source of truth для:

- `admin_users`
- `admin_actions`
- `users`
- `bookings`
- `orders`
- `order_items`
- `user_cards`

Доступ в `/admin` считается валидным, если `users.id` текущего пользователя присутствует в `admin_users.user_id`.
Если пользователь не админ, admin-страницы возвращают friendly `403`, а admin API - JSON-ошибку доступа.

Для инициализации схемы используется:

```sql
-- backend/sql/neon_init.sql
```

Для переноса существующих JSON-данных:

```powershell
python backend/ops/migrate_json_to_neon.py
```

## Переменные окружения

Шаблон переменных лежит в `backend/.env.example`.
Для локального запуска основной рабочий файл: `backend/.env.local`.

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
- `PASSWORD_HASH_METHOD` - алгоритм хранения новых паролей; по умолчанию `pbkdf2:sha256:600000`
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

Эта логика теперь собрана в `backend/services/auth_session.py`, а `backend/app.py` только подключает сервис к приложению.

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

### Бонусы, баллы и сервисный сбор

Расчёт денежных значений собран в единый backend-helper `backend/services/order_totals.py`.

Сейчас по единым правилам считаются:

- `items_total`
- `service_fee`
- `points_applied`
- `payable_total`
- `bonus_earned`

Это используется в обычном checkout, доставке, деталях заказа и уведомлениях, чтобы сумма и бонусы не расходились между экранами.

Для доставки применяется сервисный сбор `42 ₽`, который:

- показывается на этапе оформления;
- сохраняется в заказе;
- входит в итог к оплате;
- влияет на начисление бонусов.

Если заказ полностью оплачен баллами, итоговая сумма остаётся `0 ₽`, а бонусы повторно не начисляются.

### Время, бронь и статусы заказов

В проекте используется `APP_TIMEZONE` и единая timezone-aware логика из `backend/services/business_logic.py`.

Это покрывает:

- активность брони;
- доступность слотов;
- ETA доставки;
- таймеры status bar и уведомлений;
- расчёт окна жизни заказа и брони как в JSON-режиме, так и в Postgres-режиме.

Практически это нужно, чтобы локальная среда, прод и разные timezone сервера не давали разные результаты для одних и тех же бронирований и заказов.

### Admin panel

Admin panel реализована как отдельная зона внутри текущего Flask + Jinja приложения и не заменяет клиентский интерфейс.

Основные принципы:

- отдельный namespace `/admin`;
- desktop-first layout;
- backend-проверка прав по `admin_users`;
- audit logging через `admin_actions`;
- без новой role/persistence-модели для delivery statuses;
- без новой CMS для `/admin/content`;
- menu/promo редактируются form-based интерфейсом поверх файлов `item.txt`.

Сейчас в admin UI доступны:

- dashboard и KPI;
- управление заказами, бронями и доставкой;
- пользователи и корректировка бонусов;
- analytics по реальным данным;
- аудит действий администраторов;
- admin menu с live-preview карточки блюда;
- promo editor с type-aware полями и live-preview.

Ограничения текущей реализации:

- полноценная admin-зона работает только при `DATABASE_URL` / Postgres;
- мобильная версия админки намеренно не поддерживается;
- delivery-статусы в UI маппятся на существующий `orders.status`;
- `/admin/content` пока оставлен scaffold/TODO.

## Frontend-модули

Тяжёлая клиентская логика разнесена по page-specific модулям, чтобы не грузить весь код на каждой странице.

Ключевые модули:

- `backend/static/js/modules/menuCatalog.js` - фильтрация, сортировка и анимации каталога меню
- `backend/static/js/admin.js` - modals, drawers, toasts, admin charts и live-preview в admin menu/promo
- `backend/static/js/modules/cartDrawer.js` - корзина, mobile drawer и синхронизация кнопок `В корзину`
- `backend/static/js/modules/checkoutPaymentFlow.js` - checkout и экран оплаты
- `backend/static/js/modules/deliveryFlow.js` - экран оформления доставки и live-пересчёт итогов
- `backend/static/js/modules/formEnhancements.js` - маски и валидация карты, срока действия, держателя и телефона
- `backend/static/js/modules/orderStatusBar.js` - status bar активных заказов и polling статусов
- `backend/static/js/modules/paymentAddAccordion.js` - плавное раскрытие блока привязки новой карты
- `backend/static/js/modules/profileNameFit.js` - подгонка длинного имени пользователя в профиле
- `backend/static/js/modules/authToken.js` - тонкая обёртка навигации без token-логики

`backend/static/js/app.js` теперь выполняет только безопасную инициализацию страницы и подключает нужные блоки через lazy import.

## Что оптимизировано

- На backend добавлен request-scoped cache для текущего пользователя и уведомлений, чтобы не читать одни и те же данные несколько раз в рамках одного запроса.
- Расчёт сумм заказа, бонусов, баллов и сервисного сбора вынесен в единый helper `backend/services/order_totals.py`.
- Монолитный `backend/app.py` раздроблен на сервисные модули `auth_session.py`, `menu_content.py`, `storage_facade.py` и `passwords.py`, чтобы упростить сопровождение и точечные изменения.
- Логика времени выровнена между JSON-хранилищем, Postgres-веткой и сервисами статусов, чтобы избежать расхождений между локальным временем и UTC.
- `backend/static/js/app.js` разрезан на page-specific модули:
  - `menuCatalog.js`
  - `cartDrawer.js`
  - `checkoutPaymentFlow.js`
  - `formEnhancements.js`
  - `indexSummaryHydration.js`
- Главная страница не полагается только на первый server-render для баллов и status bar:
  - `/api/index-summary` вызывается один раз после загрузки;
  - постоянный polling `/api/order-statuses` работает только когда реально есть активный заказ.
- В клиентском `/menu` добавлен поиск по блюдам без перезагрузки, поверх существующего `menuCatalog.js`.

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
- Новые пароли сохраняются через `werkzeug.security.generate_password_hash`.
- Старые SHA-256 хеши поддерживаются только для мягкой миграции и автоматически обновляются после успешного логина.
- История изменений ведётся в `backend/CHANGELOG.md`.
