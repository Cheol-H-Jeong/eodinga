from __future__ import annotations

from eodinga.query.compiler import compile_query
from eodinga.query.dsl import parse


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
