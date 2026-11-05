from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.frame import NOT_SET, OTHERS, FrameBuilder, local_day
from ..lib.planner import Planner
from ..lib.spec import Spec
from . import fixtures
from .fixtures import SALE_REPORT, sample_spec

NOW = datetime(2026, 11, 5, 10, 0, 0)
TZ = "Asia/Tashkent"  # UTC+5


def plan(mutate=None, index=0, tz=TZ):
    raw = sample_spec()
    if mutate:
        mutate(raw["widgets"][index]["data"])
    return Planner(fixtures.catalog()).plan(Spec.from_raw(raw).widgets[index], SALE_REPORT, tz, NOW)


def day(key_local_midnight_utc, label="x"):
    return (key_local_midnight_utc, label)


def build(p, groups, total=None, currency=None):
    return FrameBuilder().build(p, groups, total, currency)


@tagged("levelix_board")
class TestFrame(BaseCase):
    def test_local_day_from_odoo_key(self):
        self.assertEqual(local_day("2026-10-06 19:00:00", "datetime", TZ), "2026-10-07")
        self.assertEqual(local_day("2026-10-06 19:00:00", "datetime", "UTC"), "2026-10-06")
        self.assertEqual(local_day("2026-10-06", "date", TZ), "2026-10-06")
        self.assertEqual(local_day(datetime(2026, 10, 6, 19), "datetime", TZ), "2026-10-07")

    def test_columns_and_rows(self):
        p = plan(lambda d: d.update(fill_gaps=False))
        frame = build(p, [
            {"date:day": day("2026-10-06 19:00:00"), "price_subtotal:sum": 100.0},
            {"date:day": day("2026-10-08 19:00:00"), "price_subtotal:sum": 50.5},
        ], currency={"symbol": "UZS", "position": "after"}).to_dict()
        self.assertEqual(frame["columns"], [
            {"id": "date", "label": "Order Date", "role": "dimension", "type": "datetime", "granularity": "day"},
            {"id": "m1", "label": "Revenue", "role": "measure", "type": "monetary"},
        ])
        self.assertEqual(frame["rows"], [["2026-10-07", 100.0], ["2026-10-09", 50.5]])
        self.assertEqual(frame["meta"]["count"], 2)
        self.assertEqual(frame["meta"]["currency"], {"symbol": "UZS", "position": "after"})
        self.assertFalse(frame["meta"]["truncated"])

    def test_group_refs_identify_groups_for_drill(self):
        p = plan(lambda d: d.update(fill_gaps=False))
        frame = build(p, [{"date:day": day("2026-10-06 19:00:00"), "price_subtotal:sum": 1.0}])
        self.assertEqual(frame.meta["group_refs"], [["2026-10-06 19:00:00"]])
        top = plan(index=1)
        frame = build(top, [{"product_id": (7, "Coffee"), "product_uom_qty:sum": 3.0}])
        self.assertEqual(frame.meta["group_refs"], [[7]])
        self.assertEqual(frame.rows, [["Coffee", 3.0]])

    def test_labels_for_selection_missing_and_boolean(self):
        p = plan(lambda d: d.update(dimensions=[{"field": "state"}], order=None), index=1)
        p2 = plan(lambda d: d.update(dimensions=[{"field": "partner_id"}], others=False, limit=None, order=None), index=1)
        frame = build(p, [{"state": "sale", "product_uom_qty:sum": 1.0}, {"state": False, "product_uom_qty:sum": 2.0}])
        self.assertEqual([r[0] for r in frame.rows], ["Sales Order", NOT_SET])
        self.assertEqual(frame.meta["group_refs"], [["sale"], [None]])
        frame = build(p2, [{"partner_id": False, "product_uom_qty:sum": 2.0}])
        self.assertEqual(frame.rows[0][0], NOT_SET)
        paid = plan(lambda d: d.update(dimensions=[{"field": "is_paid"}], others=False, limit=None, order=None), index=1)
        frame = build(paid, [{"is_paid": True, "product_uom_qty:sum": 1}, {"is_paid": False, "product_uom_qty:sum": 1}])
        self.assertEqual([r[0] for r in frame.rows], ["Yes", "No"])

    def test_date_parts_are_numbers(self):
        p = plan(lambda d: d.update(dimensions=[{"field": "date", "granularity": "day_of_week"}], fill_gaps=False, order=None))
        frame = build(p, [{"date:day_of_week": 3.0, "price_subtotal:sum": 1.0}])
        self.assertEqual(frame.rows, [[3, 1.0]])
        self.assertIsInstance(frame.rows[0][0], int)

    def test_empty_aggregates(self):
        p = plan(lambda d: d.update(measures=[{"id": "m1", "field": "price_unit", "agg": "avg"}, {"id": "m2", "agg": "count"}],
                                    dimensions=[{"field": "product_id"}], others=False, limit=None, order=None), index=1)
        frame = build(p, [{"product_id": (1, "A"), "price_unit:avg": None, "__count": 0}])
        self.assertEqual(frame.rows, [["A", None, 0]])

    def test_too_many_groups_is_cut_and_reported(self):
        p = plan(lambda d: d.update(limit=None, others=False, dimensions=[{"field": "product_id"}], order=None), index=1)
        groups = [{"product_id": (i, "P%d" % i), "product_uom_qty:sum": 1.0} for i in range(p.cap + 1)]
        frame = build(p, groups)
        self.assertEqual(len(frame.rows), p.cap)
        self.assertTrue(frame.meta["truncated"])
        self.assertEqual(frame.meta["warnings"][0]["code"], "TOO_MANY_GROUPS")

    # -- gaps ----------------------------------------------------------------

    def test_gaps_between_existing_days_are_filled(self):
        p = plan()
        frame = build(p, [
            {"date:day": day("2026-10-06 19:00:00"), "price_subtotal:sum": 10.0},  # 7 Oct
            {"date:day": day("2026-10-09 19:00:00"), "price_subtotal:sum": 40.0},  # 10 Oct
        ])
        self.assertEqual(frame.rows, [["2026-10-07", 10.0], ["2026-10-08", 0], ["2026-10-09", 0], ["2026-10-10", 40.0]])
        self.assertEqual(frame.meta["group_refs"][1], ["2026-10-07 19:00:00"])  # the ref of a filled day is its real key

    def test_gaps_use_the_filter_range_at_both_ends(self):
        p = plan(lambda d: d.update(domain=[["state", "=", "sale"], ["date", ">=", "2026-10-07"], ["date", "<=", "2026-10-10"]]))
        frame = build(p, [{"date:day": day("2026-10-07 19:00:00"), "price_subtotal:sum": 5.0}])  # 8 Oct
        self.assertEqual([r[0] for r in frame.rows], ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10"])
        self.assertEqual([r[1] for r in frame.rows], [0, 5.0, 0, 0])

    def test_no_data_with_a_range_is_all_zeros_without_it_is_empty(self):
        ranged = plan(lambda d: d.update(domain=[["date", ">=", "2026-10-07"], ["date", "<=", "2026-10-09"]]))
        self.assertEqual(len(build(ranged, []).rows), 3)
        self.assertEqual(build(plan(), []).rows, [])

    def test_month_gaps(self):
        p = plan(lambda d: d.update(dimensions=[{"field": "date", "granularity": "month"}]))
        frame = build(p, [
            {"date:month": day("2026-08-31 19:00:00"), "price_subtotal:sum": 1.0},  # September
            {"date:month": day("2026-10-31 19:00:00"), "price_subtotal:sum": 3.0},  # November
        ])
        self.assertEqual(frame.rows, [["2026-09-01", 1.0], ["2026-10-01", 0], ["2026-11-01", 3.0]])

    def test_descending_order_is_kept(self):
        p = plan(lambda d: d.update(order={"by": "date", "dir": "desc"}))
        frame = build(p, [
            {"date:day": day("2026-10-08 19:00:00"), "price_subtotal:sum": 4.0},
            {"date:day": day("2026-10-06 19:00:00"), "price_subtotal:sum": 1.0},
        ])
        self.assertEqual([r[0] for r in frame.rows], ["2026-10-09", "2026-10-08", "2026-10-07"])

    def test_series_are_filled_per_value(self):
        p = plan(lambda d: d.update(dimensions=[{"field": "date", "granularity": "day"}, {"field": "state"}]))
        frame = build(p, [
            {"date:day": day("2026-10-06 19:00:00"), "state": "sale", "price_subtotal:sum": 10.0},
            {"date:day": day("2026-10-06 19:00:00"), "state": "draft", "price_subtotal:sum": 2.0},
            {"date:day": day("2026-10-08 19:00:00"), "state": "sale", "price_subtotal:sum": 7.0},
        ])
        self.assertEqual(frame.rows, [
            ["2026-10-07", "Sales Order", 10.0], ["2026-10-07", "Quotation", 2.0],
            ["2026-10-08", "Sales Order", 0], ["2026-10-08", "Quotation", 0],
            ["2026-10-09", "Sales Order", 7.0], ["2026-10-09", "Quotation", 0],
        ])
        self.assertEqual(frame.meta["group_refs"][2], ["2026-10-07 19:00:00", "sale"])

    def test_missing_date_row_stays_last(self):
        p = plan()
        frame = build(p, [
            {"date:day": False, "price_subtotal:sum": 9.0},
            {"date:day": day("2026-10-06 19:00:00"), "price_subtotal:sum": 10.0},
        ])
        self.assertEqual(frame.rows, [["2026-10-07", 10.0], [NOT_SET, 9.0]])

    def test_huge_ranges_are_not_expanded(self):
        p = plan(lambda d: d.update(domain=[["date", ">=", "1900-01-01"], ["date", "<=", "2099-12-31"]]))
        self.assertEqual(build(p, []).rows, [])

    def test_weekly_buckets_follow_the_week_start(self):
        raw = sample_spec()
        raw["widgets"][0]["data"].update(dimensions=[{"field": "date", "granularity": "week"}],
                                         domain=[["date", ">=", "2026-10-26"], ["date", "<=", "2026-11-08"]])
        widget = Spec.from_raw(raw).widgets[0]
        monday = Planner(fixtures.catalog()).plan(widget, SALE_REPORT, "UTC", NOW, week_start=1)
        sunday = Planner(fixtures.catalog()).plan(widget, SALE_REPORT, "UTC", NOW, week_start=7)
        self.assertEqual([r[0] for r in build(monday, []).rows], ["2026-10-26", "2026-11-02"])
        self.assertEqual([r[0] for r in build(sunday, []).rows], ["2026-10-25", "2026-11-01", "2026-11-08"])

    # -- others --------------------------------------------------------------

    def test_others_is_total_minus_top(self):
        p = plan(index=1)
        groups = [{"product_id": (i, "P%d" % i), "product_uom_qty:sum": float(10 - i)} for i in range(3)]
        frame = build(p, groups, total={"product_uom_qty:sum": 100.0})
        self.assertEqual(frame.rows[-1], [OTHERS, 100.0 - 10 - 9 - 8])
        self.assertEqual(len(frame.rows), 4)
        self.assertEqual(frame.meta["group_refs"][-1], ["__others__"])

    def test_no_others_row_when_nothing_is_left(self):
        p = plan(index=1)
        groups = [{"product_id": (1, "A"), "product_uom_qty:sum": 10.0}]
        self.assertEqual(len(build(p, groups, total={"product_uom_qty:sum": 10.0}).rows), 1)
        self.assertEqual(build(p, [], total={}).rows, [])

    def test_others_counts_stay_whole_numbers(self):
        p = plan(lambda d: d.update(measures=[{"id": "m1", "agg": "count"}], order={"by": "m1", "dir": "desc"}), index=1)
        frame = build(p, [{"product_id": (1, "A"), "__count": 4}], total={"__count": 9})
        self.assertEqual(frame.rows[-1], [OTHERS, 5])
        self.assertIsInstance(frame.rows[-1][1], int)

    def test_a_table_gets_grand_totals_of_additive_measures_only(self):
        def table(data):
            data["measures"] = [
                {"id": "m1", "field": "price_subtotal", "agg": "sum"},
                {"id": "m2", "field": "price_unit", "agg": "avg"},
                {"id": "m3", "agg": "count"},
            ]
            data["dimensions"] = [{"field": "partner_id"}]
            data.pop("fill_gaps", None)
            data.pop("order", None)
        raw = sample_spec()
        raw["widgets"][0]["type"] = "table"
        table(raw["widgets"][0]["data"])
        p = Planner(fixtures.catalog()).plan(Spec.from_raw(raw).widgets[0], SALE_REPORT, TZ, NOW)
        self.assertTrue(p.totals)
        frame = build(p, [{"partner_id": (1, "A"), "price_subtotal:sum": 40.0, "price_unit:avg": 2.0, "__count": 2}],
                      total={"price_subtotal:sum": 100.0, "price_unit:avg": 3.0, "__count": 5.0}).to_dict()
        self.assertEqual(frame["meta"]["totals"], {"m1": 100.0, "m3": 5})  # no total of averages
        self.assertEqual(len(frame["rows"]), 1)  # the total is not a row

    def test_other_widgets_have_no_totals(self):
        self.assertFalse(plan().totals)
        self.assertIsNone(build(plan(), []).to_dict()["meta"]["totals"])
