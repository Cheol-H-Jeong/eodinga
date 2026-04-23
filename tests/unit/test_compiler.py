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


def test_compile_regex_mode_promotes_plain_terms_to_regex() -> None:
    compiled = compile_query(parse("regex:true report-[0-9]+"))
    branch = compiled.branches[0]

    assert branch.path_match_sql is None
    assert branch.path_terms == ()
    assert branch.path_regex_terms == (branch.path_regex_terms[0],)
    assert branch.path_regex_terms[0].pattern == "report-[0-9]+"
    assert branch.path_regex_terms[0].negated is False


@pytest.mark.parametrize(
    ("query", "expected_case_sensitive", "expected_regex_mode"),
    [
        ("case:true alpha", True, False),
        ("-case:true alpha", False, False),
        ("case:false alpha", False, False),
        ("-case:false alpha", True, False),
        ("regex:true alpha", False, True),
        ("-regex:true alpha", False, False),
        ("regex:false alpha", False, False),
        ("-regex:false alpha", False, True),
    ],
)
def test_compile_negated_boolean_operators_invert_requested_mode(
    query: str,
    expected_case_sensitive: bool,
    expected_regex_mode: bool,
) -> None:
    compiled = compile_query(parse(query))
    branch = compiled.branches[0]

    assert branch.case_sensitive is expected_case_sensitive
    assert branch.regex_mode is expected_regex_mode


def test_compile_date_alias_uses_mtime_range() -> None:
    compiled = compile_query(parse("date:this-week"))
    branch = compiled.branches[0]
    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert len(branch.where_params) == 2


@pytest.mark.parametrize("query", ["date:last-week", "date:last-month"])
def test_compile_previous_period_date_aliases_use_mtime_ranges(query: str) -> None:
    compiled = compile_query(parse(query))
    branch = compiled.branches[0]

    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert len(branch.where_params) == 2
    assert isinstance(branch.where_params[0], int)
    assert isinstance(branch.where_params[1], int)
    assert branch.where_params[0] < branch.where_params[1]


def test_compile_reversed_date_range_normalizes_bounds() -> None:
    compiled = compile_query(parse("date:2026-01-03..2026-01-01"))
    branch = compiled.branches[0]
    start, end = branch.where_params

    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert len(branch.where_params) == 2
    assert isinstance(start, int)
    assert isinstance(end, int)
    assert start < end


@pytest.mark.parametrize(
    ("query", "expected_sql", "param_index"),
    [
        ("date:2026-01-03..", "files.mtime >= ?", 0),
        ("created:..2026-01-03", "files.ctime < ?", 0),
    ],
)
def test_compile_open_ended_date_ranges(
    query: str,
    expected_sql: str,
    param_index: int,
) -> None:
    compiled = compile_query(parse(query))
    branch = compiled.branches[0]

    assert branch.where_sql == expected_sql
    assert isinstance(branch.where_params[param_index], int)


def test_compile_datetime_literals_preserve_instant_granularity() -> None:
    compiled = compile_query(parse("modified:2026-01-03T09:15:30"))
    branch = compiled.branches[0]
    start, end = branch.where_params

    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert isinstance(start, int)
    assert isinstance(end, int)
    assert end - start == 1


def test_compile_datetime_literals_accept_lowercase_utc_suffix() -> None:
    compiled = compile_query(parse("modified:2026-01-03T09:15:30z"))
    branch = compiled.branches[0]
    start, end = branch.where_params

    assert branch.where_sql == "files.mtime >= ? AND files.mtime < ?"
    assert isinstance(start, int)
    assert isinstance(end, int)
    assert end - start == 1


def test_compile_datetime_ranges_preserve_exact_endpoints() -> None:
    compiled = compile_query(parse("created:2026-01-03T09:15:30..2026-01-03T09:16:00"))
    branch = compiled.branches[0]
    start, end = branch.where_params

    assert branch.where_sql == "files.ctime >= ? AND files.ctime < ?"
    assert isinstance(start, int)
    assert isinstance(end, int)
    assert end - start == 31


