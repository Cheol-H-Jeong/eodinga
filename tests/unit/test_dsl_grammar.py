from __future__ import annotations

import re

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


def _escape_phrase(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _is_regex_safe_literal(value: str) -> bool:
    try:
        re.compile(value)
    except re.error:
        return False
    return True


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
    ("query", "expected_name", "expected_value"),
    [
        ('"release \\"candidate\\""', None, 'release "candidate"'),
        ('content:"release \\"candidate\\""', "content", 'release "candidate"'),
        ('path:"C:\\\\workspace\\\\notes"', "path", r"C:\workspace\notes"),
    ],
)
def test_parse_phrase_supports_escaped_quotes_and_backslashes(
    query: str,
    expected_name: str | None,
    expected_value: str,
) -> None:
    node = parse(query)

    if expected_name is None:
        assert isinstance(node, PhraseNode)
        assert node.value == expected_value
        return
    assert isinstance(node, OperatorNode)
    assert node.name == expected_name
    assert node.value_kind == "phrase"
    assert node.value == expected_value


@pytest.mark.parametrize(
    ("query", "expected_name", "expected_value"),
    [
        ('content:"a\\"b"', "content", 'a"b'),
        ('path:"dir\\\\name"', "path", r"dir\name"),
    ],
)
def test_parse_inline_phrase_without_whitespace_decodes_escapes(
    query: str,
    expected_name: str,
    expected_value: str,
) -> None:
    node = parse(query)

    assert isinstance(node, OperatorNode)
    assert node.name == expected_name
    assert node.value_kind == "phrase"
    assert node.value == expected_value


@pytest.mark.parametrize(
    ("query", "expected_value"),
    [
        ("size:> 10M", ">10M"),
        ("size:<= 512KiB", "<=512KiB"),
    ],
)
def test_parse_size_operator_allows_separated_comparator_value(
    query: str,
    expected_value: str,
) -> None:
    node = parse(query)

    assert isinstance(node, OperatorNode)
    assert node.name == "size"
    assert node.value_kind == "word"
    assert node.value == expected_value


@pytest.mark.parametrize("query", ["content://i", "path://", "regex://i"])
def test_parse_inline_operator_empty_regex_errors(query: str) -> None:
    with pytest.raises(QuerySyntaxError, match="empty regex"):
        parse(query)


@pytest.mark.parametrize("query", ['""', 'content:""', 'path: ""'])
def test_parse_empty_phrase_errors(query: str) -> None:
    with pytest.raises(QuerySyntaxError, match="empty phrase"):
        parse(query)


@pytest.mark.parametrize("query", ["/todo/x", "content:/todo/mii", "regex:/todo/ix"])
def test_parse_regex_flags_must_be_supported_and_unique(query: str) -> None:
    with pytest.raises(QuerySyntaxError, match="regex flag"):
        parse(query)


def test_parse_phrase_with_dangling_escape_errors() -> None:
    with pytest.raises(QuerySyntaxError, match="unterminated phrase"):
        parse('"\\\"')


@pytest.mark.parametrize("query", ["path:/workspace/projects", "path:/tmp/log", "path:/a/b"])
def test_parse_slash_prefixed_path_literal_as_word_value(query: str) -> None:
    node = parse(query)

    assert isinstance(node, OperatorNode)
    assert node.name == "path"
    assert node.value == query.removeprefix("path:")
    assert node.value_kind == "word"


@pytest.mark.parametrize("query", ["path:/tmp/ms", "path:/tmp/ims", "path:/tmp/is"])
def test_parse_slash_prefixed_path_literal_does_not_treat_short_basename_as_regex_flags(
    query: str,
) -> None:
    node = parse(query)

    assert isinstance(node, OperatorNode)
    assert node.name == "path"
    assert node.value == query.removeprefix("path:")
    assert node.value_kind == "word"


def test_parse_slash_prefixed_path_regex_with_valid_flags() -> None:
    node = parse("path:/tmp/log/i")

    assert isinstance(node, OperatorNode)
    assert node.name == "path"
    assert node.value == "tmp/log"
    assert node.value_kind == "regex"
    assert node.regex_flags == "i"


