from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from eodinga.query.date_range import parse_date_range


def test_parse_open_ended_relative_date_ranges() -> None:
    today = parse_date_range("today")
    last_week = parse_date_range("last-week")

    assert parse_date_range("..today") == type(today)(end=today.end)
    assert parse_date_range("last-week..") == type(last_week)(start=last_week.start)


def test_parse_open_ended_relative_date_ranges_accept_datetime_mixed_bounds() -> None:
    today = parse_date_range("today")
    instant = parse_date_range("2026-01-03T09:15:30Z")

    assert parse_date_range("2026-01-03T09:15:30Z..").start == instant.start
    assert parse_date_range("..today").end == today.end


def test_parse_open_ended_relative_date_ranges_use_local_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seoul = ZoneInfo("Asia/Seoul")
    frozen_now = datetime(2026, 4, 23, 0, 30, tzinfo=seoul)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return frozen_now.replace(tzinfo=None)
            return frozen_now.astimezone(tz)

    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)

    this_month = parse_date_range("this-month")
    previous_week = parse_date_range("previous-week")

    assert parse_date_range("..this-month").end == this_month.end
    assert parse_date_range("previous-week..").start == previous_week.start
