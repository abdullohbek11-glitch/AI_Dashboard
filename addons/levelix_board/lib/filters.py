"""Relative dates and day semantics for domains.

A spec uses relative dates so a dashboard stays current:

    today            today                          (in the viewer's time zone)
    today -7d        a week ago
    today =1d        first day of this month
    today =1d -1m    first day of last month
    today =1m =1d    January 1st of this year

Tokens after ``today`` are applied left to right: ``=Nd``/``=Nm``/``=Ny`` set the
day / month / year, ``+Nd -Nw +Nm -Ny`` shift by days / weeks / months / years.

Day semantics on datetime fields: a value without a time ("2026-11-05" or a
relative date) means that whole *local* day. ``<=`` and ``>`` therefore move to
the next local midnight, and ``=`` becomes a range, so "up to today" includes
today. Values with a time are left alone.
"""
import calendar
import re
from datetime import date, datetime, time, timedelta, timezone

import pytz
from dateutil.relativedelta import relativedelta

from . import domain as domain_lib

_TOKEN = re.compile(r"^(?P<op>[=+-])(?P<n>\d+)(?P<unit>[dwmy])$")
_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UTC_FORMAT = "%Y-%m-%d %H:%M:%S"


def is_relative(value) -> bool:
    return isinstance(value, str) and value.strip().lower().split(" ")[0] == "today"


def is_day_only(value) -> bool:
    return is_relative(value) or (isinstance(value, str) and bool(_ISO_DAY.match(value)))


