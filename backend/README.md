# Ресторан — веб-приложение (Flask)

Учебный проект: сайт ресторана с главной страницей, схемой зала, бронированием столиков, меню и базовой авторизацией.

## Возможности

- Главная страница с новостями и популярными блюдами
- Схема зала с интерактивными столами
- Бронирование на дату/время (занятость рассчитывается с интервалом 1 час)
- Уведомления о брони
- Меню с фильтрацией по разделам и простой корзиной (localStorage)
- Регистрация/вход (JSON-хранилище)

## Стек

- Python 3.10+
- Flask
- HTML/CSS/JS

## Структура проекта

- `app.py` — маршруты Flask, бизнес-логика, JSON-хранилища
- `templates/` — HTML-шаблоны
- `static/`
  - `css/style.css` — стили
  - `js/app.js` — фронтенд-логика
  - `menu_items/<позиция>/` — данные блюд (`item.txt`) и фото (`photo.png`)
  - `img/` — изображения
- `bookings.json` — бронирования (создаётся автоматически)
- `users.json` — пользователи (создаётся автоматически)

## Запуск

```powershell
cd "путь\...\Проект\backend"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Открыть: `http://..../`

## Основные страницы

- `/` — главная
- `/reserve` — бронирование
- `/menu` — меню
- `/notifications` — уведомления
- `/profile` — профиль
- `/login` — вход
- `/register` — регистрация

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

- Длительность брони: `BOOKING_DURATION_MINUTES` в `app.py`
- Позиции столов: `TABLES` в `app.py`
- Стены: `WALLS` в `app.py` + координаты в `style.css`

## Формат блюд (menu_items)

Каждое блюдо хранится в отдельной папке:

`static/menu_items/<slug>/item.txt`  
`static/menu_items/<slug>/photo.png` (рекомендуется 480x480)

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
- `static/promo_items/<slug>/photo.png` (если используете изображение)

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

- Это учебный проект без полноценной безопасности.
- Пароли хранятся как SHA-256 без соли (для учебных целей).
- Корзина хранится в `localStorage` браузера.

## TODO (идеи)
-Доработать взаимодействие с картами
-Организовать оформление заказа
-Добавить не контрастые рисунки людей

