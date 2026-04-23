from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from eodinga.query.dsl import QuerySyntaxError


@dataclass(frozen=True)
class DateRange:
    start: int | None = None
    end: int | None = None


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


def _parse_iso_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def _parse_named_range(value: str, today: date) -> DateRange | None:
    if value == "today":
        return _day_bounds(today)
    if value == "yesterday":
        return _day_bounds(today - timedelta(days=1))
    if value == "this-week":
        start = today - timedelta(days=today.weekday())
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(start + timedelta(days=7)).start)
    if value == "last-week":
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)
    if value == "this-month":
        start = _month_start(today)
        next_month = _next_month_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_month).start)
    if value == "last-month":
        this_month = _month_start(today)
        last_month = _month_start(this_month - timedelta(days=1))
        return DateRange(start=_day_bounds(last_month).start, end=_day_bounds(this_month).start)
    return None


def _instant_bounds(moment: datetime) -> DateRange:
    localized = moment if moment.tzinfo is not None else moment.replace(tzinfo=_local_tzinfo())
    start = int(localized.timestamp())
    return DateRange(start=start, end=start + 1)


def _parse_endpoint(value: str, today: date) -> DateRange:
    named_range = _parse_named_range(value, today)
    if named_range is not None:
        return named_range
    try:
        return _day_bounds(_parse_iso_day(value))
    except QuerySyntaxError:
        pass
    normalized = value.replace("Z", "+00:00")
    try:
        return _instant_bounds(datetime.fromisoformat(normalized))
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def parse_date_range(value: str) -> DateRange:
    today = datetime.now().astimezone().date()
    named_range = _parse_named_range(value, today)
    if named_range is not None:
        return named_range
    if ".." in value:
        left, right = (part.strip() for part in value.split("..", 1))
        if not left and not right:
            raise QuerySyntaxError(f"invalid date literal: {value}", 0)
        if not left:
            return DateRange(end=_parse_endpoint(right, today).end)
        if not right:
            return DateRange(start=_parse_endpoint(left, today).start)
        left_range = _parse_endpoint(left, today)
        right_range = _parse_endpoint(right, today)
        if (right_range.start or 0) < (left_range.start or 0):
            left_range, right_range = right_range, left_range
        return DateRange(start=left_range.start, end=right_range.end)
    return _parse_endpoint(value, today)
