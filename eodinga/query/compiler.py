from __future__ import annotations

import re
import unicodedata
from itertools import product
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from eodinga.query.dsl import (
    AndNode,
    AstNode,
    NotNode,
    OperatorNode,
    OrNode,
    PhraseNode,
    QuerySyntaxError,
    RegexNode,
    WordNode,
)
from eodinga.query.date_range import parse_date_range
from eodinga.query.ranker import RankingWeights


class CompiledTextTerm(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str
    kind: Literal["word", "phrase"] = "word"
    negated: bool = False
    position: int = 0


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
    if isinstance(node, NotNode):
        raise TypeError("compile_query expected negations to be normalized")
    raise TypeError(f"unsupported node: {type(node)!r}")


def _negate_term(node: WordNode | PhraseNode | RegexNode | OperatorNode) -> AstNode:
    if isinstance(node, WordNode):
        return WordNode(value=node.value, negated=not node.negated, position=node.position)
    if isinstance(node, PhraseNode):
        return PhraseNode(value=node.value, negated=not node.negated, position=node.position)
    if isinstance(node, RegexNode):
        return RegexNode(
            pattern=node.pattern,
            flags=node.flags,
            negated=not node.negated,
            position=node.position,
            pattern_position=node.pattern_position,
        )
    return OperatorNode(
        name=node.name,
        value=node.value,
        value_kind=node.value_kind,
        regex_flags=node.regex_flags,
        negated=not node.negated,
        position=node.position,
        value_position=node.value_position,
    )


def _to_nnf(node: AstNode, negated: bool = False) -> AstNode:
    if isinstance(node, (WordNode, PhraseNode, RegexNode, OperatorNode)):
        return _negate_term(node) if negated else node
    if isinstance(node, NotNode):
        return _to_nnf(node.clause, not negated)
    if isinstance(node, AndNode):
        clauses = tuple(_to_nnf(child, negated) for child in node.clauses)
        return OrNode(clauses=clauses) if negated else AndNode(clauses=clauses)
    if isinstance(node, OrNode):
        clauses = tuple(_to_nnf(child, negated) for child in node.clauses)
        return AndNode(clauses=clauses) if negated else OrNode(clauses=clauses)
    raise TypeError(f"unsupported node: {type(node)!r}")


def _fts_literal(value: str, kind: Literal["word", "phrase"]) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _normalize_literal(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _escape_like_pattern(value: str) -> str:
    return value.replace("^", "^^").replace("%", "^%").replace("_", "^_")


def _escaped_like_sql(expr: str) -> str:
    return (
        f"REPLACE(REPLACE(REPLACE({expr}, '^', '^^'), '%', '^%'), '_', '^_')"
    )


def _has_non_ascii(value: str) -> bool:
    return any(ord(char) > 127 for char in value)


def _parse_bool(value: str, *, position: int = 0) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise QuerySyntaxError(f"invalid boolean value: {value}", position)


def _try_parse_bool(value: str, *, position: int = 0) -> bool | None:
    try:
        return _parse_bool(value, position=position)
    except QuerySyntaxError:
        return None


def _regex_flags(flags: str) -> int:
    compiled_flags = 0
    for flag in flags.lower():
        if flag == "i":
            compiled_flags |= re.IGNORECASE
        elif flag == "m":
            compiled_flags |= re.MULTILINE
        elif flag == "s":
            compiled_flags |= re.DOTALL
    return compiled_flags


def _validate_regex_pattern(pattern: str, flags: str = "", *, position: int = 0) -> None:
    try:
        re.compile(pattern, _regex_flags(flags))
    except re.error as error:
        raise QuerySyntaxError(f"invalid regex: {error}", position) from error


def _parse_size_number(number_text: str, unit: str, original: str, *, position: int = 0) -> int:
    normalized_unit = unit.strip().casefold()
    factor = {
        "": 1,
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "k": 1024,
        "kb": 1024,
        "kib": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "mib": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
        "gib": 1024**3,
        "t": 1024**4,
        "tb": 1024**4,
        "tib": 1024**4,
    }.get(normalized_unit)
    if factor is None:
        raise QuerySyntaxError(f"invalid size literal: {original}", position)
    try:
        return int(float(number_text) * factor)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid size literal: {original}", position) from error


def _size_to_bytes(value: str, *, position: int = 0) -> tuple[str, int]:
    text = value.strip()
    comparator = "="
    number_position = position
    for prefix in (">=", "<=", ">", "<", "="):
        if text.startswith(prefix):
            comparator = prefix
            text = text[len(prefix) :]
            number_position += len(prefix)
            break
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)(?P<unit>[A-Za-z]*)", text)
    if match is None:
        raise QuerySyntaxError(f"invalid size literal: {value}", position)
    return comparator, _parse_size_number(
        match.group("number"),
        match.group("unit"),
        value,
        position=number_position,
    )


def _size_endpoint_to_bytes(value: str, original: str, *, position: int = 0) -> int:
    text = value.strip()
    if any(text.startswith(prefix) for prefix in (">=", "<=", ">", "<", "=")):
        raise QuerySyntaxError(f"invalid size literal: {original}", position)
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)(?P<unit>[A-Za-z]*)", text)
    if match is None:
        raise QuerySyntaxError(f"invalid size literal: {original}", position)
    return _parse_size_number(match.group("number"), match.group("unit"), original, position=position)


