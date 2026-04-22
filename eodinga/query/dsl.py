from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

OP_NAMES = {
    "date",
    "ext",
    "path",
    "size",
    "modified",
    "created",
    "is",
    "content",
    "case",
    "regex",
}


class QueryNode(BaseModel):
    model_config = ConfigDict(frozen=True)


class TermNode(QueryNode):
    negated: bool = False


class WordNode(TermNode):
    kind: Literal["word"] = "word"
    value: str


class PhraseNode(TermNode):
    kind: Literal["phrase"] = "phrase"
    value: str


class RegexNode(TermNode):
    kind: Literal["regex"] = "regex"
    pattern: str
    flags: str = ""


class OperatorNode(TermNode):
    kind: Literal["operator"] = "operator"
    name: str
    value: str
    value_kind: Literal["word", "phrase", "regex"] = "word"
    regex_flags: str = ""


class AndNode(QueryNode):
    kind: Literal["and"] = "and"
    clauses: tuple[AstNode, ...]


class OrNode(QueryNode):
    kind: Literal["or"] = "or"
    clauses: tuple[AstNode, ...]


class NotNode(QueryNode):
    kind: Literal["not"] = "not"
    clause: AstNode


AstNode = WordNode | PhraseNode | RegexNode | OperatorNode | AndNode | OrNode | NotNode


