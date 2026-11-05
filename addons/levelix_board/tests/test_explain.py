from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.errors import BoardWarning
from ..lib.explain import MAX_IMPORTANT, ExplainBuilder
from ..lib.planner import Planner
from ..lib.spec import Spec
from . import fixtures
from .fixtures import SALE_REPORT, sample_spec

NOW = datetime(2026, 11, 5, 10, 0, 0)


def explain(mutate=None, index=0, currency=None, warnings=(), resolve=None):
    raw = sample_spec()
    if mutate:
        mutate(raw["widgets"][index]["data"])
    widget = Spec.from_raw(raw).widgets[index]
    plan = Planner(fixtures.catalog()).plan(widget, SALE_REPORT, "Asia/Tashkent", NOW)
    return ExplainBuilder(resolve).build(widget, SALE_REPORT, plan, currency, warnings)


def texts(lines, detail=None):
    return [l["text"] for l in lines if detail is None or l["detail"] is detail]


@tagged("levelix_board")
class TestExplain(BaseCase):
    def test_time_series_in_plain_words(self):
        lines = explain(lambda d: d.update(domain=[["state", "=", "sale"], ["date", ">=", "today =1d"], ["date", "<=", "today"]]),
                        currency={"symbol": "UZS", "position": "after"})
        self.assertEqual(texts(lines), [
            "Data source: Sales Analysis Report.",
            "Measured: Revenue (total), in UZS.",
            "Grouped by: Order Date (by day).",
            "Status is Sales Order.",
            "Order Date: 2026-11-01 – 2026-11-05.",
        ])

    def test_only_choices_are_important(self):
        lines = explain(lambda d: d.update(domain=[["state", "=", "sale"], ["date", ">=", "today =1d"], ["date", "<=", "today"]]),
                        currency={"symbol": "UZS", "position": "after"})
        self.assertEqual(texts(lines, detail=False), [
            "Measured: Revenue (total), in UZS.", "Status is Sales Order.", "Order Date: 2026-11-01 – 2026-11-05."])
        self.assertEqual(texts(lines, detail=True), ["Data source: Sales Analysis Report.", "Grouped by: Order Date (by day)."])

    def test_cut_off_and_others(self):
        lines = explain(index=1)
        self.assertIn("Only the first 10 by Quantity; the rest is grouped as 'Others'.", texts(lines))
        lines = explain(lambda d: d.update(others=False), index=1)
        self.assertIn("Only the first 10 by Quantity.", texts(lines))

    def test_no_technical_names(self):
        joined = " ".join(texts(explain(index=1)))
        for technical in ("sale.report", "product_id", "price_subtotal", "state ", "__count"):
            self.assertNotIn(technical, joined)

    def test_selection_values_use_labels(self):
        lines = explain(lambda d: d.update(domain=[["state", "in", ["sale", "cancel"]]]))
        self.assertIn("Status is one of Sales Order, Cancelled.", texts(lines))

    def test_record_names_are_resolved_when_possible(self):
        lines = explain(lambda d: d.update(domain=[["state", "=", "sale"], ["partner_id", "in", [5, 6]]]),
                        resolve=lambda model, ids: ["Anor market", "Bahor savdo"])
        self.assertIn("Customer is one of Anor market, Bahor savdo.", texts(lines))

    def test_warnings_are_always_shown(self):
        warning = BoardWarning("STATE_FILTER_MISSING", "p", "Every status is counted.")
        lines = explain(lambda d: d.update(domain=[]), warnings=[warning])
        self.assertEqual(lines[-1], {"kind": "warning", "text": "Every status is counted.", "detail": False})

    def test_at_most_five_important_lines(self):
        many = [["state", "=", "sale"]] + [["partner_id", "=", i] for i in range(1, 9)]
        lines = explain(lambda d: d.update(domain=many))
        self.assertLessEqual(len([l for l in lines if not l["detail"]]), MAX_IMPORTANT)

    def test_mixed_currency(self):
        lines = explain(currency={"mixed": True})
        self.assertIn("Measured: Revenue (total), in several currencies.", texts(lines))
