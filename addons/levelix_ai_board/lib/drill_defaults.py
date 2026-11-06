"""Clicking a chart opens the records behind it. For the reporting models of the hints the how is always the same, so the model
may write ``"interact": {"on_click": {"action": "drill"}}`` and the server completes it: fewer tokens to write, and no more
round trips lost to a forgotten field in the map (the commonest mistake). Pure; no Odoo."""

DEFAULTS = {
    "sale.report": {
        "model": "sale.order",
        "map": {"date": "date_order", "product_id": "order_line.product_id", "product_tmpl_id": "order_line.product_template_id"},
        "columns": ["name", "partner_id", "date_order", "amount_total", "state"],
    },
    "account.invoice.report": {
        "model": "account.move",
        "map": {"invoice_date": "invoice_date", "partner_id": "partner_id", "invoice_user_id": "invoice_user_id"},
        "columns": ["name", "partner_id", "invoice_date", "amount_total", "state"],
    },
}


def expand_widget(widget):
    """The widget with its drill completed (a copy); anything that is not a bare drill is returned as it is."""
    if not isinstance(widget, dict):
        return widget
    interact = widget.get("interact")
    click = interact.get("on_click") if isinstance(interact, dict) else None
    data = widget.get("data")
    if not isinstance(click, dict) or click.get("action") != "drill" or not isinstance(data, dict):
        return widget
    defaults = DEFAULTS.get(data.get("source"))
    if defaults is None:
        return widget
    filled = dict(click)
    for key in ("model", "map", "columns"):
        if key not in filled:
            filled[key] = list(defaults[key]) if key == "columns" else (dict(defaults[key]) if key == "map" else defaults[key])
    return dict(widget, interact=dict(interact, on_click=filled))


def expand_spec(spec):
    """The spec with every bare drill completed (a copy)."""
    if not isinstance(spec, dict) or not isinstance(spec.get("widgets"), list):
        return spec
    return dict(spec, widgets=[expand_widget(w) for w in spec["widgets"]])
