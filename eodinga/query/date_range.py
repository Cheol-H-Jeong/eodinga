from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
import re

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


def _parse_iso_period(value: str) -> DateRange | None:
    if re.fullmatch(r"\d{4}", value):
        start_day = date(int(value), 1, 1)
        return DateRange(start=_day_bounds(start_day).start, end=_day_bounds(date(int(value) + 1, 1, 1)).start)
    match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if match is None:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    try:
        start_day = date(year, month, 1)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error
    return DateRange(start=_day_bounds(start_day).start, end=_day_bounds(_next_month_start(start_day)).start)


def _instant_bounds(moment: datetime) -> DateRange:
    localized = moment if moment.tzinfo is not None else moment.replace(tzinfo=_local_tzinfo())
    start = int(localized.timestamp())
    return DateRange(start=start, end=start + 1)


def _parse_iso_endpoint(value: str) -> DateRange:
    period = _parse_iso_period(value)
    if period is not None:
        return period
    try:
        return _day_bounds(_parse_iso_day(value))
    except QuerySyntaxError:
        pass
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        return _instant_bounds(datetime.fromisoformat(normalized))
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", 0) from error


def parse_date_range(value: str) -> DateRange:
    today = datetime.now().astimezone().date()
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
    if ".." in value:
        left, right = (part.strip() for part in value.split("..", 1))
        if not left and not right:
            raise QuerySyntaxError(f"invalid date literal: {value}", 0)
        if not left:
            return DateRange(end=_parse_iso_endpoint(right).end)
        if not right:
            return DateRange(start=_parse_iso_endpoint(left).start)
        left_range = _parse_iso_endpoint(left)
        right_range = _parse_iso_endpoint(right)
        if (right_range.start or 0) < (left_range.start or 0):
            left_range, right_range = right_range, left_range
        return DateRange(start=left_range.start, end=right_range.end)
    return _parse_iso_endpoint(value)
