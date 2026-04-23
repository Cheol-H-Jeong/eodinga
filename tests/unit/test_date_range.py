from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from eodinga.query.date_range import DateRange, parse_date_range


@pytest.fixture
def frozen_seoul_datetime(monkeypatch: pytest.MonkeyPatch) -> ZoneInfo:
    seoul = ZoneInfo("Asia/Seoul")
    frozen_now = datetime(2026, 4, 23, 9, 30, tzinfo=seoul)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return frozen_now.replace(tzinfo=None)
            return frozen_now.astimezone(tz)

    monkeypatch.setattr("eodinga.query.date_range.datetime", _FrozenDateTime)
    return seoul


def _day_range(day: date, zone: ZoneInfo) -> DateRange:
    start = int(datetime(day.year, day.month, day.day, tzinfo=zone).timestamp())
    next_day = day + timedelta(days=1)
    end = int(datetime(next_day.year, next_day.month, next_day.day, tzinfo=zone).timestamp())
    return DateRange(start=start, end=end)


def test_parse_date_range_accepts_relative_macro_endpoints(
    frozen_seoul_datetime: ZoneInfo,
) -> None:
    yesterday = _day_range(date(2026, 4, 22), frozen_seoul_datetime)
    today = _day_range(date(2026, 4, 23), frozen_seoul_datetime)
    this_week = DateRange(
        start=int(datetime(2026, 4, 20, tzinfo=frozen_seoul_datetime).timestamp()),
        end=int(datetime(2026, 4, 27, tzinfo=frozen_seoul_datetime).timestamp()),
    )

    assert parse_date_range("yesterday..today") == DateRange(
        start=yesterday.start,
        end=today.end,
    )
    assert parse_date_range("..today") == DateRange(end=today.end)
    assert parse_date_range("this-week..") == DateRange(start=this_week.start)


def test_parse_date_range_normalizes_reversed_relative_windows(
    frozen_seoul_datetime: ZoneInfo,
) -> None:
    yesterday = _day_range(date(2026, 4, 22), frozen_seoul_datetime)
    today = _day_range(date(2026, 4, 23), frozen_seoul_datetime)

    assert parse_date_range("today..yesterday") == DateRange(
        start=yesterday.start,
        end=today.end,
    )


def test_parse_date_range_accepts_mixed_iso_and_relative_endpoints(
    frozen_seoul_datetime: ZoneInfo,
) -> None:
    today = _day_range(date(2026, 4, 23), frozen_seoul_datetime)
    assert parse_date_range("2026-04-22..today") == DateRange(
        start=int(datetime(2026, 4, 22, tzinfo=frozen_seoul_datetime).timestamp()),
        end=today.end,
    )
