"""Dashboard filters: the controls above the widgets (period, company, a choice).

A filter in the spec names the widgets it touches by *model*: ``applies_to`` maps a model to the field of that model the
filter constrains. Every widget whose source is in the map gets the filter's condition added to its domain; any other
widget is left alone. The reader's choices (``filter_values``) are never saved in the spec; only ``default`` is.

    {"id": "period", "type": "date_range", "label": "Period", "default": "last_30_days",
     "applies_to": {"sale.report": "date", "sale.order": "date_order"}}
    {"id": "seller", "type": "select", "label": "Salesperson", "applies_to": {"sale.report": "user_id"}}
    {"id": "company", "type": "company", "label": "Company", "applies_to": {"sale.report": "company_id"}}
    {"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": "untaxed",
     "applies_to": {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_total"}}}

An ``amount_basis`` filter is not a condition but a switch: on the models it names, every measure that reads one of the two
money fields reads the one the reader chose (a measure marked ``"fixed": true`` keeps its own). So one dashboard shows
amounts without tax or with tax, with a single measure per widget.

Values the browser sends: a preset name or ``{"from": "2026-10-01", "to": "2026-10-31"}`` for a period; a list of
company ids; one value or a list of values (ids or selection keys) for a choice. Empty means "no filter".
Pure; the database part (options, the companies a user may pick) is in ``models/``.
"""
from dataclasses import replace
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from . import filters as dates
from .catalog import TEMPORAL_TYPES
from .errors import BoardError
from .i18n import t

TYPES = ("date_range", "company", "select", "amount_basis")
BASES = ("untaxed", "taxed")
BASIS_LABELS = {"untaxed": "Without tax", "taxed": "With tax"}
KEYS = ("id", "type", "label", "default", "applies_to")
MAX_FILTERS = 6
MAX_LABEL = 60
MAX_CHOICES = 50
PRESETS = (
    "all", "today", "yesterday", "this_week", "last_week", "last_7_days", "last_30_days", "last_90_days",
    "this_month", "last_month", "this_quarter", "last_quarter", "this_year", "last_year",
)
PRESET_LABELS = {
    "all": "All time", "today": "Today", "yesterday": "Yesterday", "this_week": "This week", "last_week": "Last week",
    "last_7_days": "Last 7 days", "last_30_days": "Last 30 days", "last_90_days": "Last 90 days", "this_month": "This month",
    "last_month": "Last month", "this_quarter": "This quarter", "last_quarter": "Last quarter", "this_year": "This year",
    "last_year": "Last year",
}


def _bad(path, message, code="BAD_FILTER"):
    return BoardError(code, path, message)


# -- periods ------------------------------------------------------------------------------------------------------------

def preset_range(name: str, today: date, week_start: int = 1):
    """``(first_day, last_day)`` of a preset; ``(None, None)`` for "all". Calendar presets cover the whole period,
    "last N days" end today."""
    if name == "all":
        return None, None
    if name == "today":
        return today, today
    if name == "yesterday":
        return today - timedelta(days=1), today - timedelta(days=1)
    if name in ("this_week", "last_week"):
        start = dates.start_of(today, "week", week_start)
        if name == "last_week":
            start -= timedelta(days=7)
        return start, start + timedelta(days=6)
    if name in ("last_7_days", "last_30_days", "last_90_days"):
        return today - timedelta(days=int(name.split("_")[1]) - 1), today
    unit, months = {"month": ("month", 1), "quarter": ("quarter", 3), "year": ("year", 12)}[name.split("_", 1)[1]]
    start = dates.start_of(today, unit)
    if name.startswith("last_"):
        start -= relativedelta(months=months)
    return start, start + relativedelta(months=months) - timedelta(days=1)


def _custom_day(value, path):
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise _bad(path, t("A date must be written as YYYY-MM-DD."))
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise _bad(path, t("Cannot read the date %r: %s.") % (value, error)) from error


