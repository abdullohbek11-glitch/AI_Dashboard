"""Whole-local-day meaning for dates in tool filters.

A datetime field is stored in UTC. "2026-11-01" typed without a time must mean the whole local day, or the
first hours of the month (in a UTC+5 zone) fall into the previous month. Odoo itself would read it as UTC midnight.
Same rules as ``levelix_board.lib.filters`` (this module may not import it: the core knows nothing of the board).
"""
import calendar
import re
from datetime import date, datetime, time, timedelta, timezone

import pytz
from dateutil.relativedelta import relativedelta

_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOKEN = re.compile(r"^(?P<op>[=+-])(?P<n>\d+)(?P<unit>[dwmy])$")
_UTC = "%Y-%m-%d %H:%M:%S"
COMPARISONS = ("=", "!=", "<", "<=", ">", ">=")


def is_relative(value):
    return isinstance(value, str) and value.strip().lower().split(" ")[0] == "today"


def is_day(value):
    return is_relative(value) or (isinstance(value, str) and bool(_ISO_DAY.match(value)))


def resolve_relative(expr, today):
    """``today``, ``today -7d``, ``today =1d``, ``today =1d -1m``: tokens apply left to right."""
    parts = expr.strip().lower().split()
    result = today
    for token in parts[1:]:
        match = _TOKEN.match(token)
        if not match:
            raise ValueError("cannot read %r" % token)
        op, n, unit = match["op"], int(match["n"]), match["unit"]
        if op == "=":
            if unit == "d" and 1 <= n <= 31:
                result = result.replace(day=min(n, calendar.monthrange(result.year, result.month)[1]))
            elif unit == "m" and 1 <= n <= 12:
                result = result.replace(month=n, day=min(result.day, calendar.monthrange(result.year, n)[1]))
            elif unit == "y" and 1900 <= n <= 2200:
                result = result.replace(year=n, day=min(result.day, calendar.monthrange(n, result.month)[1]))
            else:
                raise ValueError("%r is out of range" % token)
        else:
            sign = 1 if op == "+" else -1
            result += {"d": timedelta(days=sign * n), "w": timedelta(days=sign * 7 * n),
                       "m": relativedelta(months=sign * n), "y": relativedelta(years=sign * n)}[unit]
    return result


def today_in(tz, now_utc):
    return now_utc.replace(tzinfo=timezone.utc).astimezone(pytz.timezone(tz or "UTC")).date()


def local_start_utc(day, tz):
    return pytz.timezone(tz or "UTC").localize(datetime.combine(day, time.min)).astimezone(pytz.utc).strftime(_UTC)


def _day(value, today):
    return resolve_relative(value, today) if is_relative(value) else date.fromisoformat(value)


def _compare(name, op, day, kind, tz):
    if kind == "date":
        return [[name, op, day.isoformat()]]
    start, nxt = local_start_utc(day, tz), local_start_utc(day + timedelta(days=1), tz)
    if op in (">=", "<"):
        return [[name, op, start]]
    if op == "<=":
        return [[name, "<", nxt]]
    if op == ">":
        return [[name, ">=", nxt]]
    if op == "=":
        return ["&", [name, ">=", start], [name, "<", nxt]]
    return ["|", [name, "<", start], [name, ">=", nxt]]  # !=


def resolve_domain(domain, field_kind, tz, now_utc):
    """``field_kind(name)`` -> "date" | "datetime" | None. Returns a new domain; raises ValueError on a bad date."""
    today = today_in(tz, now_utc)
    out = []
    for item in domain:
        if not (isinstance(item, (list, tuple)) and len(item) == 3 and isinstance(item[0], str)):
            out.append(item)
            continue
        name, op, value = item
        kind = field_kind(name) if "." not in name else None
        if kind not in ("date", "datetime"):
            out.append(list(item))
        elif op in ("in", "not in") and isinstance(value, (list, tuple)):
            out.append([name, op, [(_day(v, today).isoformat() if kind == "date" else local_start_utc(_day(v, today), tz)) if is_day(v) else v for v in value]])
        elif is_day(value) and op in COMPARISONS:
            out.extend(_compare(name, op, _day(value, today), kind, tz))
        else:
            out.append(list(item))
    return out
