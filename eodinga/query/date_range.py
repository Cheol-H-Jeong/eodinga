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


def _instant_bounds(moment: datetime) -> DateRange:
    localized = moment if moment.tzinfo is not None else moment.replace(tzinfo=_local_tzinfo())
    start = int(localized.timestamp())
    return DateRange(start=start, end=start + 1)


def _parse_iso_endpoint(value: str) -> DateRange:
    try:
        return _day_bounds(_parse_iso_day(value))
    except QuerySyntaxError:
        pass
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        return _instant_bounds(datetime.fromisoformat(normalized))
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def _parse_endpoint_range(value: str) -> DateRange:
    if value == "today":
        return _day_bounds(datetime.now().astimezone().date())
    if value == "yesterday":
        return _day_bounds(datetime.now().astimezone().date() - timedelta(days=1))
    if value == "this-week":
        today = datetime.now().astimezone().date()
        start = today - timedelta(days=today.weekday())
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(start + timedelta(days=7)).start)
    if value == "last-week":
        today = datetime.now().astimezone().date()
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)
    if value == "this-month":
        today = datetime.now().astimezone().date()
        start = _month_start(today)
        next_month = _next_month_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_month).start)
    if value == "last-month":
        today = datetime.now().astimezone().date()
        this_month = _month_start(today)
        last_month = _month_start(this_month - timedelta(days=1))
        return DateRange(start=_day_bounds(last_month).start, end=_day_bounds(this_month).start)
    return _parse_iso_endpoint(value)


def parse_date_range(value: str) -> DateRange:
    if ".." in value:
        left, right = (part.strip() for part in value.split("..", 1))
        if not left and not right:
            raise QuerySyntaxError(f"invalid date literal: {value}", 0)
        if not left:
            return DateRange(end=_parse_endpoint_range(right).end)
        if not right:
            return DateRange(start=_parse_endpoint_range(left).start)
        left_range = _parse_endpoint_range(left)
        right_range = _parse_endpoint_range(right)
        if (right_range.start or 0) < (left_range.start or 0):
            left_range, right_range = right_range, left_range
        return DateRange(start=left_range.start, end=right_range.end)
    return _parse_endpoint_range(value)
