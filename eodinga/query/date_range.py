from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from eodinga.query.dsl import QuerySyntaxError


@dataclass(frozen=True)
class DateRange:
    start: int | None = None
    end: int | None = None


_ISO_YEAR_RE = re.compile(r"^\d{4}$")
_ISO_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _local_tzinfo() -> tzinfo | None:
    return datetime.now().astimezone().tzinfo


def _day_bounds(day: date) -> DateRange:
    local_tz = _local_tzinfo()
    start = datetime.combine(day, time.min, tzinfo=local_tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=local_tz)
    return DateRange(start=int(start.timestamp()), end=int(end.timestamp()))


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _next_month_start(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def _year_bounds(year: int) -> DateRange:
    try:
        start = date(year, 1, 1)
        end = date(year + 1, 1, 1)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {year}", 0) from error
    return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)


def _month_bounds(year: int, month: int, original: str) -> DateRange:
    try:
        start = date(year, month, 1)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {original}", 0) from error
    end = _next_month_start(start)
    return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)


def _year_start(day: date) -> date:
    return day.replace(month=1, day=1)


def _parse_iso_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def _instant_bounds(moment: datetime) -> DateRange:
    localized = moment if moment.tzinfo is not None else moment.replace(tzinfo=_local_tzinfo())
    start = int(localized.timestamp())
    return DateRange(start=start, end=start + 1)


def _parse_iso_endpoint(value: str) -> DateRange:
    try:
        return _day_bounds(_parse_iso_day(value))
    except QuerySyntaxError:
        pass
    if _ISO_MONTH_RE.fullmatch(value):
        year_text, month_text = value.split("-", 1)
        return _month_bounds(int(year_text), int(month_text), value)
    if _ISO_YEAR_RE.fullmatch(value):
        return _year_bounds(int(value))
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        return _instant_bounds(datetime.fromisoformat(normalized))
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def _relative_range(value: str) -> DateRange | None:
    today = datetime.now().astimezone().date()
    normalized = value.strip().casefold().replace("_", "-")
    if normalized == "today":
        return _day_bounds(today)
    if normalized == "yesterday":
        return _day_bounds(today - timedelta(days=1))
    if normalized == "this-week":
        start = today - timedelta(days=today.weekday())
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(start + timedelta(days=7)).start)
    if normalized == "last-week":
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)
    if normalized == "this-month":
        start = _month_start(today)
        next_month = _next_month_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_month).start)
    if normalized == "last-month":
        this_month = _month_start(today)
        last_month = _month_start(this_month - timedelta(days=1))
        return DateRange(start=_day_bounds(last_month).start, end=_day_bounds(this_month).start)
    if normalized == "this-year":
        start = _year_start(today)
        return _year_bounds(start.year)
    if normalized == "last-year":
        return _year_bounds(_year_start(today).year - 1)
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
            return DateRange(end=_parse_iso_endpoint(right).end)
        if not right:
            return DateRange(start=_parse_iso_endpoint(left).start)
        left_range = parse_date_range(left)
        right_range = parse_date_range(right)
        if (right_range.start or 0) < (left_range.start or 0):
            left_range, right_range = right_range, left_range
        return DateRange(start=left_range.start, end=right_range.end)
    return _parse_iso_endpoint(stripped)
