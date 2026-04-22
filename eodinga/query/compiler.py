from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from itertools import product
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from eodinga.query.dsl import (
    AndNode,
    AstNode,
    OperatorNode,
    OrNode,
    PhraseNode,
    RegexNode,
    WordNode,
)
from eodinga.query.ranker import RankingWeights


class CompiledTextTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str
    kind: Literal["word", "phrase"] = "word"
    negated: bool = False


class CompiledRegexTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    pattern: str
    flags: str = ""
    negated: bool = False


class CompiledBranch(BaseModel):
    model_config = ConfigDict(frozen=True)

    path_match_sql: str | None = None
    path_match_params: tuple[str, ...] = ()
    content_match_sql: str | None = None
    content_match_params: tuple[str, ...] = ()
    where_sql: str = ""
    where_params: tuple[object, ...] = ()
    case_sensitive: bool = False
    regex_mode: bool = False
    path_terms: tuple[CompiledTextTerm, ...] = ()
    content_terms: tuple[CompiledTextTerm, ...] = ()
    path_regex_terms: tuple[CompiledRegexTerm, ...] = ()
    content_regex_terms: tuple[CompiledRegexTerm, ...] = ()
    path_filters: tuple[CompiledTextTerm, ...] = ()
    content_required: bool = False


class CompiledQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    branches: tuple[CompiledBranch, ...]
    weights: RankingWeights = Field(default_factory=RankingWeights)


def _to_dnf(node: AstNode) -> list[list[WordNode | PhraseNode | RegexNode | OperatorNode]]:
    if isinstance(node, (WordNode, PhraseNode, RegexNode, OperatorNode)):
        return [[node]]
    if isinstance(node, AndNode):
        branches: list[list[WordNode | PhraseNode | RegexNode | OperatorNode]] = [[]]
        for child in node.clauses:
            child_branches = _to_dnf(child)
            branches = [left + right for left, right in product(branches, child_branches)]
        return branches
    if isinstance(node, OrNode):
        branches: list[list[WordNode | PhraseNode | RegexNode | OperatorNode]] = []
        for child in node.clauses:
            branches.extend(_to_dnf(child))
        return branches
    raise TypeError(f"unsupported node: {type(node)!r}")


def _fts_literal(value: str, kind: Literal["word", "phrase"]) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def _size_to_bytes(value: str) -> tuple[str, int]:
    text = value.strip()
    comparator = "="
    for prefix in (">=", "<=", ">", "<", "="):
        if text.startswith(prefix):
            comparator = prefix
            text = text[len(prefix) :]
            break
    unit = text[-1].upper() if text and text[-1].isalpha() else "B"
    number_text = text[:-1] if unit != "B" or (text and text[-1].isalpha()) else text
    factor = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}.get(unit)
    if factor is None:
        raise ValueError(f"invalid size literal: {value}")
    return comparator, int(float(number_text) * factor)


def _day_bounds(day: date) -> tuple[int, int]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)
    return int(start.timestamp()), int(end.timestamp())


def _date_to_range(value: str) -> tuple[int, int]:
    today = datetime.now(tz=UTC).date()
    if value == "today":
        return _day_bounds(today)
    if value == "yesterday":
        return _day_bounds(today - timedelta(days=1))
    if value == "this-week":
        start = today - timedelta(days=today.weekday())
        return _day_bounds(start)[0], _day_bounds(start + timedelta(days=7))[0]
    if value == "this-month":
        start = today.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return _day_bounds(start)[0], _day_bounds(next_month)[0]
    if ".." in value:
        left, right = value.split("..", 1)
        start = datetime.fromisoformat(left).date()
        end = datetime.fromisoformat(right).date()
        return _day_bounds(start)[0], _day_bounds(end + timedelta(days=1))[0]
    day = datetime.fromisoformat(value).date()
    return _day_bounds(day)