def period_range(value, today: date, week_start: int = 1, path: str = "filter_values"):
    """``(first_day, last_day)`` for a preset or a ``{"from", "to"}`` pair; either end may be ``None``."""
    if value is None or value == "":
        return None, None
    if isinstance(value, str):
        if value not in PRESETS:
            raise _bad(path, t("Unknown period '%s'. Use one of: %s.") % (value, ", ".join(PRESETS)))
        return preset_range(value, today, week_start)
    if not isinstance(value, dict) or set(value) - {"from", "to"}:
        raise _bad(path, t("A period is a preset name or {\"from\": \"YYYY-MM-DD\", \"to\": \"YYYY-MM-DD\"}."))
    start, end = _custom_day(value.get("from"), path + ".from"), _custom_day(value.get("to"), path + ".to")
    if start and end and start > end:
        raise _bad(path, t("The period starts after it ends."))
    return start, end


def describe_period(value, today: date, week_start: int = 1) -> str:
    """The period in words, for the reader and for "how it was calculated"."""
    start, end = period_range(value, today, week_start)
    if isinstance(value, str) and value in PRESET_LABELS:
        name = t(PRESET_LABELS[value])
        return name if value == "all" else "%s (%s – %s)" % (name, start.isoformat(), end.isoformat())
    if start and end:
        return "%s – %s" % (start.isoformat(), end.isoformat())
    return t("from %s") % start.isoformat() if start else t("until %s") % end.isoformat() if end else t("All time")


# -- checking the filters of a spec ----------------------------------------------------------------------------------------

def check(raw_filters, catalog) -> list:
    """Problems in the ``filters`` block of a spec (an empty list when it is fine)."""
    errors = []
    if not isinstance(raw_filters, (list, tuple)):
        return [_bad("filters", t("'filters' is a list."))]
    if len(raw_filters) > MAX_FILTERS:
        errors.append(_bad("filters", t("At most %d filters are allowed.") % MAX_FILTERS))
    seen = set()
    for index, item in enumerate(raw_filters[:MAX_FILTERS]):
        path = "filters[%d]" % index
        if not isinstance(item, dict):
            errors.append(_bad(path, t("A filter is an object.")))
            continue
        unknown = sorted(set(item) - set(KEYS))
        if unknown:
            errors.append(BoardError("UNKNOWN_KEY", path, t("Unknown key(s) %s. Allowed: %s.") % (", ".join(unknown), ", ".join(KEYS))))
            continue
        fid, kind = item.get("id"), item.get("type")
        if not isinstance(fid, str) or not fid or len(fid) > 32 or not fid.replace("_", "").isalnum() or not fid[0].isalpha():
            errors.append(_bad(path + ".id", t("A filter needs an 'id' like 'period' (letters, digits, underscore).")))
        elif fid in seen:
            errors.append(BoardError("DUPLICATE_ID", path + ".id", t("Filter id '%s' is used twice.") % fid))
        seen.add(fid)
        if kind not in TYPES:
            errors.append(_bad(path + ".type", t("Unknown filter type %r. Allowed: %s.") % (kind, ", ".join(TYPES))))
            continue
        label = item.get("label")
        if not isinstance(label, str) or not 0 < len(label) <= MAX_LABEL:
            errors.append(_bad(path + ".label", t("A filter needs a short 'label' (up to %d characters).") % MAX_LABEL))
        if kind == "amount_basis":
            mapped = _check_basis_map(item.get("applies_to"), catalog, path + ".applies_to", errors)
            if any(i != index and isinstance(o, dict) and o.get("type") == "amount_basis" for i, o in enumerate(raw_filters)):
                errors.append(_bad(path, t("A dashboard has one 'Amounts' filter; merge the models into one.")))
        else:
            mapped = _check_applies(item.get("applies_to"), kind, catalog, path + ".applies_to", errors)
        if "default" in item and mapped:
            try:
                parse_value(item, item["default"], date(2000, 1, 1), allowed_companies=None, path=path + ".default")
            except BoardError as error:
                errors.append(error)
    return errors