def test_parse_content_regex_with_escaped_slash_and_korean_text() -> None:
    node = parse(r"content:/회의록\/초안/ms")

    assert isinstance(node, OperatorNode)
    assert node.name == "content"
    assert node.value == r"회의록\/초안"
    assert node.value_kind == "regex"
    assert node.regex_flags == "ms"


@pytest.mark.parametrize(
    ("query", "expected_name", "expected_pattern", "expected_flags"),
    [
        (r"/회의\/록\/초안/im", None, r"회의\/록\/초안", "im"),
        (r"content:/회의\/록\/초안/im", "content", r"회의\/록\/초안", "im"),
        (r"path:/문서\/회의록\/[0-9]+/i", "path", r"문서\/회의록\/[0-9]+", "i"),
    ],
)
def test_parse_regex_with_multiple_escaped_slashes_and_korean_segments(
    query: str,
    expected_name: str | None,
    expected_pattern: str,
    expected_flags: str,
) -> None:
    node = parse(query)

    if expected_name is None:
        assert isinstance(node, RegexNode)
        assert node.pattern == expected_pattern
        assert node.flags == expected_flags
        return

    assert isinstance(node, OperatorNode)
    assert node.name == expected_name
    assert node.value_kind == "regex"
    assert node.value == expected_pattern
    assert node.regex_flags == expected_flags


@pytest.mark.parametrize(
    ("query", "expected_name", "expected_pattern", "expected_flags"),
    [
        (r"/foo\\/i", None, r"foo\\", "i"),
        (r"content: /foo\\/i", "content", r"foo\\", "i"),
        (r"path: /tmp\\/m", "path", r"tmp\\", "m"),
    ],
)
def test_parse_regex_closes_after_even_backslashes(
    query: str,
    expected_name: str | None,
    expected_pattern: str,
    expected_flags: str,
) -> None:
    node = parse(query)

    if expected_name is None:
        assert isinstance(node, RegexNode)
        assert node.pattern == expected_pattern
        assert node.flags == expected_flags
        return

    assert isinstance(node, OperatorNode)
    assert node.name == expected_name
    assert node.value == expected_pattern
    assert node.value_kind == "regex"
    assert node.regex_flags == expected_flags


@pytest.mark.parametrize(
    ("query", "expected_pattern", "expected_flags"),
    [
        (r"path:/tmp\/logs/i", r"tmp\/logs", "i"),
        (r"path:/문서\/보관/ms", r"문서\/보관", "ms"),
    ],
)
def test_parse_slash_prefixed_path_regex_with_escaped_slash(
    query: str,
    expected_pattern: str,
    expected_flags: str,
) -> None:
    node = parse(query)

    assert isinstance(node, OperatorNode)
    assert node.name == "path"
    assert node.value == expected_pattern
    assert node.value_kind == "regex"
    assert node.regex_flags == expected_flags


@pytest.mark.parametrize(
    ("query", "expected_name", "expected_value", "expected_kind"),
    [
        ('content: "hello world"', "content", "hello world", "phrase"),
        ('path:"문서 보관"', "path", "문서 보관", "phrase"),
        ("date: 2026-01-01..2026-01-03", "date", "2026-01-01..2026-01-03", "word"),
        ("date:2026-01-01 .. 2026-01-03", "date", "2026-01-01..2026-01-03", "word"),
        ("size:100 .. 500K", "size", "100..500K", "word"),
        ("date:.. 2026-01-03", "date", "..2026-01-03", "word"),
        ("date:2026-01-02 ..", "date", "2026-01-02..", "word"),
    ],
)
def test_parse_operator_values_with_spacing_and_phrases(
    query: str,
    expected_name: str,
    expected_value: str,
    expected_kind: str,
) -> None:
    node = parse(query)

    assert isinstance(node, OperatorNode)
    assert node.name == expected_name
    assert node.value == expected_value
    assert node.value_kind == expected_kind


