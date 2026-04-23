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


def test_compile_regex_operator_accepts_explicit_pattern_alias() -> None:
    compiled = compile_query(parse("regex:/todo|fixme/i"))
    branch = compiled.branches[0]

    assert branch.regex_mode is False
    assert branch.path_match_sql is None
    assert branch.path_regex_terms == (
        branch.path_regex_terms[0],
    )
    assert branch.path_regex_terms[0].pattern == "todo|fixme"
    assert branch.path_regex_terms[0].flags == "i"
    assert branch.path_regex_terms[0].negated is False


def test_compile_regex_operator_accepts_word_pattern_alias() -> None:
    compiled = compile_query(parse(r"regex:report-\d+"))
    branch = compiled.branches[0]

    assert branch.regex_mode is False
    assert branch.path_match_sql is None
    assert branch.path_terms == ()
    assert branch.path_regex_terms == (
        branch.path_regex_terms[0],
    )
    assert branch.path_regex_terms[0].pattern == r"report-\d+"
    assert branch.path_regex_terms[0].flags == ""
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


@pytest.mark.parametrize(
    "query",
    [
        "case:true | ext:txt",
        "regex:true | ext:txt",
        "-(case:false alpha beta)",
        "-(regex:false alpha beta)",
        "alpha | (case:true beta)",
        "-(alpha regex:true)",
    ],
)
def test_compile_rejects_mode_operators_inside_boolean_contexts(query: str) -> None:
    with pytest.raises(
        QuerySyntaxError,
        match="case/regex mode operators cannot appear inside OR branches or negated groups",
    ):
        compile_query(parse(query))


def test_compile_allows_mode_operator_to_scope_over_grouped_or_branch() -> None:
    compiled = compile_query(parse("case:true (alpha | beta)"))

    assert len(compiled.branches) == 2
    assert all(branch.case_sensitive is True for branch in compiled.branches)
    assert [branch.path_terms[0].value for branch in compiled.branches] == ["alpha", "beta"]


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


@pytest.mark.parametrize(
    ("query", "expected_sql", "expected_params"),
    [
        ("size:..500K", "files.size <= ?", (500 * 1024,)),
        ("size:100..", "files.size >= ?", (100,)),
    ],
)
def test_compile_open_ended_size_ranges(
    query: str,
    expected_sql: str,
    expected_params: tuple[int, ...],
) -> None:
    compiled = compile_query(parse(query))
    branch = compiled.branches[0]

    assert branch.where_sql == expected_sql
    assert branch.where_params == expected_params


@pytest.mark.parametrize(
    ("query", "expected_sql", "expected_param"),
    [
        ("size:>1.5MB", "files.size > ?", int(1.5 * 1024**2)),
        ("size:<=512KiB", "files.size <= ?", 512 * 1024),
    ],
)
def test_compile_size_aliases_accept_common_binary_suffixes(
    query: str,
    expected_sql: str,
    expected_param: int,
) -> None:
    compiled = compile_query(parse(query))
    branch = compiled.branches[0]

    assert branch.where_sql == expected_sql
    assert branch.where_params == (expected_param,)


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
    assert "descendants.path LIKE (" in branch.where_sql
    assert "ESCAPE '^'" in branch.where_sql
    assert "NOT (files.is_symlink = 1)" in branch.where_sql


def test_compile_file_and_dir_filters_exclude_symlinks() -> None:
    compiled = compile_query(parse("is:file is:dir"))
    branch = compiled.branches[0]

    assert "files.is_dir = 0 AND files.is_symlink = 0" in branch.where_sql
    assert "files.is_dir = 1 AND files.is_symlink = 0" in branch.where_sql


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


def test_compile_double_negated_group_restores_positive_branches() -> None:
    compiled = compile_query(parse("-(-(alpha | beta))"))

    assert len(compiled.branches) == 2
    assert {branch.path_match_params for branch in compiled.branches} == {('"alpha"',), ('"beta"',)}
    assert all(not branch.path_terms[0].negated for branch in compiled.branches)


def _branch_signature(compiled) -> set[tuple[tuple[tuple[str, bool, str], ...], str, tuple[object, ...]]]:
    return {
        (
            tuple((term.value, term.negated, term.kind) for term in branch.path_terms),
            branch.where_sql,
            branch.where_params,
        )
        for branch in compiled.branches
    }


@pytest.mark.parametrize(
    ("query", "equivalent"),
    [
        ("-(alpha beta)", "-alpha | -beta"),
        ("-(alpha | beta)", "-alpha -beta"),
        ("-((alpha | beta) gamma)", "-gamma | (-alpha -beta)"),
        ("-(-(alpha | beta))", "alpha | beta"),
    ],
)
def test_compile_group_negation_truth_table_matches_equivalent_form(
    query: str, equivalent: str
) -> None:
    compiled = compile_query(parse(query))
    equivalent_compiled = compile_query(parse(equivalent))

    assert _branch_signature(compiled) == _branch_signature(equivalent_compiled)


def test_compile_reuses_cached_queries() -> None:
    first = compile("report ext:pdf")
    second = compile("report ext:pdf")

    assert first is second


def test_compile_path_filter_escapes_like_wildcards() -> None:
    compiled = compile_query(parse(r"path:100%_complete^notes"))
    branch = compiled.branches[0]

    assert branch.where_sql == "files.path LIKE ? ESCAPE '^'"
    assert branch.where_params == (r"%100^%^_complete^^notes%",)


def test_compile_is_empty_escapes_descendant_like_patterns() -> None:
    compiled = compile_query(parse("is:empty"))
    branch = compiled.branches[0]

    assert "ESCAPE '^'" in branch.where_sql
    assert "REPLACE(REPLACE(REPLACE(files.path, '^', '^^'), '%', '^%'), '_', '^_')" in branch.where_sql


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
