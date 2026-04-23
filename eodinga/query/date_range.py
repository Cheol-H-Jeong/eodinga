from __future__ import annotations

import re
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


def _parse_iso_day(value: str, *, position: int = 0) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", position) from error


def _parse_iso_span(value: str, *, position: int = 0) -> DateRange | None:
    if re.fullmatch(r"\d{4}", value):
        start = date(int(value), 1, 1)
        return _span_bounds(start, _next_year_start(start))
    month_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{2})", value)
    if month_match is not None:
        try:
            start = date(int(month_match.group("year")), int(month_match.group("month")), 1)
        except ValueError as error:
            raise QuerySyntaxError(f"invalid date literal: {value}", position) from error
        return _span_bounds(start, _next_month_start(start))
    week_match = re.fullmatch(r"(?P<year>\d{4})-[Ww](?P<week>\d{2})", value)
    if week_match is None:
        return None
    try:
        start = date.fromisocalendar(int(week_match.group("year")), int(week_match.group("week")), 1)
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", position) from error
    return _span_bounds(start, start + timedelta(days=7))


def _instant_bounds(moment: datetime) -> DateRange:
    localized = moment if moment.tzinfo is not None else moment.replace(tzinfo=_local_tzinfo())
    start = int(localized.timestamp())
    return DateRange(start=start, end=start + 1)


def _parse_iso_endpoint(value: str, *, position: int = 0) -> DateRange:
    span = _parse_iso_span(value, position=position)
    if span is not None:
        return span
    try:
        return _day_bounds(_parse_iso_day(value, position=position))
    except QuerySyntaxError:
        pass
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        return _instant_bounds(datetime.fromisoformat(normalized))
    except ValueError as error:
        raise QuerySyntaxError(f"invalid date literal: {value}", position) from error


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
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(start + timedelta(days=7)).start)
    if normalized in {"last-week", "prev-week", "previous-week"}:
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(end).start)
    if normalized in {"this-month", "month"}:
        start = _month_start(today)
        next_month = _next_month_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_month).start)
    if normalized in {"last-month", "prev-month", "previous-month"}:
        this_month = _month_start(today)
        last_month = _month_start(this_month - timedelta(days=1))
        return DateRange(start=_day_bounds(last_month).start, end=_day_bounds(this_month).start)
    if normalized in {"this-year", "year"}:
        start = _year_start(today)
        next_year = _next_year_start(start)
        return DateRange(start=_day_bounds(start).start, end=_day_bounds(next_year).start)
    if normalized in {"last-year", "prev-year", "previous-year"}:
        this_year = _year_start(today)
        last_year = this_year.replace(year=this_year.year - 1)
        return DateRange(start=_day_bounds(last_year).start, end=_day_bounds(this_year).start)
    return None


def parse_date_range(value: str, *, position: int = 0) -> DateRange:
    stripped = value.strip()
    relative = _relative_range(stripped)
    if relative is not None:
        return relative
    if ".." in stripped:
        left, right = (part.strip() for part in stripped.split("..", 1))
        if not left and not right:
            raise QuerySyntaxError(f"invalid date literal: {stripped}", position)
        separator = stripped.index("..")
        right_position = position + separator + 2
        if not left:
            return DateRange(end=parse_date_range(right, position=right_position).end)
        if not right:
            return DateRange(start=parse_date_range(left, position=position).start)
        left_range = parse_date_range(left, position=position)
        right_range = parse_date_range(right, position=right_position)
        if (right_range.start or 0) < (left_range.start or 0):
            left_range, right_range = right_range, left_range
        return DateRange(start=left_range.start, end=right_range.end)
    return _parse_iso_endpoint(stripped, position=position)