def _check_applies(applies, kind, catalog, path, errors) -> bool:
    if not isinstance(applies, dict) or not applies:
        errors.append(_bad(path, t("'applies_to' maps each model the filter touches to one of its fields.")))
        return False
    good = True
    for model_name, field_name in applies.items():
        mpath = "%s.%s" % (path, model_name)
        model = catalog.model(model_name)
        if model is None:
            errors.append(BoardError("UNKNOWN_MODEL", mpath, t("Model '%s' does not exist.") % model_name))
            good = False
            continue
        if not model.accessible:
            errors.append(BoardError("NO_ACCESS", mpath, t("You are not allowed to read '%s'.") % model.label))
            good = False
            continue
        field = model.field(field_name) if isinstance(field_name, str) else None
        if field is None or not field.store:
            errors.append(BoardError("UNKNOWN_FIELD", mpath, t("Model '%(model)s' has no stored field '%(field)s'.") % {"model": model_name, "field": field_name}))
            good = False
        elif kind == "date_range" and field.type not in TEMPORAL_TYPES:
            errors.append(_bad(mpath, t("A period filter needs a date field; '%s' is not one.") % field.label))
            good = False
        elif kind == "company" and not (field.type == "many2one" and field.relation == "res.company"):
            errors.append(_bad(mpath, t("A company filter needs a link to the company; '%s' is not one.") % field.label))
            good = False
        elif kind == "select" and field.type not in ("selection", "many2one"):
            errors.append(_bad(mpath, t("A choice filter needs a selection or a link to a record; '%s' is neither.") % field.label))
            good = False
    return good


def _check_basis_map(applies, catalog, path, errors) -> bool:
    """``{model: {"untaxed": field, "taxed": field}}``: both fields stored, summable money, and different."""
    if not isinstance(applies, dict) or not applies:
        errors.append(_bad(path, t("'applies_to' maps each model to its two money fields: {\"untaxed\": field, \"taxed\": field}.")))
        return False
    good = True
    for model_name, pair in applies.items():
        mpath = "%s.%s" % (path, model_name)
        model = catalog.model(model_name)
        if model is None:
            errors.append(BoardError("UNKNOWN_MODEL", mpath, t("Model '%s' does not exist.") % model_name))
            good = False
            continue
        if not model.accessible:
            errors.append(BoardError("NO_ACCESS", mpath, t("You are not allowed to read '%s'.") % model.label))
            good = False
            continue
        if not isinstance(pair, dict) or set(pair) != set(BASES) or not all(isinstance(v, str) for v in pair.values()):
            errors.append(_bad(mpath, t("Name both money fields: {\"untaxed\": field, \"taxed\": field}.")))
            good = False
            continue
        if pair["untaxed"] == pair["taxed"]:
            errors.append(_bad(mpath, t("The untaxed and the taxed field must be different fields.")))
            good = False
        for basis in BASES:
            field = model.field(pair[basis])
            if field is None or not field.store or field.type not in ("monetary", "float", "integer") or field.aggregator != "sum":
                errors.append(BoardError("UNKNOWN_FIELD", mpath, t("'%(field)s' is not a stored money field of '%(model)s' that can be added up.") % {"field": pair[basis], "model": model_name}))
                good = False
    return good


# -- values ----------------------------------------------------------------------------------------------------------------

def parse_value(item: dict, value, today: date, allowed_companies=None, path: str = "filter_values"):
    """The value as it will be used: ``("range", first, last)`` or ``("in", [values])``; ``None`` for "no filter"."""
    kind = item["type"]
    if kind == "amount_basis":
        if value not in BASES:
            raise _bad(path, t("The amounts are 'untaxed' or 'taxed'."))
        return ("basis", value)
    if kind == "date_range":
        start, end = period_range(value, today, path=path)
        return None if start is None and end is None else ("range", start, end)
    items = value if isinstance(value, (list, tuple)) else [] if value in (None, "") else [value]
    if len(items) > MAX_CHOICES:
        raise _bad(path, t("Too many values chosen (at most %d).") % MAX_CHOICES)
    if not items:
        return None
    if kind == "company":
        if not all(isinstance(i, int) and not isinstance(i, bool) for i in items):
            raise _bad(path, t("Companies are chosen by their ids."))
        if allowed_companies is not None and not set(items) <= set(allowed_companies):
            raise _bad(path, t("You can only choose companies you work in."), "NO_ACCESS")
        return ("in", list(items))
    if not all(isinstance(i, (str, int)) and not isinstance(i, bool) for i in items):
        raise _bad(path, t("A choice is text or an id."))
    return ("in", list(items))


