# Ресторан — веб-приложение (Flask)

Учебный проект: сайт ресторана с главной страницей, схемой зала, бронированием столиков, меню, корзиной, оплатой и базовой авторизацией.

## Возможности

- Главная страница с новостями и популярными блюдами
- Схема зала с интерактивными столами
- Бронирование на дату/время (занятость рассчитывается с интервалом 1 час)
- Уведомления о брони
- Меню с фильтрацией/сортировкой и корзиной (localStorage)
- Адаптивная корзина в меню: desktop drawer + mobile FAB/bottom sheet
- Checkout -> Payment -> подтверждение заказа
- Регистрация/вход (JSON-хранилище)
- Профиль с привязкой/удалением карты
- Статус-бар заказа на главной с таймером, стадиями и анимациями текста

## Стек

- Python 3.12+ (локально) / `python-3.12.7` на Render
- Flask
- HTML/CSS/JS

## Структура проекта

- `app.py` — точка входа Flask и композиция модулей
- `config.py` — пути к JSON, константы, `TABLES/WALLS`, шаги статусов заказа
- `routes/` — HTTP-маршруты по доменам:
  - `main_routes.py`, `auth_routes.py`, `booking_routes.py`, `menu_routes.py`, `orders_routes.py`, `profile_routes.py`
- `services/` — бизнес-логика (`business_logic.py`)
- `storage/` — чтение/запись JSON (`json_store.py`)
- `models/` — dataclass-модели (`MenuItem`, `PromoItem`, `Booking`, `Order`, `User`)
- `templates/` — HTML-шаблоны
- `static/`
  - `css/style.css` — стили
  - `js/app.js` — entrypoint фронтенда (ES modules)
  - `js/modules/` — модули фронтенда (`core`, `menuHoverMood`, `bottomNavMotion`, `tableTooltip`, `orderStatusBar`, `pointsBalanceCard`)
  - `menu_items/<позиция>/` — данные блюд (`item.txt`) и фото (`photo.png` или `photo.webp`)
  - `promo_items/<позиция>/` — данные промо-блоков (`item.txt`) и фото
  - `img/` — изображения
- `bookings.json` — бронирования
- `orders.json` — заказы
- `users.json` — пользователи и карты

## Запуск

```powershell
cd "путь\...\Проект\backend"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Открыть локально: `http://127.0.0.1:5000`

## Основные страницы

- `/` — главная
- `/reserve` — бронирование
- `/menu` — меню
- `/checkout` — оформление
- `/payment` — предпросмотр оплаты (POST)
- `/notifications` — уведомления
- `/orders` — история заказов
- `/orders/<id>` — детали заказа
- `/profile` — профиль
- `/login` — вход
- `/register` — регистрация

## Мобильный UX меню (`/menu`)

- На mobile используется фиксированная FAB-кнопка корзины (правый нижний угол) с badge количества.
- По нажатию FAB открывается `bottom sheet` корзины поверх контента (через overlay), без сдвига списка блюд.
- Закрытие корзины:
  - кнопка в шапке панели;
  - тап по overlay;
  - свайп вниз по шапке панели (закрытие при смещении более `30%` высоты sheet).
- Карточки блюд на mobile раскрываются по тапу на карточку (`.is-expanded`), при этом тап по кнопке `В корзину` не переключает раскрытие.
- На desktop сохранён правый drawer-режим корзины.

## Now Bar (статусы заказа)

- Компонент выводится на главной при наличии активных заказов.
- Стадии:
  - `cooking` (`Готовим`)
  - `delivering` (`Несём`)
  - `delivered` (`Заказ выдан`)
- Для каждой стадии используется пул случайных фраз; одинаковая фраза не повторяется подряд.
- Логика анимаций:
  - комментарий статуса — typewriter (стирание -> пауза -> печать) с caret;
  - заголовок стадии — эффект «электронного табло» (scramble);
  - прогресс-бар — плавный переход ширины + мягкий shimmer и glow.
- Диапазоны прогресса по стадиям:
  - `cooking`: `20-60%`
  - `delivering`: `65-90%`
  - `delivered`: `100%`
- Для пользователей с `prefers-reduced-motion: reduce` снижена интенсивность анимаций (caret/shimmer/transitions).

## JS-модули фронтенда

- `static/js/app.js` — entrypoint и инициализация страниц.
- `static/js/modules/core.js` — общие утилиты (`stagger`, CSRF helper).
- `static/js/modules/menuHoverMood.js` — динамика фона/неона от фото блюда.
- `static/js/modules/bottomNavMotion.js` — анимированный индикатор нижней навигации.
- `static/js/modules/tableTooltip.js` — интерактив схемы зала и мобильные sheet-панели бронирования.
- `static/js/modules/orderStatusBar.js` — логика стадий заказа, таймеры, фразы и анимации now bar.
- `static/js/modules/pointsBalanceCard.js` — анимация/адаптация карточки баллов.

