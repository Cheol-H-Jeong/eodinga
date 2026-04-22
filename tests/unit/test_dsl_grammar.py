from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eodinga.query.dsl import (
    AndNode,
    NotNode,
    OperatorNode,
    OrNode,
    PhraseNode,
    QuerySyntaxError,
    RegexNode,
    WordNode,
    parse,
)
from eodinga.query.compiler import compile_query


@pytest.mark.parametrize(
    ("query", "expected_type"),
    [
        ("report", WordNode),
        ('"exact phrase"', PhraseNode),
        ("/foo.*/i", RegexNode),
        ("ext:pdf", OperatorNode),
        ('content:"hello world"', OperatorNode),
    ],
)
def test_parse_atomic_terms(query: str, expected_type: type[object]) -> None:
    assert isinstance(parse(query), expected_type)


def test_parse_and_expression() -> None:
    node = parse("alpha beta")
    assert isinstance(node, AndNode)
    assert [clause.value for clause in node.clauses] == ["alpha", "beta"]  # type: ignore[attr-defined]


def test_parse_or_expression() -> None:
    node = parse("alpha | beta")
    assert isinstance(node, OrNode)
    assert len(node.clauses) == 2


def test_parse_grouped_expression() -> None:
    node = parse('(alpha | beta) ext:txt')
    assert isinstance(node, AndNode)
    assert isinstance(node.clauses[0], OrNode)
    assert isinstance(node.clauses[1], OperatorNode)


def test_parse_negation() -> None:
    node = parse('-content:"secret"')
    assert isinstance(node, OperatorNode)
    assert node.negated is True


def test_parse_negated_group() -> None:
    node = parse("-(alpha | beta)")
    assert isinstance(node, NotNode)
    assert isinstance(node.clause, OrNode)


def test_parse_operator_regex_value() -> None:
    node = parse("content:/todo|fixme/i")
    assert isinstance(node, OperatorNode)
    assert node.value_kind == "regex"
    assert node.regex_flags == "i"


@pytest.mark.parametrize(
    "query",
    [
        "",
        '"unterminated',
        "/unterminated",
        "()",
        "alpha |",
        "content:",
        "((alpha)",
    ],
)
def test_parse_errors(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        parse(query)


@given(
    st.one_of(
        st.builds(
            lambda value: f'"{value}',
            st.text(min_size=1, max_size=20).filter(lambda value: '"' not in value),
        ),
        st.builds(
            lambda value: f"/{value}",
            st.text(min_size=1, max_size=20).filter(lambda value: "/" not in value),
        ),
        st.sampled_from(["content:", 'content:"', "content:/", "(", "alpha |", "((alpha)"]),
    )
)
def test_invalid_query_fuzz_raises_cleanly(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        parse(query)


OPERATOR_ATOMS = st.one_of(
    st.builds(lambda value: f"content:{value}", st.sampled_from(["alpha", '"hello world"'])),
    st.builds(lambda value: f"date:{value}", st.sampled_from(["today", "yesterday", "this-week", "this-month", "2026-01-01", "2026-01-01..2026-01-03"])),
    st.builds(lambda value: f"ext:{value}", st.sampled_from(["pdf", "txt", "md"])),
    st.builds(lambda value: f"is:{value}", st.sampled_from(["file", "dir", "symlink", "duplicate"])),
    st.builds(lambda value: f"path:{value}", st.sampled_from(["workspace", "프로젝트", '"team notes"'])),
    st.builds(lambda value: f"size:{value}", st.sampled_from([">10M", "<=42K", "=512B"])),
)

ATOMS = st.one_of(
    st.text(
        st.characters(blacklist_characters='()|" /', blacklist_categories=("Cs",)),
        min_size=1,
        max_size=12,
    ),
    st.builds(
        lambda value: f'"{value}"',
        st.text(
            st.characters(blacklist_characters='"', blacklist_categories=("Cs",)),
            min_size=1,
            max_size=12,
        ),
    ),
    OPERATOR_ATOMS,
)

VALID_QUERY_STRATEGY = st.recursive(
    ATOMS.map(str),
    lambda children: st.one_of(
        st.builds(lambda items: " ".join(items), st.lists(children, min_size=2, max_size=3)),
        st.builds(lambda items: " | ".join(items), st.lists(children, min_size=2, max_size=3)),
        st.builds(lambda child: f"({child})", children),
        st.builds(lambda child: f"-({child})", children),
    ),
    max_leaves=8,
)


@given(VALID_QUERY_STRATEGY)
def test_valid_query_fuzz_parses_and_compiles(query: str) -> None:
    compile_query(parse(query))