def check_choices(item: dict, parsed, catalog) -> None:
    """A choice of a selection field must be one of its values."""
    if item["type"] != "select" or parsed is None:
        return
    for model_name, field_name in item["applies_to"].items():
        model = catalog.model(model_name)
        field = model.field(field_name) if model else None
        if field is not None and field.type == "selection" and field.selection:
            allowed = [key for key, _label in field.selection]
            for value in parsed[1]:
                if value not in allowed:
                    raise _bad("filter_values.%s" % item["id"], t("'%(value)s' is not a value of '%(field)s'.") % {"value": value, "field": field.label})
        break


def resolve(raw_filters, values, catalog, today: date, week_start: int = 1, allowed_companies=None):
    """``({model: [domain leaves]}, {filter id: parsed value})`` for the reader's choices.

    ``values`` may leave a filter out (its ``default`` applies); a filter id the dashboard does not have is an error.
    """
    by_id = {f["id"]: f for f in raw_filters}
    values = values or {}
    unknown = [k for k in values if k not in by_id]
    if unknown:
        raise _bad("filter_values.%s" % unknown[0], t("The dashboard has no filter '%s'.") % unknown[0])
    leaves, parsed_values = {}, {}
    for fid, item in by_id.items():
        value = values[fid] if fid in values else item.get("default")
        if item["type"] == "amount_basis" and value in (None, ""):
            value = "untaxed"  # the first choice, until the reader makes one
        parsed = parse_value(item, value, today, allowed_companies, "filter_values.%s" % fid)
        check_choices(item, parsed, catalog)
        parsed_values[fid] = parsed
        if parsed is None or parsed[0] == "basis":  # a basis is a switch, not a condition: see ``swaps``
            continue
        for model_name, field_name in item["applies_to"].items():
            if parsed[0] == "in":
                leaves.setdefault(model_name, []).append([field_name, "in", list(parsed[1])])
            else:
                _kind, start, end = parsed
                if start is not None:
                    leaves.setdefault(model_name, []).append([field_name, ">=", start.isoformat()])
                if end is not None:
                    leaves.setdefault(model_name, []).append([field_name, "<=", end.isoformat()])
    return leaves, parsed_values


# -- the amounts switch --------------------------------------------------------------------------------------------------------

def swaps(raw_filters, parsed_values) -> dict:
    """``{model: {field: field}}``: for each model, which money field to read instead of which.

    Only the field of the basis that was *not* chosen is listed (it is replaced by the chosen one)."""
    out = {}
    for item in raw_filters:
        parsed = parsed_values.get(item["id"])
        if item["type"] != "amount_basis" or not parsed:
            continue
        chosen = parsed[1]
        other = "taxed" if chosen == "untaxed" else "untaxed"
        for model_name, pair in item["applies_to"].items():
            out.setdefault(model_name, {})[pair[other]] = pair[chosen]
    return out


def basis_mapping(raw_filters, model_name: str, chosen: str) -> dict:
    """The swap of one model for one basis, without resolving the reader's values (the validator checks both)."""
    other = "taxed" if chosen == "untaxed" else "untaxed"
    for item in raw_filters:
        if isinstance(item, dict) and item.get("type") == "amount_basis" and model_name in (item.get("applies_to") or {}):
            pair = item["applies_to"][model_name]
            if isinstance(pair, dict) and chosen in pair and other in pair:
                return {pair[other]: pair[chosen]}
    return {}


def swap_measures(widget, mapping: dict):
    """The widget with its money measures reading the chosen field; ``fixed`` measures and calculated ones stay as they are."""
    if not mapping:
        return widget
    measures = tuple(
        replace(m, field=mapping[m.field]) if (m.field in mapping and not m.fixed and m.calc is None) else m for m in widget.data.measures)
    if measures == widget.data.measures:
        return widget
    return replace(widget, data=replace(widget.data, measures=measures))


def follows_basis(widget, raw_filters) -> bool:
    """Does any measure of this widget follow the amounts switch (so "how it was calculated" should say which basis)?"""
    for item in raw_filters:
        if isinstance(item, dict) and item.get("type") == "amount_basis":
            pair = (item.get("applies_to") or {}).get(widget.data.source)
            if isinstance(pair, dict) and any(m.field in pair.values() and not m.fixed for m in widget.data.measures):
                return True
    return False