def test_compile_size_range_normalizes_bounds() -> None:
    compiled = compile_query(parse("size:500K..100"))
    branch = compiled.branches[0]

    assert branch.where_sql == "files.size >= ? AND files.size <= ?"
    assert branch.where_params == (100, 500 * 1024)


def test_compile_duplicate_filter_shape() -> None:
    compiled = compile_query(parse("is:duplicate -is:symlink"))
    branch = compiled.branches[0]
    assert "files.content_hash IS NOT NULL" in branch.where_sql
    assert "duplicates.content_hash = files.content_hash" in branch.where_sql
    assert "NOT (files.is_symlink = 1)" in branch.where_sql


def test_compile_empty_filter_shape() -> None:
    compiled = compile_query(parse("is:empty -is:symlink"))
    branch = compiled.branches[0]

    assert "files.size = 0" in branch.where_sql
    assert "files.is_dir = 1 AND NOT EXISTS" in branch.where_sql
    assert "descendants.path LIKE (files.path || '/%')" in branch.where_sql
    assert "NOT (files.is_symlink = 1)" in branch.where_sql


def test_compile_non_ascii_path_filter_uses_python_normalized_scan() -> None:
    compiled = compile_query(parse("path:회의록 ext:txt"))
    branch = compiled.branches[0]

    assert "files.path LIKE ?" not in branch.where_sql
    assert branch.path_filters[0].value == "회의록"
    assert branch.where_sql == "files.ext = ?"
    assert branch.where_params == ("txt",)


def test_compile_negated_group_pushes_negation_to_leaf_terms() -> None:
    compiled = compile_query(parse("-(alpha | beta) ext:txt"))
    branch = compiled.branches[0]

    assert branch.path_match_sql is None
    assert branch.where_sql == "files.ext = ?"
    assert branch.where_params == ("txt",)
    assert [term.value for term in branch.path_terms] == ["alpha", "beta"]
    assert all(term.negated for term in branch.path_terms)


def test_compile_negated_and_group_splits_into_negated_branches() -> None:
    compiled = compile_query(parse("-(alpha beta) ext:txt"))

    assert len(compiled.branches) == 2
    assert all(branch.where_sql == "files.ext = ?" for branch in compiled.branches)
    assert all(branch.where_params == ("txt",) for branch in compiled.branches)
    assert {branch.path_terms[0].value for branch in compiled.branches} == {"alpha", "beta"}
    assert all(branch.path_terms[0].negated for branch in compiled.branches)


def test_compile_double_negated_group_restores_positive_branches() -> None:
    compiled = compile_query(parse("-(-(alpha | beta))"))

    assert len(compiled.branches) == 2
    assert {branch.path_match_params for branch in compiled.branches} == {('"alpha"',), ('"beta"',)}
    assert all(not branch.path_terms[0].negated for branch in compiled.branches)


def test_compile_double_negated_and_group_restores_positive_conjunction() -> None:
    compiled = compile_query(parse("-(-(alpha beta))"))

    assert len(compiled.branches) == 1
    assert compiled.branches[0].path_match_params == ('"alpha" "beta"',)
    assert [term.value for term in compiled.branches[0].path_terms] == ["alpha", "beta"]
    assert all(not term.negated for term in compiled.branches[0].path_terms)


def test_compile_reuses_cached_queries() -> None:
    first = compile("report ext:pdf")
    second = compile("report ext:pdf")

    assert first is second


@pytest.mark.parametrize(
    "query",
    [
        "case:maybe report",
        "/[a-/",
        "regex:true [a-",
        "size:>tenM report",
        "date:2026-01-01..bogus report",
        "is:bundle report",
    ],
)
def test_compile_invalid_operator_values_raise_query_syntax_error(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        compile_query(parse(query))
