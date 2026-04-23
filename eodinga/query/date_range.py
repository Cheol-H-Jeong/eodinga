from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from eodinga.query.dsl import QuerySyntaxError


@dataclass(frozen=True)
class DateRange:
    start: int | None = None
    end: int | None = None


def _relative_aliases(*keywords: str) -> frozenset[str]:
    aliases: set[str] = set()
    for keyword in keywords:
        normalized = keyword.casefold()
        aliases.add(normalized)
        aliases.add(normalized.replace("-", "_"))
        aliases.add(normalized.replace("-", ""))
    return frozenset(aliases)


_TODAY_KEYWORDS = _relative_aliases("today")
_YESTERDAY_KEYWORDS = _relative_aliases("yesterday")
_TOMORROW_KEYWORDS = _relative_aliases("tomorrow")
_THIS_WEEK_KEYWORDS = _relative_aliases("this-week", "week")
_LAST_WEEK_KEYWORDS = _relative_aliases("last-week", "prev-week", "previous-week")
_THIS_MONTH_KEYWORDS = _relative_aliases("this-month", "month")
_LAST_MONTH_KEYWORDS = _relative_aliases("last-month", "prev-month", "previous-month")
_THIS_YEAR_KEYWORDS = _relative_aliases("this-year", "year")
_LAST_YEAR_KEYWORDS = _relative_aliases("last-year", "prev-year", "previous-year")

RELATIVE_DATE_KEYWORDS = frozenset().union(
    _TODAY_KEYWORDS,
    _YESTERDAY_KEYWORDS,
    _TOMORROW_KEYWORDS,
    _THIS_WEEK_KEYWORDS,
    _LAST_WEEK_KEYWORDS,
    _THIS_MONTH_KEYWORDS,
    _LAST_MONTH_KEYWORDS,
    _THIS_YEAR_KEYWORDS,
    _LAST_YEAR_KEYWORDS,
)


def _local_tzinfo() -> tzinfo | None:
    return datetime.now().astimezone().tzinfo


def _day_bounds(day: date) -> DateRange:
    local_tz = _local_tzinfo()
    start = datetime.combine(day, time.min, tzinfo=local_tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=local_tz)
    return DateRange(start=int(start.timestamp()), end=int(end.timestamp()))


def _span_bounds(start_day: date, end_day: date) -> DateRange:
    return DateRange(start=_day_bounds(start_day).start, end=_day_bounds(end_day).start)


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _next_month_start(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def _year_start(day: date) -> date:
    return day.replace(month=1, day=1)


def _next_year_start(day: date) -> date:
    return day.replace(year=day.year + 1, month=1, day=1)


def _parse_iso_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def _parse_iso_span(value: str) -> DateRange | None:
    if re.fullmatch(r"\d{4}", value):
        start = date(int(value), 1, 1)
        return _span_bounds(start, _next_year_start(start))
    month_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{2})", value)
    if month_match is not None:
        try:
            start = date(int(month_match.group("year")), int(month_match.group("month")), 1)
        except ValueError as error:
            raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error
        return _span_bounds(start, _next_month_start(start))
    week_match = re.fullmatch(r"(?P<year>\d{4})-?[Ww](?P<week>\d{2})", value)
    if week_match is None:
        return None
    try:
        start = date.fromisocalendar(int(week_match.group("year")), int(week_match.group("week")), 1)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error
    return _span_bounds(start, start + timedelta(days=7))


def _instant_bounds(moment: datetime) -> DateRange:
    localized = moment if moment.tzinfo is not None else moment.replace(tzinfo=_local_tzinfo())
    start = int(localized.timestamp())
    return DateRange(start=start, end=start + 1)


def _parse_iso_endpoint(value: str) -> DateRange:
    span = _parse_iso_span(value)
    if span is not None:
        return span
    try:
        return _day_bounds(_parse_iso_day(value))
    except QuerySyntaxError:
        pass
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        return _instant_bounds(datetime.fromisoformat(normalized))
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def _relative_range(value: str) -> DateRange | None:
    today = datetime.now().astimezone().date()
    normalized = value.strip().casefold()
    if normalized in _TODAY_KEYWORDS:
        return _day_bounds(today)
    if normalized in _YESTERDAY_KEYWORDS:
        return _day_bounds(today - timedelta(days=1))
    if normalized in _TOMORROW_KEYWORDS:
        return _day_bounds(today + timedelta(days=1))
    if normalized in _THIS_WEEK_KEYWORDS:
        start = today - timedelta(days=today.weekday())
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(start + timedelta(days=7)).start)
    if normalized in _LAST_WEEK_KEYWORDS:
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)
    if normalized in _THIS_MONTH_KEYWORDS:
        start = _month_start(today)
        next_month = _next_month_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_month).start)
    if normalized in _LAST_MONTH_KEYWORDS:
        this_month = _month_start(today)
        last_month = _month_start(this_month - timedelta(days=1))
        return DateRange(start=_day_bounds(last_month).start, end=_day_bounds(this_month).start)
    if normalized in _THIS_YEAR_KEYWORDS:
        start = _year_start(today)
        next_year = _next_year_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_year).start)
    if normalized in _LAST_YEAR_KEYWORDS:
        this_year = _year_start(today)
        last_year = this_year.replace(year=this_year.year - 1)
        return DateRange(start=_day_bounds(last_year).start, end=_day_bounds(this_year).start)
    return None


def parse_date_range(value: str) -> DateRange:
    stripped = value.strip()
    relative = _relative_range(stripped)
    if relative is not None:
        return relative
    if ".." in stripped:
        left, right = (part.strip() for part in stripped.split("..", 1))
        if not left and not right:
            raise QuerySyntaxError(f"invalid date literal: {stripped}", 0)
        if not left:
            return DateRange(end=parse_date_range(right).end)
        if not right:
            return DateRange(start=parse_date_range(left).start)
        left_range = parse_date_range(left)
        right_range = parse_date_range(right)
        if (right_range.start or 0) < (left_range.start or 0):
            left_range, right_range = right_range, left_range
        return DateRange(start=left_range.start, end=right_range.end)
    return _parse_iso_endpoint(stripped)
