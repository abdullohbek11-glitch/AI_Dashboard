"""Which two money fields a model has: without tax and with tax.

A dashboard reads one of them per widget and lets the reader switch (the ``amount_basis`` filter of ``levelix_board``).
This is what keeping a chat answer needs to build that switch; the hints (``data/hints.xml``) tell the model the same pairs.
"""

PAIRS = {
    "sale.report": ("price_subtotal", "price_total"),
    "sale.order": ("amount_untaxed", "amount_total"),
    "account.invoice.report": ("price_subtotal", "price_total"),
    "account.move": ("amount_untaxed", "amount_total"),
    "purchase.report": ("untaxed_total", "price_total"),
    "purchase.order": ("amount_untaxed", "amount_total"),
    "report.pos.order": ("price_subtotal_excl", "price_total"),
}


def basis_of(model: str, spec: str):
    """``"untaxed"`` / ``"taxed"`` when ``spec`` (``"field:sum"``) is one of the model's two money fields, else ``None``."""
    pair = PAIRS.get(model)
    if not pair:
        return None
    return {"%s:sum" % pair[0]: "untaxed", "%s:sum" % pair[1]: "taxed"}.get(spec)


def switch(models_and_default):
    """The ``filters`` entry for ``{model: ...}`` pairs and the basis the reader saw first."""
    models, default = models_and_default
    return {"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": default,
            "applies_to": {m: {"untaxed": PAIRS[m][0], "taxed": PAIRS[m][1]} for m in models}}
