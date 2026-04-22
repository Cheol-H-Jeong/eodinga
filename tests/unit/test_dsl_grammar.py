from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eodinga.query.dsl import (
    AndNode,
    OperatorNode,
    OrNode,
    PhraseNode,
    QuerySyntaxError,
    RegexNode,
    WordNode,
    parse,
)


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
        "-(alpha beta)",
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
        st.just("-(alpha beta)"),
    )
)
def test_invalid_query_fuzz_raises_cleanly(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        parse(query)