def _compile_branch(
    terms: list[WordNode | PhraseNode | RegexNode | OperatorNode],
) -> CompiledBranch:
    where_parts: list[str] = []
    where_params: list[object] = []
    path_terms: list[CompiledTextTerm] = []
    content_terms: list[CompiledTextTerm] = []
    path_regex_terms: list[CompiledRegexTerm] = []
    content_regex_terms: list[CompiledRegexTerm] = []
    path_filters: list[CompiledTextTerm] = []
    case_sensitive = False
    regex_mode = False

    for term in terms:
        if isinstance(term, WordNode):
            path_terms.append(CompiledTextTerm(value=term.value, kind="word", negated=term.negated))
            continue
        if isinstance(term, PhraseNode):
            path_terms.append(
                CompiledTextTerm(value=term.value, kind="phrase", negated=term.negated)
            )
            continue
        if isinstance(term, RegexNode):
            path_regex_terms.append(
                CompiledRegexTerm(pattern=term.pattern, flags=term.flags, negated=term.negated)
            )
            continue
        if term.name == "content":
            if term.value_kind == "regex":
                content_regex_terms.append(
                    CompiledRegexTerm(
                        pattern=term.value, flags=term.regex_flags, negated=term.negated
                    )
                )
            else:
                content_terms.append(
                    CompiledTextTerm(
                        value=term.value, kind=term.value_kind, negated=term.negated
                    )
                )
            continue
        if term.name == "path":
            if term.value_kind == "regex":
                path_regex_terms.append(
                    CompiledRegexTerm(
                        pattern=term.value, flags=term.regex_flags, negated=term.negated
                    )
                )
            else:
                path_filters.append(
                    CompiledTextTerm(value=term.value, kind=term.value_kind, negated=term.negated)
                )
                comparator = "NOT LIKE" if term.negated else "LIKE"
                where_parts.append(f"files.path {comparator} ?")
                where_params.append(f"%{term.value}%")
            continue
        if term.name == "ext":
            comparator = "!=" if term.negated else "="
            where_parts.append(f"files.ext {comparator} ?")
            where_params.append(term.value.lower())
            continue
        if term.name in {"modified", "created"}:
            start, end = _date_to_range(term.value)
            column = "mtime" if term.name == "modified" else "ctime"
            if term.negated:
                where_parts.append(f"NOT (files.{column} >= ? AND files.{column} < ?)")
            else:
                where_parts.append(f"files.{column} >= ? AND files.{column} < ?")
            where_params.extend([start, end])
            continue
        if term.name == "size":
            comparator, size_bytes = _size_to_bytes(term.value)
            if term.negated:
                where_parts.append(f"NOT (files.size {comparator} ?)")
            else:
                where_parts.append(f"files.size {comparator} ?")
            where_params.append(size_bytes)
            continue
        if term.name == "is":
            normalized = term.value.lower()
            if normalized == "dir":
                clause = "files.is_dir = 1"
            elif normalized == "file":
                clause = "files.is_dir = 0"
            elif normalized == "symlink":
                clause = "files.is_symlink = 1"
            else:
                raise ValueError(f"invalid is: value: {term.value}")
            where_parts.append(f"NOT ({clause})" if term.negated else clause)
            continue
        if term.name == "case":
            case_sensitive = _parse_bool(term.value)
            continue
        if term.name == "regex":
            regex_mode = _parse_bool(term.value)
            continue
        raise ValueError(f"unsupported operator: {term.name}")

    positive_path_terms = tuple(term for term in path_terms if not term.negated)
    positive_content_terms = tuple(term for term in content_terms if not term.negated)
    path_match_sql = "paths_fts MATCH ?" if positive_path_terms else None
    content_match_sql = "content_fts MATCH ?" if positive_content_terms else None
    path_query = " ".join(_fts_literal(term.value, term.kind) for term in positive_path_terms)
    content_query = " ".join(_fts_literal(term.value, term.kind) for term in positive_content_terms)
    return CompiledBranch(
        path_match_sql=path_match_sql,
        path_match_params=((path_query,) if path_query else ()),
        content_match_sql=content_match_sql,
        content_match_params=((content_query,) if content_query else ()),
        where_sql=" AND ".join(where_parts),
        where_params=tuple(where_params),
        case_sensitive=case_sensitive,
        regex_mode=regex_mode,
        path_terms=tuple(path_terms),
        content_terms=tuple(content_terms),
        path_regex_terms=tuple(path_regex_terms),
        content_regex_terms=tuple(content_regex_terms),
        path_filters=tuple(path_filters),
        content_required=bool(content_terms or content_regex_terms),
    )


def compile_query(ast: AstNode) -> CompiledQuery:
    branches = tuple(_compile_branch(branch) for branch in _to_dnf(ast))
    return CompiledQuery(branches=branches)


__all__ = [
    "CompiledBranch",
    "CompiledQuery",
    "CompiledRegexTerm",
    "CompiledTextTerm",
    "compile_query",
]
