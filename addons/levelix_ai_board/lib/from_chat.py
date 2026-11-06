"""Keeping a chat answer as a dashboard: the query behind a chart, number or table becomes a widget.

The assistant's ``aggregate`` tool leaves ``query`` on its blocks: the model, the conditions *as they were asked* (so
"the last 30 days" is still relative and the dashboard stays current), the grouping, the measures and their names.
This turns that into widgets of the dashboard spec. The result is checked like any other spec before it is stored.
Pure; no Odoo.
"""
from odoo.addons.levelix_board.lib.spec import GRANULARITIES, SHAPES

from . import amounts

MAX_LIMIT = 500
SAVABLE_BLOCKS = ("kpi", "chart", "table")


def savable(block) -> bool:
    """Does this block carry a query that can become a widget?"""
    if not isinstance(block, dict):
        return False
    query = block.get("query")
    return bool(block.get("type") in SAVABLE_BLOCKS and isinstance(query, dict) and query.get("model") and query.get("aggregates"))


def _dimension(text, is_date, model):
    field, _sep, granularity = text.partition(":")
    out = {"field": field}
    if granularity:
        out["granularity"] = granularity
    elif is_date(model, field):
        out["granularity"] = "month"  # what the chat uses for a date it was not told how to group
    return out


def _collapse_amounts(query):
    """``(specs, labels, alias, basis)``: when the answer shows both money fields of a model, the dashboard keeps the first and
    lets its "Amounts" switch stand for the other. ``alias`` maps the dropped spec to the kept one (for the sort order);
    ``basis`` is the field the reader saw first (``None`` when no money field is involved)."""
    labels = list(query.get("labels") or [])
    specs, kept_labels, alias, basis, first = [], [], {}, None, None
    for index, spec in enumerate(query["aggregates"]):
        which = amounts.basis_of(query["model"], spec)
        if which is None:
            specs.append(spec)
            kept_labels.append(labels[index] if index < len(labels) else None)
            continue
        basis = basis or which
        if first is not None:
            alias[spec] = first
            continue
        first = spec
        specs.append(spec)
        kept_labels.append(None)  # no fixed name: the field's own name ("Untaxed Total" / "Total") follows the switch
    return specs, kept_labels, alias, basis


def pair_basis(block):
    """The basis the reader saw first in this block, or ``None`` when it shows no money field of a pair."""
    return _collapse_amounts(block["query"])[3]


def _measures(specs, labels, limit):
    out = []
    for index, spec in enumerate(specs[:limit]):
        measure = {"id": "m%d" % (index + 1)}
        if spec == "__count":
            measure["agg"] = "count"
        else:
            field, _sep, agg = spec.partition(":")
            measure.update({"field": field, "agg": agg})
        if index < len(labels) and isinstance(labels[index], str) and labels[index]:
            measure["label"] = labels[index][:60]
        out.append(measure)
    return out


def _order(text, measures, specs, dims, alias):
    """The chat's ``"price_subtotal:sum desc"`` as the dashboard's ``{"by": "m1", "dir": "desc"}``; ``None`` when it does not map."""
    if not isinstance(text, str) or not text.strip():
        return None
    parts = text.split()
    direction = parts[-1].lower() if parts[-1].lower() in ("asc", "desc") else "asc"
    key = alias.get(parts[0], parts[0])
    for measure, spec in zip(measures, specs):
        if key == spec:
            return {"by": measure["id"], "dir": direction}
    for dim in dims:
        if key in (dim["field"], "%s:%s" % (dim["field"], dim.get("granularity"))):
            return {"by": dim["field"], "dir": direction}
    return None


def widget_from_block(block, number, is_date):
    """``(widget dict, notes)`` for one savable block. ``notes`` say what had to be adjusted, in plain words."""
    query, notes = block["query"], []
    model = query["model"]
    dims = [_dimension(g, is_date, model) for g in (query.get("groupby") or []) if isinstance(g, str)]
    wtype = {"kpi": "kpi", "table": "table"}.get(block["type"]) or (block.get("chart") if block.get("chart") in ("bar", "line", "pie") else "bar")
    if wtype == "line" and not (dims and is_date(model, dims[0]["field"])):
        wtype = "bar"
        notes.append("a line needs a date axis, so it became a bar chart")
    if wtype == "pie" and len(dims) != 1:
        wtype = "bar"
        notes.append("a pie needs exactly one grouping, so it became a bar chart")
    _min_d, max_d, _min_m, max_m = SHAPES[wtype]
    if len(dims) > max_d:
        dims = dims[:max_d]
        notes.append("only the first %d grouping(s) are kept" % max_d)
    specs, labels, alias, _basis = _collapse_amounts(query)
    measures = _measures(specs, labels, max_m)
    if len(specs) > len(measures):
        notes.append("only the first %d measure(s) are kept" % len(measures))
    data = {"source": query["model"], "dimensions": dims, "measures": measures}
    if query.get("domain"):
        data["domain"] = [list(leaf) if isinstance(leaf, (list, tuple)) else leaf for leaf in query["domain"]]
    order = _order(query.get("order"), measures, specs, dims, alias)
    if wtype in ("line", "area") and dims and dims[0].get("granularity") in GRANULARITIES:
        data["fill_gaps"] = True  # a day without sales is a zero on the line, not a missing point
        order = {"by": dims[0]["field"], "dir": "asc"}
    if order and dims:
        data["order"] = order
    limit = query.get("limit")
    if isinstance(limit, int) and 1 <= limit <= MAX_LIMIT and dims and not (wtype == "pie" and limit > 8):
        data["limit"] = limit
    widget = {"id": "w%d" % number, "type": wtype, "title": (block.get("title") or "")[:80], "data": data}
    if not data["dimensions"]:
        del data["dimensions"]
    return widget, notes


def spec_from_blocks(blocks, title, is_date, max_widgets=8):
    """``(spec, skipped notes)`` from the savable blocks of one answer."""
    widgets, notes, models, default = [], [], [], None
    for block in blocks:
        if not savable(block):
            continue
        if len(widgets) >= max_widgets:
            notes.append("%s: left out (a dashboard here has at most %d widgets)" % (block.get("title") or "?", max_widgets))
            continue
        widget, adjusted = widget_from_block(block, len(widgets) + 1, is_date)
        widgets.append(widget)
        notes += ["%s: %s" % (widget["title"] or widget["id"], note) for note in adjusted]
        basis = pair_basis(block)
        if basis:  # money on the screen: the dashboard gets the switch between amounts without tax and with tax
            model = block["query"]["model"]
            models += [model] if model not in models else []
            default = default or basis
    spec = {"v": 1, "title": title[:80], "assumptions": ["Saved from a chat answer."], "widgets": widgets}
    if models:
        spec["filters"] = [amounts.switch((models, default))]
    return spec, notes
