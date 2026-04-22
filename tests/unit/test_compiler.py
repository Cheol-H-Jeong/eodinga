from __future__ import annotations

import pytest

from eodinga.query import compile
from eodinga.query.compiler import compile_query
from eodinga.query.dsl import QuerySyntaxError, parse


def test_compile_text_query_shape() -> None:
    compiled = compile_query(parse('report ext:pdf size:>10M modified:2026-01-01'))
    branch = compiled.branches[0]
    assert branch.path_match_sql == "paths_fts MATCH ?"
    assert branch.path_match_params == ('"report"',)
    assert branch.where_sql.count("?") == 4
    assert "files.ext = ?" in branch.where_sql
    assert "files.size > ?" in branch.where_sql
    assert "files.mtime >= ? AND files.mtime < ?" in branch.where_sql


def test_compile_content_query_shape() -> None:
    compiled = compile_query(parse('content:"hello world" -path:node_modules'))
    branch = compiled.branches[0]
    assert branch.content_match_sql == "content_fts MATCH ?"
    assert branch.content_match_params == ('"hello world"',)
    assert "files.path NOT LIKE ?" in branch.where_sql


def test_compile_or_to_multiple_branches() -> None:
    compiled = compile_query(parse("(alpha | beta) ext:txt"))
    assert len(compiled.branches) == 2
    assert all(branch.where_params == ("txt",) for branch in compiled.branches)


def test_compile_regex_and_case_flags() -> None:
    compiled = compile_query(parse("case:true regex:true /todo.*/ content:/fixme/i"))
    branch = compiled.branches[0]
    assert branch.case_sensitive is True
    assert branch.regex_mode is True
    assert branch.path_regex_terms[0].pattern == "todo.*"
    assert branch.content_regex_terms[0].flags == "i"


def test_compile_date_alias_uses_mtime_range() -> None:
    compiled = compile_query(parse("date:this-week"))
    branch = compiled.branches[0]
    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert len(branch.where_params) == 2


def test_compile_reversed_date_range_normalizes_bounds() -> None:
    compiled = compile_query(parse("date:2026-01-03..2026-01-01"))
    branch = compiled.branches[0]
    start, end = branch.where_params

    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert len(branch.where_params) == 2
    assert isinstance(start, int)
    assert isinstance(end, int)
    assert start < end


def test_compile_duplicate_filter_shape() -> None:
    compiled = compile_query(parse("is:duplicate -is:symlink"))
    branch = compiled.branches[0]
    assert "files.content_hash IS NOT NULL" in branch.where_sql
    assert "duplicates.content_hash = files.content_hash" in branch.where_sql
    assert "NOT (files.is_symlink = 1)" in branch.where_sql


def test_compile_negated_group_pushes_negation_to_leaf_terms() -> None:
    compiled = compile_query(parse("-(alpha | beta) ext:txt"))
    branch = compiled.branches[0]

    assert branch.path_match_sql is None
    assert branch.where_sql == "files.ext = ?"
    assert branch.where_params == ("txt",)
    assert [term.value for term in branch.path_terms] == ["alpha", "beta"]
    assert all(term.negated for term in branch.path_terms)


def test_compile_double_negated_group_restores_positive_branches() -> None:
    compiled = compile_query(parse("-(-(alpha | beta))"))

    assert len(compiled.branches) == 2
    assert {branch.path_match_params for branch in compiled.branches} == {('"alpha"',), ('"beta"',)}
    assert all(not branch.path_terms[0].negated for branch in compiled.branches)


def test_compile_reuses_cached_queries() -> None:
    first = compile("report ext:pdf")
    second = compile("report ext:pdf")

    assert first is second


@pytest.mark.parametrize(
    "query",
    [
        "case:maybe report",
        "size:>tenM report",
        "date:2026-01-01..bogus report",
        "is:folder report",
    ],
)
def test_compile_invalid_operator_values_raise_query_syntax_error(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        compile_query(parse(query))