def test_parse_inline_or_without_surrounding_spaces() -> None:
    node = parse("ext:pdf|ext:txt")

    assert isinstance(node, OrNode)
    assert [clause.value for clause in node.clauses] == ["pdf", "txt"]  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "\r",
        "-",
        "(-)",
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
        st.sampled_from(
            [
                "content:",
                'content:"',
                "content:/",
                "content://",
                "content://i",
                "path://",
                "regex://i",
                "(",
                "alpha |",
                "((alpha)",
            ]
        ),
    )
)
def test_invalid_query_fuzz_raises_cleanly(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        parse(query)


OPERATOR_ATOMS = st.one_of(
    st.builds(lambda value: f"content:{value}", st.sampled_from(["alpha", '"hello world"'])),
    st.builds(
        lambda value: f"date:{value}",
        st.sampled_from(
            [
                "today",
                "yesterday",
                "this-week",
                "last-week",
                "this-month",
                "last-month",
                "2026-01-01",
                "2026-01-01..2026-01-03",
            ]
        ),
    ),
    st.builds(lambda value: f"ext:{value}", st.sampled_from(["pdf", "txt", "md"])),
    st.builds(
        lambda value: f"is:{value}",
        st.sampled_from(["file", "dir", "symlink", "empty", "duplicate"]),
    ),
    st.builds(lambda value: f"path:{value}", st.sampled_from(["workspace", "프로젝트", '"team notes"'])),
    st.builds(lambda value: f"size:{value}", st.sampled_from([">10M", "<=42K", "=512B", "100..500K"])),
)

ATOMS = st.one_of(
    st.text(
        st.characters(blacklist_characters='()|" /', blacklist_categories=("Cs",)),
        min_size=1,
        max_size=12,
    ).filter(lambda value: value.strip() and value != "-"),
    st.builds(
        lambda value: f'"{_escape_phrase(value)}"',
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


@given(
    st.tuples(
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=8,
        ),
        st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=3,
        ).filter(
            lambda value: len(set(value)) != len(value) or any(flag not in {"i", "m", "s"} for flag in value)
        ),
    )
)
def test_slash_prefixed_path_literal_with_short_basename_fuzz_parses_as_word(
    segments: tuple[str, str],
) -> None:
    left, right = segments
    node = parse(f"path:/{left}/{right}")

    assert isinstance(node, OperatorNode)
    assert node.name == "path"
    assert node.value == f"/{left}/{right}"
    assert node.value_kind == "word"


@given(st.sampled_from(["i", "m", "s", "im", "is", "ms", "ims"]))
def test_slash_prefixed_path_literal_with_regex_like_basename_fuzz_stays_word(
    basename: str,
) -> None:
    node = parse(f"path:/tmp/{basename}")

    assert isinstance(node, OperatorNode)
    assert node.name == "path"
    assert node.value == f"/tmp/{basename}"
    assert node.value_kind == "word"


INVALID_REGEX_FLAGS = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=3,
).filter(
    lambda flags: any(flag not in {"i", "m", "s"} for flag in flags)
    or len(set(flags)) != len(flags)
)


@given(INVALID_REGEX_FLAGS)
def test_invalid_regex_flags_fuzz_raise_cleanly(flags: str) -> None:
    with pytest.raises(QuerySyntaxError):
        parse(f"content:/todo/{flags}")


PHRASE_TEXT = st.text(
    alphabet=st.characters(blacklist_characters='"', blacklist_categories=("Cs",)),
    min_size=1,
    max_size=24,
)


@given(PHRASE_TEXT)
def test_phrase_escape_round_trip_fuzz(value: str) -> None:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    node = parse(f'content:"{escaped}"')

    assert isinstance(node, OperatorNode)
    assert node.name == "content"
    assert node.value_kind == "phrase"
    assert node.value == value


REGEX_BODY_TEXT = st.text(
    alphabet=st.sampled_from(
        [
            "a",
            "b",
            "c",
            "0",
            "1",
            "-",
            "_",
            "[",
            "]",
            "+",
            ".",
            "회",
            "의",
            "록",
            "/",
            "\\",
        ]
    ),
    min_size=1,
    max_size=24,
).filter(lambda value: not value.endswith("\\"))