class QuerySyntaxError(ValueError):
    def __init__(self, message: str, position: int) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:
        return f"{self.message} at position {self.position}"


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.index = 0

    def parse(self) -> AstNode:
        self._skip_ws()
        if self.index >= self.length:
            raise QuerySyntaxError("query is empty", 0)
        node = self._parse_or_expr()
        self._skip_ws()
        if self.index != self.length:
            raise QuerySyntaxError("unexpected token", self.index)
        return node

    def _parse_or_expr(self) -> AstNode:
        clauses = [self._parse_and_expr()]
        self._skip_ws()
        while self._peek() == "|":
            self.index += 1
            self._skip_ws()
            clauses.append(self._parse_and_expr())
            self._skip_ws()
        return clauses[0] if len(clauses) == 1 else OrNode(clauses=tuple(clauses))

    def _parse_and_expr(self) -> AstNode:
        clauses = [self._parse_term()]
        while True:
            ws_start = self.index
            consumed = self._skip_ws()
            current = self._peek()
            if not consumed or current in (None, "|", ")"):
                self.index = ws_start if current in ("|", ")") else self.index
                break
            clauses.append(self._parse_term())
        return clauses[0] if len(clauses) == 1 else AndNode(clauses=tuple(clauses))

    def _parse_term(self) -> AstNode:
        self._skip_ws()
        negated = False
        if self._peek() == "-":
            negated = True
            self.index += 1
            self._skip_ws()
        char = self._peek()
        if char is None:
            raise QuerySyntaxError("expected term", self.index)
        if char == "(":
            self.index += 1
            inner = self._parse_or_expr()
            self._skip_ws()
            if self._peek() != ")":
                raise QuerySyntaxError("expected closing ')'", self.index)
            self.index += 1
            return NotNode(clause=inner) if negated else inner
        if char == '"':
            return self._with_negation(self._parse_phrase(), negated)
        if char == "/":
            return self._with_negation(self._parse_regex(), negated)
        token_start = self.index
        token = self._read_token()
        if not token:
            raise QuerySyntaxError("expected term", self.index)
        if ":" in token:
            name, raw = token.split(":", 1)
            if name in OP_NAMES:
                if (raw.startswith('"') and not raw.endswith('"')) or (
                    raw.startswith("/") and raw.count("/") < 2
                ):
                    self.index = token_start + len(name) + 1
                    return self._parse_operator(name, "", negated)
                return self._parse_operator(name, raw, negated)
        return WordNode(value=token, negated=negated)

    def _parse_operator(self, name: str, initial_value: str, negated: bool) -> OperatorNode:
        if initial_value:
            value, value_kind, regex_flags = self._decode_inline_value(name, initial_value)
            return OperatorNode(
                name=name,
                value=value,
                value_kind=value_kind,
                regex_flags=regex_flags,
                negated=negated,
            )
        self._skip_ws()
        char = self._peek()
        if char is None:
            raise QuerySyntaxError("expected operator value", self.index)
        if char == '"':
            phrase = self._parse_phrase()
            return OperatorNode(name=name, value=phrase.value, value_kind="phrase", negated=negated)
        if char == "/":
            regex = self._parse_regex()
            return OperatorNode(
                name=name,
                value=regex.pattern,
                value_kind="regex",
                regex_flags=regex.flags,
                negated=negated,
            )
        value = self._read_token()
        if not value:
            raise QuerySyntaxError("expected operator value", self.index)
        return OperatorNode(name=name, value=value, value_kind="word", negated=negated)

    def _parse_phrase(self) -> PhraseNode:
        start = self.index
        if self._peek() != '"':
            raise QuerySyntaxError('expected \'"\'', start)
        self.index += 1
        phrase_start = self.index
        while self._peek() not in ('"', None):
            self.index += 1
        if self._peek() != '"':
            raise QuerySyntaxError("unterminated phrase", start)
        value = self.source[phrase_start:self.index]
        self.index += 1
        if not value:
            raise QuerySyntaxError("empty phrase", phrase_start)
        return PhraseNode(value=value)

    def _parse_regex(self) -> RegexNode:
        start = self.index
        if self._peek() != "/":
            raise QuerySyntaxError("expected regex", start)
        self.index += 1
        pattern_start = self.index
        while True:
            char = self._peek()
            if char is None:
                raise QuerySyntaxError("unterminated regex", start)
            if char == "/" and self.source[self.index - 1] != "\\":
                break
            self.index += 1
        pattern = self.source[pattern_start:self.index]
        self.index += 1
        flags_start = self.index
        while (char := self._peek()) is not None and char.isalpha():
            self.index += 1
        if not pattern:
            raise QuerySyntaxError("empty regex", pattern_start)
        flags = self.source[flags_start:self.index]
        self._validate_regex_flags(flags, flags_start)
        return RegexNode(pattern=pattern, flags=flags)

    def _decode_inline_value(
        self, name: str, value: str
    ) -> tuple[str, Literal["word", "phrase", "regex"], str]:
        if value.startswith('"'):
            start = self.index - len(value)
            if not value.endswith('"') or len(value) == 1:
                raise QuerySyntaxError("unterminated phrase", start)
            return value[1:-1], "phrase", ""
        if value.startswith("/"):
            delimiters = self._regex_delimiters(value)
            if len(delimiters) < 2 or value.endswith("\\"):
                raise QuerySyntaxError("unterminated regex", self.index - len(value))
            last = delimiters[-1]
            pattern = value[1:last]
            if not pattern:
                raise QuerySyntaxError("empty regex", self.index - len(value) + 1)
            suffix = value[last + 1 :]
            if suffix and (len(suffix) > 3 or not suffix.isalpha()):
                return value, "word", ""
            if name == "path" and value.startswith("/") and (len(delimiters) < 3 or not suffix):
                return value, "word", ""
            if name == "path" and suffix:
                try:
                    self._validate_regex_flags(suffix, self.index - len(value) + last + 1)
                except QuerySyntaxError:
                    return value, "word", ""
            flags = suffix
            self._validate_regex_flags(flags, self.index - len(value) + last + 1)
            return pattern, "regex", flags
        return value, "word", ""

    def _regex_delimiters(self, value: str) -> list[int]:
        delimiters: list[int] = []
        backslashes = 0
        for index, char in enumerate(value):
            if char == "\\":
                backslashes += 1
                continue
            if char == "/" and backslashes % 2 == 0:
                delimiters.append(index)
            backslashes = 0
        return delimiters

    def _with_negation(self, node: PhraseNode | RegexNode, negated: bool) -> PhraseNode | RegexNode:
        if not negated:
            return node
        if isinstance(node, PhraseNode):
            return PhraseNode(value=node.value, negated=True)
        return RegexNode(pattern=node.pattern, flags=node.flags, negated=True)

    def _read_token(self) -> str:
        start = self.index
        while (char := self._peek()) is not None and char not in '()|"':
            if char.isspace():
                break
            self.index += 1
        return self.source[start:self.index]

    def _peek(self) -> str | None:
        if self.index >= self.length:
            return None
        return self.source[self.index]

    def _skip_ws(self) -> bool:
        start = self.index
        while (char := self._peek()) is not None and char.isspace():
            self.index += 1
        return self.index > start

    def _validate_regex_flags(self, flags: str, position: int) -> None:
        allowed = {"i", "m", "s"}
        seen: set[str] = set()
        for offset, flag in enumerate(flags.lower()):
            if flag not in allowed:
                raise QuerySyntaxError(f"unsupported regex flag: {flags[offset]}", position + offset)
            if flag in seen:
                raise QuerySyntaxError(f"duplicate regex flag: {flags[offset]}", position + offset)
            seen.add(flag)


def parse(source: str) -> AstNode:
    return _Parser(source).parse()


__all__ = [
    "AndNode",
    "AstNode",
    "NotNode",
    "OperatorNode",
    "OrNode",
    "PhraseNode",
    "QuerySyntaxError",
    "RegexNode",
    "WordNode",
    "parse",
]
