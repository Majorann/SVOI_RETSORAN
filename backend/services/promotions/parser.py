from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ast import Comparison, ConditionGroup, MetricRef, PromotionDefinition, PromotionDslError, Reward


SUPPORTED_FIELDS = {
    "type",
    "name",
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

    return PromotionDefinition(
        promotion_type=fields.get("type", "akciya"),
        name=fields.get("name", "").strip(),
        active=_parse_bool(fields.get("active", "true"), "active"),
        priority=_parse_int(fields.get("priority", "0"), "priority", allow_zero=True),
        condition=parse_condition(fields["condition"]),
        reward=parse_reward(fields["reward"]),
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


def parse_condition(text: str):
    tokens = _tokenize(text)
    parser = _ConditionParser(tokens)
    result = parser.parse()
    if parser.current.kind != "EOF":
        raise PromotionDslError(f"Unexpected token '{parser.current.value}' in condition")
    return result


def parse_reward(text: str) -> Reward:
    source = (text or "").strip()
    if not source:
        raise PromotionDslError("Reward must not be empty")

    if source.startswith("POINTS(") and source.endswith(")"):
        return Reward(kind="POINTS", amount=_parse_int(source[7:-1].strip(), "POINTS", allow_zero=False))
    if source.startswith("DISCOUNT_PERCENT(") and source.endswith(")"):
        return Reward(
            kind="DISCOUNT_PERCENT",
            amount=_parse_int(source[17:-1].strip(), "DISCOUNT_PERCENT", allow_zero=False),
        )
    if source.startswith("DISCOUNT_RUB(") and source.endswith(")"):
        return Reward(
            kind="DISCOUNT_RUB",
            amount=_parse_int(source[13:-1].strip(), "DISCOUNT_RUB", allow_zero=False),
        )
    if source.startswith("GIFT(") and source.endswith(")"):
        payload = source[5:-1].strip()
        parts = [part.strip() for part in payload.split(",")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise PromotionDslError("GIFT reward must be in format GIFT(id, qty)")
        return Reward(
            kind="GIFT",
            item_id=_parse_int(parts[0], "GIFT item id", allow_zero=False),
            qty=_parse_int(parts[1], "GIFT qty", allow_zero=False),
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
        normalized_key = key.strip().lower()
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
    if normalized in {"once", "per_match"}:
        return normalized
    raise PromotionDslError("Field reward_mode must be once or per_match")


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
        if source.startswith(">=", index) or source.startswith("<=", index):
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
            kind = "KEYWORD" if word in {"AND", "OR", "ID", "GROUP", "ORDER", "QTY", "SUM"} else "WORD"
            tokens.append(Token(kind, word, index))
            index = end
            continue
        raise PromotionDslError(f"Unknown token '{char}' in condition")
    tokens.append(Token("EOF", "", len(source)))
    return tokens


class _ConditionParser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

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
        node = self.parse_primary()
        while self.current.kind == "KEYWORD" and self.current.value == "AND":
            self.advance()
            node = ConditionGroup(operator="AND", left=node, right=self.parse_primary())
        return node

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
        if operator not in {"=", ">", "<", ">=", "<="}:
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
            if self.current.kind == "KEYWORD" and self.current.value in {"QTY", "SUM"}:
                field = self.advance().value
                return MetricRef(target="all_items", field=field)
            if self.current.kind != "WORD":
                raise PromotionDslError("ID.<type> metric must include a type name")
            item_type = self.advance().value
            self.expect(".", ".")
            field = self.expect("KEYWORD").value
            if field not in {"QTY", "SUM"}:
                raise PromotionDslError("ID.<type> metric must end with .QTY or .SUM")
            return MetricRef(target="type", item_type=item_type, field=field)

        if token.value == "GROUP":
            self.advance()
            self.expect("(", "(")
            group_ids: list[int] = []
            while True:
                if self.current.kind == ")":
                    break
                group_ids.append(_parse_int(self.expect("NUMBER").value, "GROUP id", allow_zero=False))
                if self.current.kind == ",":
                    self.advance()
                    continue
                break
            self.expect(")", ")")
            if not group_ids:
                raise PromotionDslError("GROUP() must not be empty")
            self.expect(".", ".")
            field = self.expect("KEYWORD").value
            if field not in {"QTY", "SUM"}:
                raise PromotionDslError("GROUP metric must end with .QTY or .SUM")
            return MetricRef(target="group", group_ids=tuple(group_ids), field=field)

        if token.value == "ORDER":
            self.advance()
            self.expect(".", ".")
            field = self.expect("KEYWORD").value
            if field != "SUM":
                raise PromotionDslError("ORDER metric supports only .SUM")
            return MetricRef(target="order", field="SUM")

        raise PromotionDslError(f"Unsupported metric root '{token.value}'")
