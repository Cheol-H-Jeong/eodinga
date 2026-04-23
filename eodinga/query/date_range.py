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


def _period_bounds(start_day: date, end_day: date) -> DateRange:
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


def _parse_iso_period(value: str) -> DateRange | None:
    if re.fullmatch(r"\d{4}", value):
        year = int(value)
        start = date(year, 1, 1)
        return _period_bounds(start, date(year + 1, 1, 1))
    if match := re.fullmatch(r"(\d{4})-(\d{2})", value):
        year = int(match.group(1))
        month = int(match.group(2))
        if not 1 <= month <= 12:
            raise QuerySyntaxError(f"invalid date literal: {value}", 0)
        start = date(year, month, 1)
        return _period_bounds(start, _next_month_start(start))
    return None


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


def _relative_range(value: str) -> DateRange | None:
    today = datetime.now().astimezone().date()
    normalized = value.strip().casefold().replace("_", "-")
    if normalized == "today":
        return _day_bounds(today)
    if normalized == "yesterday":
        return _day_bounds(today - timedelta(days=1))
    if normalized == "tomorrow":
        return _day_bounds(today + timedelta(days=1))
    if normalized in {"this-week", "week"}:
        start = today - timedelta(days=today.weekday())
        return _period_bounds(start, start + timedelta(days=7))
    if normalized in {"last-week", "prev-week", "previous-week"}:
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return _period_bounds(start, end)
    if normalized in {"this-month", "month"}:
        start = _month_start(today)
        next_month = _next_month_start(start)
        return _period_bounds(start, next_month)
    if normalized in {"last-month", "prev-month", "previous-month"}:
        this_month = _month_start(today)
        last_month = _month_start(this_month - timedelta(days=1))
        return _period_bounds(last_month, this_month)
    if normalized in {"this-year", "year"}:
        start = _year_start(today)
        next_year = _next_year_start(start)
        return _period_bounds(start, next_year)
    if normalized in {"last-year", "prev-year", "previous-year"}:
        this_year = _year_start(today)
        last_year = this_year.replace(year=this_year.year - 1)
        return _period_bounds(last_year, this_year)
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
