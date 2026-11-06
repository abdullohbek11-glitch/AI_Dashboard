"""``compare``: the same query over an earlier period, so a number can be read as "up 12 % on last month".

``previous_period``  the stretch just before, as long as this one. A whole number of calendar months (a month, a
                     quarter, a year ...) moves back by that many months, so "November" compares with "October"
                     and not with "the 30 days before Nov 1"; any other stretch moves back by its own length in days.
``previous_year``    the same days one year earlier (29 February becomes 28 February).

Pure date arithmetic on whole local days; the domain rewriting is in ``planner.py``.
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

KINDS = ("previous_period", "previous_year")


def months_between(start: date, end_excl: date) -> int:
    return (end_excl.year - start.year) * 12 + end_excl.month - start.month


def shift(start: date, end_excl: date, kind: str):
    """``(start, end_excl)`` of the earlier period, both as whole days."""
    if kind == "previous_year":
        return start - relativedelta(years=1), end_excl - relativedelta(years=1)
    if kind != "previous_period":
        raise ValueError("unknown comparison %r" % kind)
    if end_excl <= start:
        raise ValueError("the period is empty")
    if start.day == 1 and end_excl.day == 1:  # whole calendar months
        step = relativedelta(months=months_between(start, end_excl))
        return start - step, end_excl - step
    length = (end_excl - start).days
    return start - timedelta(days=length), start
