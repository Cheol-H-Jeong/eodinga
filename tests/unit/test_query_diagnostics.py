from __future__ import annotations

import pytest

from eodinga.query.compiler import compile_query
from eodinga.query.dsl import OperatorNode, QuerySyntaxError, parse


@pytest.mark.parametrize(
    ("query", "expected_position"),
    [
        ("case:maybe duplicate", 5),
        ("date:2026-01-01..bogus duplicate", 17),
        ("size:>100..500K duplicate", 5),
        ("is:bundle duplicate", 3),
        ("/[a-/", 1),
        ("regex:true [a-", 11),
        ("content:/[a-/", 9),
    ],
)
def test_semantic_query_errors_report_precise_positions(
    query: str,
    expected_position: int,
) -> None:
    with pytest.raises(QuerySyntaxError) as excinfo:
        compile_query(parse(query))

    assert excinfo.value.position == expected_position


def test_parse_operator_tracks_value_position_for_spaced_values() -> None:
    node = parse('content: "hello world"')

    assert isinstance(node, OperatorNode)
    assert node.position == 0
    assert node.value_position == 9


def test_parse_operator_tracks_value_position_for_spaced_range_values() -> None:
    node = parse("date: 2026-01-01 .. 2026-01-03")

    assert isinstance(node, OperatorNode)
    assert node.position == 0
    assert node.value_position == 6
