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
        return WordNode(value=node.value, negated=not node.negated)
    if isinstance(node, PhraseNode):
        return PhraseNode(value=node.value, negated=not node.negated)
    if isinstance(node, RegexNode):
        return RegexNode(pattern=node.pattern, flags=node.flags, negated=not node.negated)
    return OperatorNode(
        name=node.name,
        value=node.value,
        value_kind=node.value_kind,
        regex_flags=node.regex_flags,
        negated=not node.negated,
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


def _has_non_ascii(value: str) -> bool:
    return any(ord(char) > 127 for char in value)


def _parse_bool(value: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise QuerySyntaxError(f"invalid boolean value: {value}", 0)


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


def _validate_regex_pattern(pattern: str, flags: str = "") -> None:
    try:
        re.compile(pattern, _regex_flags(flags))
    except re.error as error:
        raise QuerySyntaxError(f"invalid regex: {error}", 0) from error


def _parse_size_number(number_text: str, unit: str, original: str) -> int:
    factor = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}.get(unit)
    if factor is None:
        raise QuerySyntaxError(f"invalid size literal: {original}", 0)
    try:
        return int(float(number_text) * factor)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid size literal: {original}", 0) from error


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
    return comparator, _parse_size_number(number_text, unit, value)


def _size_to_range(value: str) -> tuple[int | None, int | None] | None:
    if ".." not in value:
        return None
    left, right = (part.strip() for part in value.split("..", 1))
    if not left and not right:
        raise QuerySyntaxError(f"invalid size literal: {value}", 0)
    start = None
    end = None
    if left:
        left_unit = left[-1].upper() if left[-1].isalpha() else "B"
        left_number = left[:-1] if left[-1].isalpha() else left
        start = _parse_size_number(left_number, left_unit, value)
    if right:
        right_unit = right[-1].upper() if right[-1].isalpha() else "B"
        right_number = right[:-1] if right[-1].isalpha() else right
        end = _parse_size_number(right_number, right_unit, value)
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


def _normalize_is_value(value: str) -> str:
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
        raise QuerySyntaxError(f"invalid is: value: {value}", 0) from error


def _empty_clause(negated: bool) -> str:
    clause = (
        "("
        "(files.is_dir = 0 AND files.is_symlink = 0 AND files.size = 0) OR "
        "("
        "files.is_dir = 1 AND files.is_symlink = 0 AND NOT EXISTS ("
        "SELECT 1 FROM files AS descendants "
        "WHERE descendants.id != files.id "
        "AND (descendants.path LIKE (files.path || '/%') "
        "OR descendants.path LIKE (files.path || '\\%'))"
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
                )
            )
            continue
        if isinstance(term, PhraseNode):
            path_terms.append(
                CompiledTextTerm(
                    value=_normalize_literal(term.value),
                    kind="phrase",
                    negated=term.negated,
                )
            )
            continue
        if isinstance(term, RegexNode):
            _validate_regex_pattern(term.pattern, term.flags)
            path_regex_terms.append(
                CompiledRegexTerm(pattern=term.pattern, flags=term.flags, negated=term.negated)
            )
            continue
        if term.name == "content":
            if term.value_kind == "regex":
                _validate_regex_pattern(term.value, term.regex_flags)
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
                    )
                )
            continue
        if term.name == "path":
            if term.value_kind == "regex":
                _validate_regex_pattern(term.value, term.regex_flags)
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
                    )
                )
                if not _has_non_ascii(normalized_value):
                    comparator = "NOT LIKE" if term.negated else "LIKE"
                    where_parts.append(f"files.path {comparator} ?")
                    where_params.append(f"%{normalized_value}%")
            continue
        if term.name == "ext":
            comparator = "!=" if term.negated else "="
            where_parts.append(f"files.ext {comparator} ?")
            where_params.append(term.value.lower())
            continue
        if term.name in {"date", "modified", "created"}:
            range_bounds = parse_date_range(term.value)
            column = "ctime" if term.name == "created" else "mtime"
            clauses: list[str] = []
            if range_bounds.start is not None:
                clauses.append(f"files.{column} >= ?")
                where_params.append(range_bounds.start)
            if range_bounds.end is not None:
                clauses.append(f"files.{column} < ?")
                where_params.append(range_bounds.end)
            if not clauses:
                raise QuerySyntaxError(f"invalid date literal: {term.value}", 0)
            clause_sql = " AND ".join(clauses)
            where_parts.append(f"NOT ({clause_sql})" if term.negated else clause_sql)
            continue
        if term.name == "size":
            size_range = _size_to_range(term.value)
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
                where_parts.append(f"NOT ({clause_sql})" if term.negated else clause_sql)
                continue
            comparator, size_bytes = _size_to_bytes(term.value)
            if term.negated:
                where_parts.append(f"NOT (files.size {comparator} ?)")
            else:
                where_parts.append(f"files.size {comparator} ?")
            where_params.append(size_bytes)
            continue
        if term.name == "is":
            normalized = _normalize_is_value(term.value)
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
            case_sensitive = _parse_bool(term.value)
            if term.negated:
                case_sensitive = not case_sensitive
            continue
        if term.name == "regex":
            regex_mode = _parse_bool(term.value)
            if term.negated:
                regex_mode = not regex_mode
            continue
        raise QuerySyntaxError(f"unsupported operator: {term.name}", 0)

    if regex_mode and path_terms:
        regex_terms = []
        for term in path_terms:
            _validate_regex_pattern(term.value)
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