def _escape_regex_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    return escaped.replace("/", r"\/")


@given(REGEX_BODY_TEXT, st.sampled_from(["", "i", "m", "s", "im", "is", "ms", "ims"]))
def test_regex_escape_round_trip_fuzz(value: str, flags: str) -> None:
    escaped = _escape_regex_literal(value)
    node = parse(f"content:/{escaped}/{flags}")

    assert isinstance(node, OperatorNode)
    assert node.name == "content"
    assert node.value_kind == "regex"
    assert node.value == escaped
    assert node.regex_flags == flags


NEGATABLE_OPERATOR_ATOMS = st.one_of(
    st.sampled_from(
        [
            "content:/todo|fixme/i",
            'content:"alpha beta"',
            'path:"team notes"',
            "path:/workspace/projects",
            "path:/tmp/log/i",
            "date:this-week",
            "size:>10M",
            "is:duplicate",
            "case:false",
            "regex:true",
        ]
    ),
    st.builds(lambda value: f"-{value}", st.sampled_from(["ext:pdf", "is:symlink", "path:archive"])),
)

NEGATABLE_ATOMS = st.one_of(
    st.text(
        st.characters(blacklist_characters='()|" /', blacklist_categories=("Cs",)),
        min_size=1,
        max_size=12,
    ).filter(lambda value: value.strip() and value != "-" and _is_regex_safe_literal(value)),
    st.builds(
        lambda value: f'"{_escape_phrase(value)}"',
        st.text(
            st.characters(blacklist_characters='"', blacklist_categories=("Cs",)),
            min_size=1,
            max_size=12,
        ).filter(_is_regex_safe_literal),
    ),
    OPERATOR_ATOMS,
)

NEGATABLE_VALID_QUERY_STRATEGY = st.recursive(
    st.one_of(NEGATABLE_ATOMS, NEGATABLE_OPERATOR_ATOMS).map(str),
    lambda children: st.one_of(
        st.builds(lambda items: " ".join(items), st.lists(children, min_size=2, max_size=3)),
        st.builds(lambda items: " | ".join(items), st.lists(children, min_size=2, max_size=3)),
        st.builds(lambda child: f"({child})", children),
        st.builds(lambda child: f"-({child})", children),
    ),
    max_leaves=10,
)


@given(NEGATABLE_VALID_QUERY_STRATEGY)
def test_negated_operator_query_fuzz_parses_and_compiles(query: str) -> None:
    compile_query(parse(query))


@given(
    st.one_of(
        st.tuples(
            st.just("case"),
            st.booleans(),
            st.text(
                alphabet=st.characters(
                    blacklist_characters='()|" /',
                    blacklist_categories=("Cs",),
                ),
                min_size=1,
                max_size=12,
            ).filter(lambda value: value.strip() and value != "-" and not value.startswith("-")),
        ),
        st.tuples(
            st.just("regex"),
            st.booleans(),
            st.from_regex(r"[A-Za-z0-9._+-]{1,12}", fullmatch=True).filter(
                lambda value: value != "-" and not value.startswith("-") and _is_valid_regex_pattern(value)
            ),
        ),
    )
)
def test_negated_boolean_operator_fuzz_inverts_compiled_mode(
    payload: tuple[str, bool, str],
) -> None:
    operator, value, term = payload
    literal = str(value).lower()
    enabled = compile_query(parse(f"{operator}:{literal} {term}")).branches[0]
    negated = compile_query(parse(f"-{operator}:{literal} {term}")).branches[0]

    if operator == "case":
        assert negated.case_sensitive is (not enabled.case_sensitive)
        assert negated.regex_mode is enabled.regex_mode
    else:
        assert negated.regex_mode is (not enabled.regex_mode)
        assert negated.case_sensitive is enabled.case_sensitive


def _is_valid_regex_pattern(value: str) -> bool:
    try:
        re.compile(value)
    except re.error:
        return False
    return True