def _month_length(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def resolve_relative(expr: str, today: date) -> date:
    """Resolve ``today =1d -1m`` and friends; raises ``ValueError`` when malformed."""
    parts = expr.strip().lower().split()
    if not parts or parts[0] != "today":
        raise ValueError("a relative date starts with 'today'")
    result = today
    for token in parts[1:]:
        match = _TOKEN.match(token)
        if not match:
            raise ValueError("cannot read %r (use e.g. -7d, +1w, -1m, =1d)" % token)
        op, n, unit = match["op"], int(match["n"]), match["unit"]
        if op == "=":
            if unit == "d" and 1 <= n <= 31:
                result = result.replace(day=min(n, _month_length(result.year, result.month)))
            elif unit == "m" and 1 <= n <= 12:
                result = result.replace(month=n, day=min(result.day, _month_length(result.year, n)))
            elif unit == "y" and 1900 <= n <= 2200:
                result = result.replace(year=n, day=min(result.day, _month_length(n, result.month)))
            else:
                raise ValueError("%r is out of range (or '=w' which does not exist)" % token)
        else:
            sign = 1 if op == "+" else -1
            delta = {
                "d": timedelta(days=sign * n),
                "w": timedelta(days=sign * 7 * n),
                "m": relativedelta(months=sign * n),
                "y": relativedelta(years=sign * n),
            }[unit]
            result = result + delta
    return result


def today_in(tz: str, now_utc: datetime) -> date:
    """The current calendar day in the viewer's time zone."""
    zone = pytz.timezone(tz or "UTC")
    return now_utc.replace(tzinfo=timezone.utc).astimezone(zone).date()


def local_start_utc(day: date, tz: str) -> str:
    """Local midnight of ``day`` as the UTC string Odoo stores."""
    zone = pytz.timezone(tz or "UTC")
    local = zone.localize(datetime.combine(day, time.min))
    return local.astimezone(pytz.utc).strftime(_UTC_FORMAT)


def local_date_of(value: str, field_type: str, tz: str) -> date:
    """The local calendar day of a stored date / datetime string."""
    if field_type == "date" or len(value) <= 10:
        return date.fromisoformat(value[:10])
    moment = datetime.strptime(value[:19], _UTC_FORMAT).replace(tzinfo=timezone.utc)
    return moment.astimezone(pytz.timezone(tz or "UTC")).date()


def _as_day(value: str, today: date) -> date:
    return resolve_relative(value, today) if is_relative(value) else date.fromisoformat(value)


def check_date_value(value) -> None:
    """Raise ``ValueError`` if a string cannot be read as a day (used by the validator)."""
    if isinstance(value, str) and is_relative(value):
        resolve_relative(value, date(2000, 1, 1))
    elif isinstance(value, str) and _ISO_DAY.match(value):
        date.fromisoformat(value)


def _comparison(leaf_field, op, value, day: date, field_type: str, tz: str):
    """One comparison against a whole day, as domain items."""
    if field_type == "date":
        return [[leaf_field, op, day.isoformat()]]
    start = local_start_utc(day, tz)
    nxt = local_start_utc(day + timedelta(days=1), tz)
    if op in (">=", "<"):
        return [[leaf_field, op, start]]
    if op == "<=":
        return [[leaf_field, "<", nxt]]
    if op == ">":
        return [[leaf_field, ">=", nxt]]
    if op == "=":
        return ["&", [leaf_field, ">=", start], [leaf_field, "<", nxt]]
    if op == "!=":
        return ["|", [leaf_field, "<", start], [leaf_field, ">=", nxt]]
    return [[leaf_field, op, start]]


def resolve_domain(domain, field_types, tz: str, now_utc: datetime) -> list:
    """Replace relative / day-only values by concrete ones.

    ``field_types`` maps a field name to its type (``None`` for unknown or dotted
    names, which are left untouched). The input is not modified.
    """
    today = today_in(tz, now_utc)
    out = []
    for item in domain:
        if not domain_lib.is_leaf(item):
            out.append(item)
            continue
        name, op, value = item
        ftype = field_types(name)
        if ftype not in ("date", "datetime"):
            out.append(list(item))
            continue
        if op in ("in", "not in") and isinstance(value, (list, tuple)):
            resolved = []
            for element in value:
                if is_day_only(element):
                    day = _as_day(element, today)
                    resolved.append(day.isoformat() if ftype == "date" else local_start_utc(day, tz))
                else:
                    resolved.append(element)
            out.append([name, op, resolved])
        elif is_day_only(value) and op in ("=", "!=", "<", "<=", ">", ">="):
            out.extend(_comparison(name, op, value, _as_day(value, today), ftype, tz))
        else:
            out.append(list(item))
    return out


def date_bounds(domain, field_name: str, field_type: str, tz: str):
    """``(first_day, day_after_last)`` the domain always imposes on a date field.

    Either side is ``None`` when the domain does not bound it. Only conditions
    that must always hold count (top level / under ``&``).
    """
    start = end = None
    for name, op, value in domain_lib.always_true_leaves(domain_lib.parse(domain)):
        if name != field_name or not isinstance(value, str):
            continue
        try:
            day = local_date_of(value, field_type, tz)
        except ValueError:
            continue
        if op == ">=" or op == "=":
            start = day if start is None else max(start, day)
        if op == ">":
            day_after = day + timedelta(days=1) if field_type == "date" else day
            start = day_after if start is None else max(start, day_after)
        if op == "<":
            end = day if end is None else min(end, day)
        if op == "<=":
            day_after = day + timedelta(days=1)
            end = day_after if end is None else min(end, day_after)
    return start, end


def start_of(day: date, granularity: str, week_start: int = 1) -> date:
    """First day of the bucket ``day`` falls in. ``week_start``: 1 = Monday ... 7 = Sunday."""
    if granularity == "week":
        return day - timedelta(days=(day.weekday() - (week_start - 1)) % 7)
    if granularity == "month":
        return day.replace(day=1)
    if granularity == "quarter":
        return day.replace(month=((day.month - 1) // 3) * 3 + 1, day=1)
    if granularity == "year":
        return day.replace(month=1, day=1)
    return day


def next_bucket(day: date, granularity: str) -> date:
    return day + {
        "day": relativedelta(days=1), "week": relativedelta(weeks=1), "month": relativedelta(months=1),
        "quarter": relativedelta(months=3), "year": relativedelta(years=1),
    }[granularity]
