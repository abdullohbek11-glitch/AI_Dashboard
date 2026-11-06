"""Date parts (weekday, hour, month ...) for grouping, and the order of a grouped question. Pure; no Odoo.

``day_of_week`` counts from Sunday (0), as Odoo does; a reader expects Monday first, so weekdays are put in that order.
"""
DATE_PARTS = (
    "year_number", "quarter_number", "month_number", "iso_week_number", "day_of_year",
    "day_of_month", "day_of_week", "hour_number", "minute_number", "second_number",
)
HOUR_PARTS = ("hour_number", "minute_number", "second_number")  # a date without a time has none of these


class OrderError(ValueError):
    pass


def monday_first(value) -> int:
    """Sort key of an Odoo weekday number (Sunday = 0): Monday = 0 ... Sunday = 6."""
    return (int(value) + 6) % 7


def label(value, part, day_names=None, month_names=None) -> str:
    """What a group of a date part is called: ``Mon``, ``15:00``, ``Mar``, ``Q2``, or the number itself.

    ``day_names`` are the names Monday..Sunday and ``month_names`` January..December in the reader's language (English if absent)."""
    if value is None or value is False:
        return "Not set"
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value)
    if part == "day_of_week":
        names = day_names or ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        return names[monday_first(number)]
    if part == "month_number" and 1 <= number <= 12:
        names = month_names or ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        return names[number - 1]
    if part == "hour_number":
        return "%02d:00" % number
    if part == "quarter_number":
        return "Q%d" % number
    return str(number)


def normalise_order(order, groupby, aggregates):
    """The order a model wrote, as Odoo needs it (``"date:day asc"``), or ``OrderError`` saying what is allowed.

    Accepted slips: ``"date:asc"`` / ``"date asc"`` for a date grouped by day, ``"price_subtotal desc"`` for ``price_subtotal:sum``."""
    if order in (None, False, ""):
        return None
    options = list(groupby) + list(aggregates)
    terms = []
    for raw in str(order).split(","):
        words = raw.split()
        if not words:
            continue
        if len(words) > 2 or (len(words) == 2 and words[1].lower() not in ("asc", "desc")):
            raise OrderError(_help(order, options))
        key, direction = words[0], words[1].lower() if len(words) == 2 else "asc"
        head, _sep, tail = key.rpartition(":")
        if head and tail.lower() in ("asc", "desc"):  # "date:asc"
            key, direction = head, tail.lower()
        terms.append("%s %s" % (_resolve(key, groupby, aggregates, order, options), direction))
    return ", ".join(terms) or None


def _resolve(key, groupby, aggregates, order, options):
    if key in options:
        return key
    same_field = [g for g in groupby if g.partition(":")[0] == key] or [a for a in aggregates if a.partition(":")[0] == key]
    if len(same_field) == 1:
        return same_field[0]
    raise OrderError(_help(order, options))


def _help(order, options):
    return "Cannot order by '%s'. Order by one of: %s, each followed by asc or desc (for example '%s asc')." % (
        order, ", ".join(options) or "nothing (there is nothing to order)", options[0] if options else "date:day")
