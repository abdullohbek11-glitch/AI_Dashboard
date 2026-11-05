from datetime import date, datetime

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.planner import DEFAULT_GROUP_CAP, Planner
from ..lib.spec import Spec
from . import fixtures
from .fixtures import SALE_REPORT, sample_spec

NOW = datetime(2026, 11, 5, 10, 0, 0)
TZ = "Asia/Tashkent"


def plan_for(widget_index=0, tz=TZ, mutate=None, week_start=1):
    raw = sample_spec()
    if mutate:
        mutate(raw["widgets"][widget_index]["data"])
    widget = Spec.from_raw(raw).widgets[widget_index]
    return Planner(fixtures.catalog()).plan(widget, SALE_REPORT, tz, NOW, week_start)


@tagged("levelix_board")
class TestPlanner(BaseCase):
    def test_time_series(self):
        plan = plan_for(0)
        self.assertEqual(plan.model, "sale.report")
        self.assertEqual(plan.groupby, ["date:day"])
        self.assertEqual(plan.aggregates, ["price_subtotal:sum"])
        self.assertEqual(plan.order, "date:day asc")
        self.assertEqual(plan.query_limit, DEFAULT_GROUP_CAP + 1)  # one extra row detects truncation
        self.assertEqual(plan.dims[0].label, "Order Date")
        self.assertEqual(plan.measures[0].label, "Revenue")
        self.assertEqual(plan.measures[0].type, "monetary")
        self.assertEqual(plan.fill.granularity, "day")

    def test_top_n(self):
        plan = plan_for(1)
        self.assertEqual(plan.groupby, ["product_id"])
        self.assertEqual(plan.order, "product_uom_qty:sum desc")
        self.assertEqual(plan.query_limit, 10)
        self.assertTrue(plan.others)
        self.assertEqual(plan.top_n, 10)
        self.assertTrue(plan.measures[0].additive)

    def test_temporal_axis_defaults_to_month(self):
        plan = plan_for(0, mutate=lambda d: d.update(dimensions=[{"field": "date"}], fill_gaps=False))
        self.assertEqual(plan.groupby, ["date:month"])

    def test_dates_are_resolved_in_the_viewers_zone(self):
        plan = plan_for(0, mutate=lambda d: d.update(domain=[["state", "=", "sale"], ["date", ">=", "today -29d"], ["date", "<=", "today"]]))
        self.assertEqual(plan.domain, [["state", "=", "sale"], ["date", ">=", "2026-10-06 19:00:00"], ["date", "<", "2026-11-05 19:00:00"]])
        self.assertEqual((plan.fill.start, plan.fill.end_excl), (date(2026, 10, 7), date(2026, 11, 6)))

    def test_fill_without_bounds_is_open(self):
        plan = plan_for(0)
        self.assertEqual((plan.fill.start, plan.fill.end_excl), (None, None))

    def test_fill_direction_follows_order(self):
        plan = plan_for(0, mutate=lambda d: d.update(order={"by": "date", "dir": "desc"}))
        self.assertEqual(plan.order, "date:day desc")
        self.assertEqual(plan.fill.direction, "desc")

    def test_default_order(self):
        no_order = lambda d: d.pop("order")  # noqa: E731
        self.assertEqual(plan_for(0, mutate=no_order).order, "date:day asc")
        self.assertEqual(plan_for(1, mutate=lambda d: (d.pop("order"), d.pop("limit"), d.pop("others"))).order, "product_uom_qty:sum desc")
        kpi = plan_for(0, mutate=lambda d: (d.pop("order"), d.update(dimensions=[], fill_gaps=False)))
        self.assertIsNone(kpi.order)
        self.assertIsNone(kpi.fill)

    def test_order_by_dimension_name(self):
        plan = plan_for(1, mutate=lambda d: d.update(order={"by": "product_id", "dir": "asc"}))
        self.assertEqual(plan.order, "product_id asc")

    def test_measure_keys(self):
        def mutate(d):
            d["measures"] = [
                {"id": "m1", "field": "price_subtotal", "agg": "sum"},
                {"id": "m2", "field": "price_subtotal", "agg": "sum", "label": "Again"},  # same query, two columns
                {"id": "m3", "field": "name", "agg": "count_distinct", "label": "Orders"},
                {"id": "m4", "agg": "count"},
                {"id": "m5", "field": "price_unit"},
            ]
        plan = plan_for(1, mutate=mutate)
        self.assertEqual(plan.aggregates, ["price_subtotal:sum", "name:count_distinct", "__count", "price_unit:avg"])
        self.assertEqual([m.key for m in plan.measures], ["price_subtotal:sum", "price_subtotal:sum", "name:count_distinct", "__count", "price_unit:avg"])
        self.assertEqual([m.type for m in plan.measures], ["monetary", "monetary", "number", "number", "number"])
        self.assertEqual(plan.measures[3].label, "Count")
        self.assertEqual(plan.measures[4].label, "Unit Price")
        self.assertFalse(plan.measures[4].additive)

    def test_measure_format_overrides_type(self):
        plan = plan_for(1, mutate=lambda d: d.update(measures=[{"id": "m1", "field": "product_uom_qty", "agg": "sum", "format": "currency"}]))
        self.assertEqual(plan.measures[0].type, "monetary")

    def test_having_uses_aggregate_keys(self):
        plan = plan_for(1, mutate=lambda d: d.update(having=[["m1", ">", 100]], others=False))
        self.assertEqual(plan.having, [("product_uom_qty:sum", ">", 100)])

    def test_linked_axis(self):
        plan = plan_for(1, mutate=lambda d: d.update(dimensions=[{"field": "partner_id.country_id"}]))
        self.assertEqual(plan.groupby, ["partner_id.country_id"])
        self.assertEqual(plan.dims[0].label, "Country")
        self.assertEqual(plan.dims[0].type, "many2one")

    def test_selection_labels_travel_with_the_plan(self):
        plan = plan_for(1, mutate=lambda d: d.update(dimensions=[{"field": "state"}]))
        self.assertEqual(plan.dims[0].selection["sale"], "Sales Order")