def _size_to_range(value: str, *, position: int = 0) -> tuple[int | None, int | None] | None:
    if ".." not in value:
        return None
    left, right = (part.strip() for part in value.split("..", 1))
    if not left and not right:
        raise QuerySyntaxError(f"invalid size literal: {value}", position)
    left_position = position
    right_position = position + value.index("..") + 2
    start = _size_endpoint_to_bytes(left, value, position=left_position) if left else None
    end = _size_endpoint_to_bytes(right, value, position=right_position) if right else None
    if start is not None and end is not None and end < start:
        start, end = end, start
    return start, end


def _duplicate_clause(negated: bool) -> str:
    clause = (
        "files.content_hash IS NOT NULL AND EXISTS ("
        "SELECT 1 FROM files AS duplicates "
        "WHERE duplicates.content_hash = files.content_hash "
        "AND duplicates.id != files.id)"
    )
    return f"NOT ({clause})" if negated else clause


def _normalize_is_value(value: str, *, position: int = 0) -> str:
    normalized = value.strip().casefold().replace("_", "-")
    aliases = {
        "dir": "dir",
        "directory": "dir",
        "folder": "dir",
        "file": "file",
        "symlink": "symlink",
        "link": "symlink",
        "empty": "empty",
        "duplicate": "duplicate",
        "dup": "duplicate",
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise QuerySyntaxError(f"invalid is: value: {value}", position) from error


def _empty_clause(negated: bool) -> str:
    escaped_path = _escaped_like_sql("files.path")
    clause = (
        "("
        "(files.is_dir = 0 AND files.size = 0) OR "
        "("
        "files.is_dir = 1 AND NOT EXISTS ("
        "SELECT 1 FROM files AS descendants "
        "WHERE descendants.id != files.id "
        f"AND (descendants.path LIKE ({escaped_path} || '/%') ESCAPE '^' "
        f"OR descendants.path LIKE ({escaped_path} || '\\%') ESCAPE '^')"
        ")"
        ")"
        ")"
    )
    return f"NOT ({clause})" if negated else clause


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
            path_terms.append(
                CompiledTextTerm(
                    value=_normalize_literal(term.value),
                    kind="word",
                    negated=term.negated,
                    position=term.position,
                )
            )
            continue
        if isinstance(term, PhraseNode):
            path_terms.append(
                CompiledTextTerm(
                    value=_normalize_literal(term.value),
                    kind="phrase",
                    negated=term.negated,
                    position=term.position,
                )
            )
            continue
        if isinstance(term, RegexNode):
            _validate_regex_pattern(term.pattern, term.flags, position=term.pattern_position)
            path_regex_terms.append(
                CompiledRegexTerm(pattern=term.pattern, flags=term.flags, negated=term.negated)
            )
            continue
        if term.name == "content":
            if term.value_kind == "regex":
                _validate_regex_pattern(term.value, term.regex_flags, position=term.value_position + 1)
                content_regex_terms.append(
                    CompiledRegexTerm(
                        pattern=term.value, flags=term.regex_flags, negated=term.negated
                    )
                )
            else:
                content_terms.append(
                    CompiledTextTerm(
                        value=_normalize_literal(term.value),
                        kind=term.value_kind,
                        negated=term.negated,
                        position=term.value_position,
                    )
                )
            continue
        if term.name == "path":
            if term.value_kind == "regex":
                _validate_regex_pattern(term.value, term.regex_flags, position=term.value_position + 1)
                path_regex_terms.append(
                    CompiledRegexTerm(
                        pattern=term.value, flags=term.regex_flags, negated=term.negated
                    )
                )
            else:
                normalized_value = _normalize_literal(term.value)
                path_filters.append(
                    CompiledTextTerm(
                        value=normalized_value,
                        kind=term.value_kind,
                        negated=term.negated,
                        position=term.value_position,
                    )
                )
                if not _has_non_ascii(normalized_value):
                    comparator = "NOT LIKE" if term.negated else "LIKE"
                    where_parts.append(f"files.path {comparator} ? ESCAPE '^'")
                    where_params.append(f"%{_escape_like_pattern(normalized_value)}%")
            continue
        if term.name == "ext":
            comparator = "!=" if term.negated else "="
            where_parts.append(f"files.ext {comparator} ?")
            where_params.append(term.value.lower())
            continue
        if term.name in {"date", "modified", "created"}:
            range_bounds = parse_date_range(term.value, position=term.value_position)
            column = "ctime" if term.name == "created" else "mtime"
            clauses: list[str] = []
            if range_bounds.start is not None:
                clauses.append(f"files.{column} >= ?")
                where_params.append(range_bounds.start)
            if range_bounds.end is not None:
                clauses.append(f"files.{column} < ?")
                where_params.append(range_bounds.end)
            if not clauses:
                raise QuerySyntaxError(f"invalid date literal: {term.value}", term.value_position)
            clause_sql = " AND ".join(clauses)
            where_parts.append(f"NOT ({clause_sql})" if term.negated else clause_sql)
            continue
        if term.name == "size":
            size_range = _size_to_range(term.value, position=term.value_position)
            if size_range is not None:
                start, end = size_range
                clauses: list[str] = []
                if start is not None:
                    clauses.append("files.size >= ?")
                    where_params.append(start)
                if end is not None:
                    clauses.append("files.size <= ?")
                    where_params.append(end)
                clause_sql = " AND ".join(clauses)
                if term.negated:
                    where_parts.append(f"NOT ({clause_sql})")
                else:
                    where_parts.append(clause_sql)
                continue
            comparator, size_bytes = _size_to_bytes(term.value, position=term.value_position)
            if term.negated:
                where_parts.append(f"NOT (files.size {comparator} ?)")
            else:
                where_parts.append(f"files.size {comparator} ?")
            where_params.append(size_bytes)
            continue
        if term.name == "is":
            normalized = _normalize_is_value(term.value, position=term.value_position)
            if normalized == "dir":
                clause = "files.is_dir = 1 AND files.is_symlink = 0"
            elif normalized == "file":
                clause = "files.is_dir = 0 AND files.is_symlink = 0"
            elif normalized == "symlink":
                clause = "files.is_symlink = 1"
            elif normalized == "empty":
                where_parts.append(_empty_clause(term.negated))
                continue
            elif normalized == "duplicate":
                clause = _duplicate_clause(term.negated)
                where_parts.append(clause)
                continue
            where_parts.append(f"NOT ({clause})" if term.negated else clause)
            continue
        if term.name == "case":
            case_sensitive = _parse_bool(term.value, position=term.value_position)
            if term.negated:
                case_sensitive = not case_sensitive
            continue
        if term.name == "regex":
            bool_value = (
                _try_parse_bool(term.value, position=term.value_position)
                if term.value_kind == "word"
                else None
            )
            if bool_value is not None:
                regex_mode = bool_value
                if term.negated:
                    regex_mode = not regex_mode
                continue
            _validate_regex_pattern(term.value, term.regex_flags, position=term.value_position + 1)
            path_regex_terms.append(
                CompiledRegexTerm(
                    pattern=term.value,
                    flags=term.regex_flags,
                    negated=term.negated,
                )
            )
            continue
        raise QuerySyntaxError(f"unsupported operator: {term.name}", 0)

    if regex_mode and path_terms:
        regex_terms = []
        for term in path_terms:
            _validate_regex_pattern(term.value, position=term.position)
            regex_terms.append(
                CompiledRegexTerm(pattern=term.value, flags="", negated=term.negated)
            )
        path_regex_terms.extend(regex_terms)
        path_terms = []

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
    normalized = _to_nnf(ast)
    branches = tuple(_compile_branch(branch) for branch in _to_dnf(normalized))
    return CompiledQuery(branches=branches)


__all__ = [
    "CompiledBranch",
    "CompiledQuery",
    "CompiledRegexTerm",
    "CompiledTextTerm",
    "compile_query",
]
