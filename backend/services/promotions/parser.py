from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ast import (
    Comparison,
    ConditionGroup,
    ConditionNot,
    MetricRef,
    PromotionDefinition,
    PromotionDslError,
    Reward,
)


SUPPORTED_FIELDS = {
    "id",
    "type",
    "class",
    "name",
    "lore",
    "dsl_version",
    "active",
    "priority",
    "condition",
    "reward",
    "notify",
    "reward_mode",
    "limit_per_order",
    "limit_per_user_per_day",
    "start_at",
    "end_at",
}

KEYWORDS = {
    "AND",
    "OR",
    "NOT",
    "ID",
    "TYPE",
    "GROUP",
    "ORDER",
    "QTY",
    "SUM",
    "UNIQUE_QTY",
    "SUBTOTAL",
}


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


def parse_promotion(raw_text: str) -> PromotionDefinition:
    fields = _parse_fields(raw_text)
    if "condition" not in fields:
        raise PromotionDslError("Missing required field: condition")
    if "reward" not in fields:
        raise PromotionDslError("Missing required field: reward")

    notify = fields.get("notify")
    if notify is not None:
        notify = notify.strip()
        if not notify:
            raise PromotionDslError("Field notify must not be empty")
        if "\n" in notify or "\r" in notify:
            raise PromotionDslError("Field notify must be a single line")

    dsl_version = _parse_dsl_version(fields.get("dsl_version"))
    promotion_type = fields.get("class", fields.get("type", "akciya")).strip() or "akciya"

    return PromotionDefinition(
        promotion_type=promotion_type,
        name=fields.get("name", "").strip(),
        dsl_version=dsl_version,
        active=_parse_bool(fields.get("active", "true"), "active"),
        priority=_parse_int(fields.get("priority", "0"), "priority", allow_zero=True),
        condition=parse_condition(fields["condition"], dsl_version=dsl_version),
        reward=parse_reward(fields["reward"], dsl_version=dsl_version),
        notify=notify,
        reward_mode=_parse_reward_mode(fields.get("reward_mode", "once")),
        limit_per_order=_parse_optional_int(fields.get("limit_per_order"), "limit_per_order"),
        limit_per_user_per_day=_parse_optional_int(
            fields.get("limit_per_user_per_day"),
            "limit_per_user_per_day",
        ),
        start_at=_parse_datetime(fields.get("start_at"), "start_at"),
        end_at=_parse_datetime(fields.get("end_at"), "end_at"),
    )


def parse_condition(text: str, *, dsl_version: int = 1):
    tokens = _tokenize(text)
    parser = _ConditionParser(tokens, dsl_version=dsl_version)
    result = parser.parse()
    if parser.current.kind != "EOF":
        raise PromotionDslError(f"Unexpected token '{parser.current.value}' in condition")
    return result


def parse_reward(text: str, *, dsl_version: int = 1) -> Reward:
    source = (text or "").strip()
    if not source:
        raise PromotionDslError("Reward must not be empty")

    points_payload = _extract_function_payload(source, "POINTS")
    if points_payload is not None:
        return Reward(
            kind="POINTS",
            amount=_parse_int(points_payload, "POINTS", allow_zero=False),
        )

    discount_percent_payload = _extract_function_payload(source, "DISCOUNT_PERCENT")
    if discount_percent_payload is not None:
        amount, target_kind, target_group_ids = _parse_discount_reward_payload(
            discount_percent_payload,
            "DISCOUNT_PERCENT",
            dsl_version=dsl_version,
        )
        return Reward(
            kind="DISCOUNT_PERCENT",
            amount=amount,
            target_kind=target_kind,
            target_group_ids=target_group_ids,
        )

    discount_rub_payload = _extract_function_payload(source, "DISCOUNT_RUB")
    if discount_rub_payload is not None:
        amount, target_kind, target_group_ids = _parse_discount_reward_payload(
            discount_rub_payload,
            "DISCOUNT_RUB",
            dsl_version=dsl_version,
        )
        return Reward(
            kind="DISCOUNT_RUB",
            amount=amount,
            target_kind=target_kind,
            target_group_ids=target_group_ids,
        )

    gift_payload = _extract_function_payload(source, "GIFT")
    if gift_payload is not None:
        parts = _split_csv(gift_payload)
        if len(parts) != 2:
            raise PromotionDslError("GIFT reward must be in format GIFT(id, qty)")
        return Reward(
            kind="GIFT",
            item_id=_parse_int(parts[0], "GIFT item id", allow_zero=False),
            qty=_parse_int(parts[1], "GIFT qty", allow_zero=False),
        )

    cheapest_payload = _extract_function_payload(source, "CHEAPEST_FREE_FROM_GROUP")
    if cheapest_payload is not None:
        if dsl_version != 2:
            raise PromotionDslError("CHEAPEST_FREE_FROM_GROUP is supported only in DSL v2")
        group_ids = _parse_group_ids_payload(
            cheapest_payload,
            field_name="CHEAPEST_FREE_FROM_GROUP",
        )
        return Reward(
            kind="CHEAPEST_FREE_FROM_GROUP",
            target_kind="GROUP",
            target_group_ids=group_ids,
        )

    raise PromotionDslError(f"Unsupported reward syntax: {source}")