## Хранилища (JSON)

### bookings.json

Пример записи:
```json
{
  "table_id": 5,
  "date": "2026-02-03",
  "time": "19:00",
  "name": "Андрей",
  "user_id": 1,
  "created_at": "2026-02-03T12:00:00"
}
```

### users.json

Пример записи:
```json
{
  "id": 1,
  "name": "Андрей",
  "phone": "+79990000000",
  "password_hash": "...",
  "balance": 0,
  "cards": [
    {"brand": "Visa", "last4": "4821", "active": true}
  ],
  "created_at": "2026-02-03T12:00:00"
}
```

## Настройки

- Длительность брони: `BOOKING_DURATION_MINUTES` в `config.py`
- Позиции столов: `TABLES` в `config.py`
- Стены: `WALLS` в `config.py` + координаты в `style.css`
- Секрет сессии: `FLASK_SECRET_KEY` (env)
- Флаг secure-cookie: `SESSION_COOKIE_SECURE` (env)

## Безопасность и валидация

- Для mutating-запросов включена CSRF-защита (токен в сессии + hidden/input/header).
- Для JSON-операций используется файловая блокировка (`*.lock`) в критических местах.
- Пароли хранятся как SHA-256 без соли (допустимо только для учебного проекта).
- В привязке карты:
  - holder нормализуется в английский формат (автотранслитерация RU -> EN);
  - срок карты проходит проверку `MM/YY`, месяц `01..12`, дата не в прошлом.

## Формат блюд (menu_items)

Каждое блюдо хранится в отдельной папке:

`static/menu_items/<slug>/item.txt`  
`static/menu_items/<slug>/photo.png` или `static/menu_items/<slug>/photo.webp` (рекомендуется 480x480)

Пример `item.txt`:

```txt
id=101
name=Брускетта с томатами
type=Закуски
price=390
lore=Поджаренный багет, томаты, базилик и оливковое масло.
featured=true
```

Поля:
- `id` — уникальный целый ID блюда
- `name` — название
- `type` — категория (например, `Закуски`, `Супы`)
- `price` — цена в рублях (целое число)
- `lore` — описание
- `featured` — `true/false`, попадание в блок "Популярное" на главной

## Формат промо-блоков (promo_items)

Папка:
- `static/promo_items/<slug>/item.txt`
- `static/promo_items/<slug>/photo.png` или `static/promo_items/<slug>/photo.webp` (если используете изображение)

Созданы заготовки:
- `static/promo_items/reklama/item.txt`
- `static/promo_items/akciya/item.txt`

Пример `reklama/item.txt`:

```txt
id=1
class=reklama
text=Текст рекламного блока.
link=https://example.com
priority=10
active=true
```

Пример `akciya/item.txt`:

```txt
id=2
class=akciya
name=Название акции
lore=Описание акции и условия.
priority=20
active=true
```

Поля:
- `id` — уникальный целый ID блока
- `class` — класс блока (`reklama` или `akciya`)
- `text` — текст (для `reklama`)
- `link` — ссылка (для `reklama`)
- `name` — название (для `akciya`)
- `lore` — описание (для `akciya`)
- `priority` — порядок сортировки
- `active` — `true/false`, активность блока

## Примечания

- Это учебный проект без полноценной production-безопасности.
- Корзина хранится в `localStorage` браузера.
- JSON-хранилища подходят для учебного сценария, но не для высокой нагрузки/конкуренции.

## Deploy на Render (полный Flask backend)

В репозитории уже подготовлены файлы:
- `render.yaml` (в корне проекта)
- `backend/runtime.txt`
- `backend/requirements.txt` (добавлен `gunicorn`)

Шаги:
1. Запушить изменения в GitHub-репозиторий.
2. В Render: `New +` -> `Blueprint`.
3. Выбрать репозиторий `Majorann/SVOI_RETSORAN`.
4. Render автоматически прочитает `render.yaml` и создаст web service.
5. Нажать `Apply`/`Deploy`.

После деплоя приложение будет доступно по URL вида:
`https://<service-name>.onrender.com`

Важно:
- Файлы `users.json`, `bookings.json`, `orders.json` в Render живут на эфемерной файловой системе.
- Для учебного проекта это нормально, но данные могут сбрасываться при пересборке/рестарте.

