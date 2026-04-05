# Combo Builder Operations Script V2

Документ описывает DSL V2 для исполняемых promo-акций `class=akciya`.

## Главное отличие от V1

- добавлено `dsl_version=2`;
- в `condition` используются `==`, `!=`, `NOT`;
- приоритет операторов: `NOT > AND > OR`;
- `ID.<type>.QTY/SUM` заменён на `TYPE(<type>).QTY/SUM`;
- добавлен `UNIQUE_QTY` для `ID`, `TYPE(...)`, `GROUP(...)`;
- `ORDER.SUBTOTAL` введён как основная метрика суммы заказа (`ORDER.SUM` оставлен как alias);
- в `reward` добавлены таргетированные скидки через `TARGET=...`;
- добавлен reward `CHEAPEST_FREE_FROM_GROUP(...)`.

## Формат файла

```txt
key=value
```

Правила:
- одна строка = одно поле;
- пустые строки допустимы;
- строки, начинающиеся с `#`, считаются комментариями;
- повторять поле нельзя;
- неизвестные поля запрещены.

## Поддерживаемые поля

Общие:
- `id`
- `class=akciya`
- `name`
- `lore`
- `dsl_version`
- `condition`
- `reward`
- `notify`
- `reward_mode`
- `limit_per_order`
- `limit_per_user_per_day`
- `priority`
- `active`
- `start_at`
- `end_at`

Для исполняемой акции V2 обязательны:
- `id`
- `class=akciya`
- `name`
- `lore`
- `dsl_version=2`
- `condition`
- `reward`

## Condition (V2)

### Операторы сравнения

Поддерживаются:

```txt
==
!=
>
<
>=
<=
```

### Логические операторы

Поддерживаются:

```txt
NOT
AND
OR
```

### Приоритет

1. `NOT`
2. `AND`
3. `OR`

Скобки поддерживаются и имеют приоритет выше операторов.

### Метрики

```txt
ID(74).QTY
ID(74).SUM

ID.QTY
ID.SUM
ID.UNIQUE_QTY

TYPE(закуски).QTY
TYPE(закуски).SUM
TYPE(закуски).UNIQUE_QTY

GROUP(10,11,12).QTY
GROUP(10,11,12).SUM
GROUP(10,11,12).UNIQUE_QTY

ORDER.SUBTOTAL
ORDER.SUM
```

Семантика:
- `QTY` — сумма количества `qty`;
- `SUM` — сумма `price * qty`;
- `UNIQUE_QTY` — количество уникальных `item_id` с `qty > 0`;
- в метрики не попадают подарочные позиции (`is_gift=true`);
- `ORDER.SUM` в V2 равен `ORDER.SUBTOTAL` (alias совместимости).

## Reward (V2)

### Совместимые reward из V1

```txt
POINTS(100)
DISCOUNT_PERCENT(10)
DISCOUNT_RUB(300)
GIFT(777, 1)
```

### Новые reward

```txt
DISCOUNT_PERCENT(10, TARGET=ORDER)
DISCOUNT_PERCENT(15, TARGET=GROUP(10,11,12))
DISCOUNT_RUB(200, TARGET=ORDER)
DISCOUNT_RUB(300, TARGET=GROUP(10,11,12))
CHEAPEST_FREE_FROM_GROUP(10,11,12)
```

Ограничения:
- `TARGET` разрешён только для `DISCOUNT_PERCENT` и `DISCOUNT_RUB`;
- `TARGET` может быть только `ORDER` или `GROUP(...)`;
- `CHEAPEST_FREE_FROM_GROUP(...)` поддерживает только `reward_mode=once`.

## reward_mode

```txt
once
per_match
```

`per_match` разрешён только для одного сравнения вида `... >= N`, где `N > 0`.

## Примеры

### V2, баллы

```txt
id=1001
class=akciya
name=2 закуски + чек
lore=За 2 закуски и чек от 900 начислим 100 баллов
dsl_version=2
condition=TYPE(закуски).QTY >= 2 AND ORDER.SUBTOTAL >= 900
reward=POINTS(100)
reward_mode=once
active=true
priority=100
```

### V2, скидка на группу

```txt
id=1002
class=akciya
name=Скидка на набор
lore=15% на конкретную группу блюд
dsl_version=2
condition=GROUP(10,11,12).UNIQUE_QTY >= 2
reward=DISCOUNT_PERCENT(15, TARGET=GROUP(10,11,12))
reward_mode=once
active=true
priority=120
```

### V2, самое дешёвое бесплатно

```txt
id=1003
class=akciya
name=Самое дешёвое бесплатно
lore=Одно самое дешёвое блюдо из группы бесплатно
dsl_version=2
condition=GROUP(10,11,12).QTY >= 3
reward=CHEAPEST_FREE_FROM_GROUP(10,11,12)
reward_mode=once
active=true
priority=130
```

## Обратная совместимость

- если `dsl_version` не указан, применяется V1;
- V1-синтаксис остаётся валиден;
- `ORDER.SUM` поддерживается и в V2 (как alias);
- старые `DISCOUNT_PERCENT(n)` и `DISCOUNT_RUB(n)` эквивалентны `TARGET=ORDER`.