def _parse_fields(raw_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line_no, raw_line in enumerate((raw_text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in raw_line:
            raise PromotionDslError(f"Invalid line {line_no}: expected key=value")
        key, value = raw_line.split("=", 1)
        normalized_key = key.strip().lower().lstrip("\ufeff")
        if not normalized_key:
            raise PromotionDslError(f"Invalid line {line_no}: empty field name")
        if normalized_key not in SUPPORTED_FIELDS:
            raise PromotionDslError(f"Unsupported field: {normalized_key}")
        if normalized_key in fields:
            raise PromotionDslError(f"Duplicate field: {normalized_key}")
        fields[normalized_key] = value.strip()
    return fields


def _parse_bool(value: str, field_name: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise PromotionDslError(f"Field {field_name} must be true or false")


def _parse_reward_mode(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"", "none", "нет"}:
        return "once"
    if normalized in {"once", "per_match"}:
        return normalized
    raise PromotionDslError("Field reward_mode must be once or per_match")


def _parse_dsl_version(value: str | None) -> int:
    text = (value or "").strip()
    if not text:
        return 1
    parsed = _parse_int(text, "dsl_version", allow_zero=False)
    if parsed not in {1, 2}:
        raise PromotionDslError("Field dsl_version must be 1 or 2")
    return parsed


def _parse_int(value: str, field_name: str, *, allow_zero: bool) -> int:
    text = (value or "").strip()
    if not text:
        raise PromotionDslError(f"Field {field_name} must not be empty")
    if text.startswith("-"):
        raise PromotionDslError(f"Field {field_name} must not be negative")
    try:
        parsed = int(text)
    except (TypeError, ValueError) as exc:
        raise PromotionDslError(f"Field {field_name} must be an integer") from exc
    if parsed == 0 and not allow_zero:
        raise PromotionDslError(f"Field {field_name} must be greater than zero")
    return parsed


def _parse_optional_int(value: str | None, field_name: str) -> int | None:
    if value is None or not str(value).strip():
        return None
    return _parse_int(str(value), field_name, allow_zero=False)


def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    try:
        return datetime.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise PromotionDslError(f"Field {field_name} must be a valid ISO timestamp") from exc


def _tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
            continue
        if (
            source.startswith(">=", index)
            or source.startswith("<=", index)
            or source.startswith("==", index)
            or source.startswith("!=", index)
        ):
            tokens.append(Token("OP", source[index:index + 2], index))
            index += 2
            continue
        if char in "=><(),.":
            tokens.append(Token("OP" if char in "=><" else char, char, index))
            index += 1
            continue
        if char.isdigit():
            end = index + 1
            while end < len(source) and source[end].isdigit():
                end += 1
            tokens.append(Token("NUMBER", source[index:end], index))
            index = end
            continue
        if char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (source[end].isalnum() or source[end] == "_"):
                end += 1
            word = source[index:end]
            keyword_value = word.upper()
            if keyword_value in KEYWORDS:
                tokens.append(Token("KEYWORD", keyword_value, index))
            else:
                tokens.append(Token("WORD", word, index))
            index = end
            continue
        raise PromotionDslError(f"Unknown token '{char}' in condition")
    tokens.append(Token("EOF", "", len(source)))
    return tokens


def _extract_function_payload(source: str, function_name: str) -> str | None:
    prefix = f"{function_name}("
    if not source.startswith(prefix) or not source.endswith(")"):
        return None
    return source[len(prefix):-1].strip()


def _split_csv(payload: str) -> list[str]:
    source = (payload or "").strip()
    if not source:
        return []
    parts: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(source):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise PromotionDslError("Invalid reward syntax: unbalanced parentheses")
        elif char == "," and depth == 0:
            parts.append(source[start:index].strip())
            start = index + 1
    if depth != 0:
        raise PromotionDslError("Invalid reward syntax: unbalanced parentheses")
    parts.append(source[start:].strip())
    if any(not part for part in parts):
        raise PromotionDslError("Invalid reward syntax: empty argument")
    return parts


def _parse_group_ids_payload(payload: str, *, field_name: str) -> tuple[int, ...]:
    parts = _split_csv(payload)
    if not parts:
        raise PromotionDslError(f"{field_name} must contain at least one item id")
    group_ids: list[int] = []
    seen: set[int] = set()
    for part in parts:
        item_id = _parse_int(part, f"{field_name} item id", allow_zero=False)
        if item_id in seen:
            raise PromotionDslError(f"{field_name} must not contain duplicate ids")
        seen.add(item_id)
        group_ids.append(item_id)
    return tuple(group_ids)


def _parse_discount_target(value: str) -> tuple[str, tuple[int, ...]]:
    token = (value or "").strip()
    if not token.startswith("TARGET="):
        raise PromotionDslError("Discount TARGET must be in format TARGET=ORDER or TARGET=GROUP(...)")
    target_value = token[len("TARGET="):].strip()
    if target_value == "ORDER":
        return "ORDER", ()
    if target_value.startswith("GROUP(") and target_value.endswith(")"):
        inner = target_value[6:-1].strip()
        return "GROUP", _parse_group_ids_payload(inner, field_name="TARGET GROUP")
    raise PromotionDslError("Discount TARGET must be ORDER or GROUP(...)")


def _parse_discount_reward_payload(payload: str, field_name: str, *, dsl_version: int) -> tuple[int, str, tuple[int, ...]]:
    parts = _split_csv(payload)
    if not parts:
        raise PromotionDslError(f"Field {field_name} must not be empty")
    amount = _parse_int(parts[0], field_name, allow_zero=False)
    if len(parts) == 1:
        return amount, "ORDER", ()
    if len(parts) > 2:
        raise PromotionDslError(f"{field_name} supports only value or value + TARGET")
    if dsl_version != 2:
        raise PromotionDslError(f"{field_name} with TARGET is supported only in DSL v2")
    target_kind, target_group_ids = _parse_discount_target(parts[1])
    return amount, target_kind, target_group_ids


class _ConditionParser:
    def __init__(self, tokens: list[Token], *, dsl_version: int):
        self.tokens = tokens
        self.index = 0
        self.dsl_version = dsl_version

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def expect(self, kind: str, value: str | None = None) -> Token:
        token = self.current
        if token.kind != kind or (value is not None and token.value != value):
            expected = value if value is not None else kind
            raise PromotionDslError(f"Expected {expected} in condition")
        self.index += 1
        return token

    def parse(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_and()
        while self.current.kind == "KEYWORD" and self.current.value == "OR":
            self.advance()
            node = ConditionGroup(operator="OR", left=node, right=self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while self.current.kind == "KEYWORD" and self.current.value == "AND":
            self.advance()
            node = ConditionGroup(operator="AND", left=node, right=self.parse_not())
        return node

    def parse_not(self):
        if self.current.kind == "KEYWORD" and self.current.value == "NOT":
            if self.dsl_version != 2:
                raise PromotionDslError("NOT operator is supported only in DSL v2")
            self.advance()
            return ConditionNot(operand=self.parse_not())
        return self.parse_primary()

    def parse_primary(self):
        if self.current.kind == "(":
            self.advance()
            node = self.parse_or()
            self.expect(")", ")")
            return node
        return self.parse_comparison()

    def parse_comparison(self):
        metric = self.parse_metric()
        operator = self.expect("OP").value
        allowed_operators = {"=", ">", "<", ">=", "<="} if self.dsl_version == 1 else {"==", "!=", ">", "<", ">=", "<="}
        if operator not in allowed_operators:
            raise PromotionDslError(f"Unsupported operator '{operator}'")
        value = _parse_int(self.expect("NUMBER").value, "condition number", allow_zero=True)
        return Comparison(metric=metric, operator=operator, value=value)

    def parse_metric(self) -> MetricRef:
        token = self.current
        if token.kind != "KEYWORD":
            raise PromotionDslError("Expected metric in condition")

        if token.value == "ID":
            self.advance()
            if self.current.kind == "(":
                self.advance()
                item_id = _parse_int(self.expect("NUMBER").value, "ID", allow_zero=False)
                self.expect(")", ")")
                self.expect(".", ".")
                field = self.expect("KEYWORD").value
                if field not in {"QTY", "SUM"}:
                    raise PromotionDslError("ID(n) metric must end with .QTY or .SUM")
                return MetricRef(target="item", item_id=item_id, field=field)

            self.expect(".", ".")
            all_fields = {"QTY", "SUM"} if self.dsl_version == 1 else {"QTY", "SUM", "UNIQUE_QTY"}
            if self.current.kind == "KEYWORD" and self.current.value in all_fields:
                field = self.advance().value
                return MetricRef(target="all_items", field=field)

            if self.dsl_version == 2:
                raise PromotionDslError("ID.<type> metric is not supported in DSL v2, use TYPE(<type>).QTY/SUM/UNIQUE_QTY")

            if self.current.kind not in {"WORD", "KEYWORD"}:
                raise PromotionDslError("ID.<type> metric must include a type name")
            item_type = self.advance().value
            self.expect(".", ".")
            field = self.expect("KEYWORD").value
            if field not in {"QTY", "SUM"}:
                raise PromotionDslError("ID.<type> metric must end with .QTY or .SUM")
            return MetricRef(target="type", item_type=item_type, field=field)

        if token.value == "TYPE":
            if self.dsl_version != 2:
                raise PromotionDslError("TYPE(...) metric is supported only in DSL v2")
            self.advance()
            self.expect("(", "(")
            if self.current.kind not in {"WORD", "KEYWORD"}:
                raise PromotionDslError("TYPE(...) metric must include a type name")
            item_type = self.advance().value
            self.expect(")", ")")
            self.expect(".", ".")
            field = self.expect("KEYWORD").value
            if field not in {"QTY", "SUM", "UNIQUE_QTY"}:
                raise PromotionDslError("TYPE(...) metric must end with .QTY, .SUM or .UNIQUE_QTY")
            return MetricRef(target="type", item_type=item_type, field=field)

        if token.value == "GROUP":
            self.advance()
            self.expect("(", "(")
            group_ids = self._parse_group_ids()
            self.expect(")", ")")
            if not group_ids:
                raise PromotionDslError("GROUP() must not be empty")
            self.expect(".", ".")
            fields = {"QTY", "SUM"} if self.dsl_version == 1 else {"QTY", "SUM", "UNIQUE_QTY"}
            field = self.expect("KEYWORD").value
            if field not in fields:
                if self.dsl_version == 1:
                    raise PromotionDslError("GROUP metric must end with .QTY or .SUM")
                raise PromotionDslError("GROUP metric must end with .QTY, .SUM or .UNIQUE_QTY")
            return MetricRef(target="group", group_ids=group_ids, field=field)

        if token.value == "ORDER":
            self.advance()
            self.expect(".", ".")
            field = self.expect("KEYWORD").value
            if self.dsl_version == 1:
                if field != "SUM":
                    raise PromotionDslError("ORDER metric supports only .SUM")
                return MetricRef(target="order", field="SUM")
            if field not in {"SUM", "SUBTOTAL"}:
                raise PromotionDslError("ORDER metric supports only .SUBTOTAL or .SUM")
            return MetricRef(target="order", field="SUBTOTAL")

        raise PromotionDslError(f"Unsupported metric root '{token.value}'")

    def _parse_group_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        seen: set[int] = set()
        while True:
            if self.current.kind == ")":
                break
            item_id = _parse_int(self.expect("NUMBER").value, "GROUP id", allow_zero=False)
            if item_id in seen:
                raise PromotionDslError("GROUP() must not contain duplicate ids")
            seen.add(item_id)
            ids.append(item_id)
            if self.current.kind == ",":
                self.advance()
                continue
            break
        return tuple(ids)
