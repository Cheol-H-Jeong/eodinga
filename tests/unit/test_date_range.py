from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from eodinga.query.date_range import parse_date_range


class _FrozenDateTime(datetime):
    frozen_now = datetime(2026, 4, 23, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is None:
            return cls.frozen_now.replace(tzinfo=None)
        return cls.frozen_now.astimezone(tz)


@pytest.mark.parametrize(
    ("value", "expected_start", "expected_end"),
    [
        (
            "2026",
            datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")),
            datetime(2027, 1, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        ),
        (
            "2026-02",
            datetime(2026, 2, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")),
            datetime(2026, 3, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        ),
    ],
)
def test_parse_date_range_supports_reduced_precision_iso_literals(
    value: str,
    expected_start: datetime,
    expected_end: datetime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)

    parsed = parse_date_range(value)

    assert parsed.start == int(expected_start.timestamp())
    assert parsed.end == int(expected_end.timestamp())


def test_parse_date_range_supports_mixed_relative_and_reduced_precision_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)

    parsed = parse_date_range("2026-03..today")

    assert parsed.start == int(datetime(2026, 3, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())
    assert parsed.end == int(datetime(2026, 4, 24, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())


def test_parse_date_range_normalizes_reversed_reduced_precision_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)

    parsed = parse_date_range("2026-03..2026-01")

    assert parsed.start == int(datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())
    assert parsed.end == int(datetime(2026, 4, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())


@pytest.mark.parametrize("value", ["2026-13", "9999"])
def test_parse_date_range_rejects_invalid_reduced_precision_literals(value: str) -> None:
    with pytest.raises(ValueError, match="invalid date literal"):
        parse_date_range(value)
