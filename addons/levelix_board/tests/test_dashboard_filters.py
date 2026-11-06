"""Dashboard filters, cross-filtering, comparison, calculated measures and pies on the real ORM."""
from odoo.tests import tagged

from ..lib.errors import BoardError
from ..lib.frame import OTHERS_REF
from .support import TZ, BoardCase, widget

COUNT = [{"id": "m1", "agg": "count"}]
CROSS = {"on_click": {"action": "cross_filter"}}
DRILL = {"on_click": {"action": "drill", "model": "sale.order", "columns": ["name", "partner_id", "state"]}}


@tagged("post_install", "-at_install", "levelix_board")
class TestDashboardFilters(BoardCase):
    """Orders: A and B on 10 March (admin), A on 11 March (the seller); one quotation on the 12th that is never counted."""

    def setUp(self):
        super().setUp()
        base = [["state", "=", "sale"], ["partner_id", "in", self.partners.ids]]
        self.spec = {
            "v": 1, "title": "Filters",
            "filters": [
                {"id": "period", "type": "date_range", "label": "Period", "default": "all", "applies_to": {"sale.order": "date_order"}},
                {"id": "seller", "type": "select", "label": "Salesperson", "applies_to": {"sale.order": "user_id"}},
                {"id": "company", "type": "company", "label": "Company", "applies_to": {"sale.order": "company_id"}},
                {"id": "status", "type": "select", "label": "Status", "applies_to": {"sale.order": "state"}},
            ],
            "widgets": [
                widget("total", "kpi", domain=base, measures=COUNT),
                widget("money", "kpi", domain=base, measures=[{"id": "m1", "field": "amount_untaxed", "agg": "sum"}]),
                widget("day", "area", domain=base, measures=COUNT, interact=CROSS, fill_gaps=True, order={"by": "date_order", "dir": "asc"},
                       dimensions=[{"field": "date_order", "granularity": "day"}]),
                widget("cust", "bar", domain=base, measures=COUNT, interact=CROSS, dimensions=[{"field": "partner_id"}]),
                widget("open", "bar", domain=base, measures=COUNT, interact=DRILL, dimensions=[{"field": "partner_id"}]),
                widget("plain", "bar", domain=base, measures=COUNT, dimensions=[{"field": "partner_id"}]),
            ],
        }
        self.board = self.make_board(self.spec)
        self.rpc = self.as_user(self.admin)

    def run_all(self, filter_values=None, cross=None):
        out = self.rpc.lx_run(self.board.id, None, filter_values, False, cross)["widgets"]
        return {wid: res.get("frame") or res for wid, res in out.items()}

    def count(self, frames):
        return frames["total"]["rows"][0][0]

    def by_customer(self, frame):
        return {row[0]: row[1] for row in frame["rows"]}

    # -- dashboard filters ----------------------------------------------------------------------------------

    def test_no_choice_means_the_default_and_the_default_is_everything(self):
        frames = self.run_all()
        self.assertEqual(self.count(frames), 3)
        self.assertEqual([r[0] for r in frames["day"]["rows"]], ["2024-03-10", "2024-03-11"])

    def test_a_period_narrows_every_widget_on_the_model(self):
        frames = self.run_all({"period": {"from": "2024-03-11", "to": "2024-03-11"}})
        self.assertEqual(self.count(frames), 1)
        self.assertEqual(frames["money"]["rows"][0][0], 10)
        self.assertEqual([r[0] for r in frames["day"]["rows"]], ["2024-03-11"])  # gaps are filled inside the chosen period only
        self.assertEqual(self.by_customer(frames["cust"]), {"Levelix drill customer A": 1})
        frames = self.run_all({"period": {"from": "2024-03-10", "to": "2024-03-11"}})
        self.assertEqual(self.count(frames), 3)

    def test_a_choice_of_salesperson(self):
        self.assertEqual(self.count(self.run_all({"seller": [self.salesman.id]})), 1)
        self.assertEqual(self.count(self.run_all({"seller": [self.admin.id]})), 2)
        self.assertEqual(self.count(self.run_all({"seller": [self.admin.id, self.salesman.id]})), 3)
        self.assertEqual(self.count(self.run_all({"seller": []})), 3)  # empty means everyone

    def test_choices_combine(self):
        frames = self.run_all({"seller": [self.admin.id], "period": {"from": "2024-03-10", "to": "2024-03-10"}, "status": ["sale"]})
        self.assertEqual(self.count(frames), 2)
        self.assertEqual(self.count(self.run_all({"seller": [self.salesman.id], "period": {"to": "2024-03-10"}})), 0)

    def test_the_company_choice_is_limited_to_the_readers_companies(self):
        mine = self.admin.company_ids.ids
        self.assertEqual(self.count(self.run_all({"company": mine})), 3)
        other = self.env["res.company"].create({"name": "Levelix other company"})
        with self.assertRaises(BoardError) as caught:
            self.run_all({"company": [other.id]})
        self.assertEqual(caught.exception.code, "NO_ACCESS")

    def test_bad_choices_are_refused(self):
        for bad in ({"nope": 1}, {"period": "someday"}, {"status": ["frozen"]}, {"seller": {"x": 1}}):
            with self.subTest(bad=bad), self.assertRaises(BoardError) as caught:
                self.run_all(bad)
            self.assertIn(caught.exception.code, ("BAD_FILTER",))

    def test_a_widget_of_another_model_is_left_alone(self):
        self.spec["widgets"].append(widget("people", "kpi", source="res.partner", domain=[["id", "in", self.partners.ids]], measures=COUNT))
        board = self.make_board(self.spec)
        out = self.rpc.lx_run(board.id, ["people"], {"seller": [self.salesman.id]})["widgets"]["people"]["frame"]
        self.assertEqual(out["rows"], [[2]])

    def test_the_options_a_reader_may_choose_from(self):
        sellers = self.rpc.lx_filter_options(self.board.id, "seller", "Lx")
        self.assertIn(self.salesman.id, [o["value"] for o in sellers])
        self.assertTrue(all(set(o) == {"value", "label"} for o in sellers))
        states = {o["value"]: o["label"] for o in self.rpc.lx_filter_options(self.board.id, "status")}
        self.assertEqual(states["sale"], "Sales Order")
        self.assertEqual([o["value"] for o in self.rpc.lx_filter_options(self.board.id, "company")], self.admin.company_ids.ids)
        for bad in ("period", "nothing"):
            with self.subTest(bad=bad), self.assertRaises(BoardError) as caught:
                self.rpc.lx_filter_options(self.board.id, bad)
            self.assertEqual(caught.exception.code, "BAD_FILTER")

    def test_the_explanation_names_the_chosen_period(self):
        out = self.rpc.lx_explain(self.board.id, ["total"], {"period": {"from": "2024-03-11", "to": "2024-03-11"}})["total"]["explain"]
        self.assertTrue(any("2024-03-11" in line["text"] for line in out), out)

    # -- cross-filtering ----------------------------------------------------------------------------------

    def ref(self, frame, label):
        return frame["meta"]["group_refs"][[r[0] for r in frame["rows"]].index(label)]

    def test_clicking_a_customer_filters_the_others_but_not_itself(self):
        frames = self.run_all()
        ref = self.ref(frames["cust"], "Levelix drill customer A")
        frames = self.run_all(cross={"widget_id": "cust", "group_ref": ref})
        self.assertEqual(self.count(frames), 2)
        self.assertEqual(self.by_customer(frames["plain"]), {"Levelix drill customer A": 2})
        self.assertEqual(self.by_customer(frames["cust"]), {"Levelix drill customer A": 2, "Levelix drill customer B": 1})  # the clicked one keeps its context

    def test_clicking_a_day_filters_by_that_local_day(self):
        frames = self.run_all()
        ref = self.ref(frames["day"], "2024-03-10")
        frames = self.run_all(cross={"widget_id": "day", "group_ref": ref})
        self.assertEqual(self.count(frames), 2)
        self.assertEqual(self.by_customer(frames["plain"]), {"Levelix drill customer A": 1, "Levelix drill customer B": 1})

    def test_a_cross_filter_adds_to_the_dashboard_filters(self):
        frames = self.run_all({"seller": [self.admin.id]})
        ref = self.ref(frames["cust"], "Levelix drill customer A")
        frames = self.run_all({"seller": [self.admin.id]}, {"widget_id": "cust", "group_ref": ref})
        self.assertEqual(self.count(frames), 1)

    def test_a_cross_filter_that_cannot_be_applied_is_an_error(self):
        frames = self.run_all()
        ref = self.ref(frames["cust"], "Levelix drill customer A")
        cases = {
            "CROSS_NOT_CONFIGURED": {"widget_id": "plain", "group_ref": ref},
            "UNKNOWN_WIDGET": {"widget_id": "nope", "group_ref": ref},
            "CROSS_EMPTY": {"widget_id": "cust", "group_ref": [99999999]},
            "DRILL_OTHERS": {"widget_id": "cust", "group_ref": [OTHERS_REF]},
            "BAD_ARGUMENT": {"widget_id": "cust"},
        }
        for code, cross in cases.items():
            with self.subTest(code=code), self.assertRaises(BoardError) as caught:
                self.run_all(cross=cross)
            self.assertEqual(caught.exception.code, code)

    def test_drilling_shows_the_records_the_chart_counted(self):
        frames = self.run_all({"seller": [self.salesman.id]})
        ref = self.ref(frames["open"], "Levelix drill customer A")
        result = self.rpc.lx_drill(self.board.id, "open", ref, {"seller": [self.salesman.id]})
        self.assertEqual(result["ids"], self.order_3.ids)
        everyone = self.rpc.lx_drill(self.board.id, "open", ref)
        self.assertCountEqual(everyone["ids"], (self.order_1 + self.order_3).ids)
        crossed = self.rpc.lx_drill(self.board.id, "open", ref, None, {"widget_id": "day", "group_ref": self.ref(self.run_all()["day"], "2024-03-10")})
        self.assertEqual(crossed["ids"], self.order_1.ids)


@tagged("post_install", "-at_install", "levelix_board")
class TestComparison(BoardCase):
    def setUp(self):
        super().setUp()
        self.rpc = self.as_user(self.admin)
        self.base = [["state", "=", "sale"], ["partner_id", "in", self.partners.ids]]

    def frame(self, wtype="kpi", compare="previous_period", domain=(), cross=None, **data):
        spec = {"v": 1, "widgets": [widget("w", wtype, domain=self.base + list(domain), measures=COUNT, compare=compare, interact=CROSS, **data)]}
        board = self.make_board(spec)
        res = self.rpc.lx_run(board.id, None, None, False, cross)["widgets"]["w"]
        return res.get("frame") or res

    def test_a_number_is_compared_with_the_stretch_before(self):
        # 11 and 12 March against 9 and 10 March
        frame = self.frame(domain=[["date_order", ">=", "2024-03-11"], ["date_order", "<=", "2024-03-12"]])
        self.assertEqual(frame["rows"], [[1]])
        self.assertEqual(frame["compare_rows"], [[2]])
        self.assertEqual(frame["meta"]["compare"], {"kind": "previous_period", "from": "2024-03-09", "to": "2024-03-10"})
        self.assertEqual(frame["meta"]["warnings"], [])

    def test_a_calendar_month_is_compared_with_the_calendar_month_before(self):
        frame = self.frame(domain=[["date_order", ">=", "2024-03-01"], ["date_order", "<=", "2024-03-31"]])
        self.assertEqual(frame["rows"], [[3]])
        self.assertEqual(frame["meta"]["compare"], {"kind": "previous_period", "from": "2024-02-01", "to": "2024-02-29"})  # a leap year
        self.assertEqual(frame["compare_rows"], [[0]])

    def test_the_same_days_a_year_earlier(self):
        frame = self.frame(compare="previous_year", domain=[["date_order", ">=", "2024-03-01"], ["date_order", "<=", "2024-03-31"]])
        self.assertEqual(frame["meta"]["compare"], {"kind": "previous_year", "from": "2023-03-01", "to": "2023-03-31"})
        self.assertEqual(frame["compare_rows"], [[0]])

    def test_a_series_lines_up_bucket_by_bucket(self):
        frame = self.frame("area", dimensions=[{"field": "date_order", "granularity": "day"}], fill_gaps=True, order={"by": "date_order", "dir": "asc"},
                           domain=[["date_order", ">=", "2024-03-10"], ["date_order", "<=", "2024-03-12"]])
        self.assertEqual([r[0] for r in frame["rows"]], ["2024-03-10", "2024-03-11", "2024-03-12"])
        self.assertEqual([r[1] for r in frame["rows"]], [2, 1, 0])
        self.assertEqual(len(frame["compare_rows"]), 3)  # 7 to 9 March
        self.assertEqual([r[0] for r in frame["compare_rows"]], ["2024-03-07", "2024-03-08", "2024-03-09"])

    def test_the_earlier_stretch_that_has_orders(self):
        # 12 to 12 March against the 11th (one order)
        frame = self.frame(domain=[["date_order", ">=", "2024-03-12"], ["date_order", "<=", "2024-03-12"]])
        self.assertEqual((frame["rows"], frame["compare_rows"]), ([[0]], [[1]]))

    def test_a_dashboard_period_moves_the_comparison_with_it(self):
        spec = {"v": 1, "filters": [{"id": "period", "type": "date_range", "label": "P", "default": "all", "applies_to": {"sale.order": "date_order"}}],
                "widgets": [widget("w", "kpi", domain=self.base + [["date_order", ">=", "2024-01-01"]], measures=COUNT, compare="previous_period")]}
        board = self.make_board(spec)
        frame = self.rpc.lx_run(board.id, None, {"period": {"from": "2024-03-11", "to": "2024-03-12"}})["widgets"]["w"]["frame"]
        self.assertEqual((frame["rows"], frame["compare_rows"]), ([[1]], [[2]]))  # the narrower range wins

    def test_a_cross_filter_turns_the_comparison_off_for_that_widget(self):
        spec = {"v": 1, "widgets": [
            widget("w", "kpi", domain=self.base + [["date_order", ">=", "2024-03-10"]], measures=COUNT, compare="previous_period"),
            widget("pick", "bar", domain=self.base, measures=COUNT, interact=CROSS, dimensions=[{"field": "partner_id"}])]}
        board = self.make_board(spec)
        pick = self.rpc.lx_run(board.id, ["pick"])["widgets"]["pick"]["frame"]
        ref = pick["meta"]["group_refs"][0]
        frame = self.rpc.lx_run(board.id, ["w"], None, False, {"widget_id": "pick", "group_ref": ref})["widgets"]["w"]["frame"]
        self.assertNotIn("compare_rows", frame)
        self.assertEqual(self.rpc.lx_run(board.id, ["w"])["widgets"]["w"]["frame"]["compare_rows"], [[0]])

    def test_no_start_date_means_no_comparison_and_a_warning(self):
        frame = self.frame()
        self.assertNotIn("compare_rows", frame)
        self.assertEqual([w["code"] for w in frame["meta"]["warnings"]], ["COMPARE_NO_PERIOD"])


@tagged("post_install", "-at_install", "levelix_board")
class TestCalculatedMeasuresAndPies(BoardCase):
    def setUp(self):
        super().setUp()
        self.rpc = self.as_user(self.admin)
        self.base = [["state", "=", "sale"], ["partner_id", "in", self.partners.ids]]

    def run_widget(self, spec_widget):
        board = self.make_board({"v": 1, "widgets": [spec_widget]})
        res = self.rpc.lx_run(board.id)["widgets"][spec_widget["id"]]
        return res.get("frame") or res

    def table(self, extra, **data):
        measures = [{"id": "m1", "agg": "count"}, {"id": "m2", "field": "amount_untaxed", "agg": "sum"}] + extra
        return self.run_widget(widget("w", "table", domain=self.base, measures=measures, dimensions=[{"field": "partner_id"}],
                                      order={"by": "m1", "dir": "desc"}, **data))

    def test_a_calculated_measure_is_worked_out_per_row_and_in_the_total(self):
        frame = self.table([{"id": "m3", "calc": "m2 / m1", "label": "Average order"}])
        self.assertEqual([c["label"] for c in frame["columns"]], ["Customer", "Count", "Untaxed Amount", "Average order"])
        self.assertEqual(frame["rows"], [["Levelix drill customer A", 2, 20.0, 10.0], ["Levelix drill customer B", 1, 10.0, 10.0]])
        self.assertEqual(frame["meta"]["totals"], {"m1": 3, "m2": 30.0, "m3": 10.0})  # the formula over the totals, not a sum of rows

    def test_a_calculated_measure_knows_what_it_is(self):
        frame = self.table([{"id": "m3", "calc": "m2 - m2"}, {"id": "m4", "calc": "m2 / m1"}])
        self.assertEqual([c["type"] for c in frame["columns"][3:]], ["monetary", "number"])  # money minus money stays money
        frame = self.table([{"id": "m3", "calc": "m2 / m1", "format": "percent"}])
        self.assertEqual(frame["columns"][3]["type"], "percent")

    def test_dividing_by_nothing_is_no_value_not_an_error(self):
        frame = self.table([{"id": "m3", "calc": "m2 / (m1 - m1)"}])
        self.assertEqual([row[3] for row in frame["rows"]], [None, None])
        self.assertNotIn("m3", frame["meta"]["totals"])

    def test_others_works_for_a_calculated_measure(self):
        frame = self.run_widget(widget("w", "bar", domain=self.base, dimensions=[{"field": "partner_id"}], limit=1, others=True,
                                       order={"by": "m1", "dir": "desc"},
                                       measures=[{"id": "m1", "agg": "count"}, {"id": "m2", "field": "amount_untaxed", "agg": "sum"}, {"id": "m3", "calc": "m2 / m1"}]))
        self.assertEqual(frame["rows"], [["Levelix drill customer A", 2, 20.0, 10.0], ["Others", 1, 10.0, 10.0]])
        self.assertEqual(frame["meta"]["group_refs"][-1], [OTHERS_REF])

    def test_only_a_calculated_measure_is_not_enough(self):
        spec = {"v": 1, "widgets": [widget("w", "kpi", domain=self.base, measures=[{"id": "m1", "calc": "1 + 1"}])]}
        result = self.env["levelix.board.engine"]._validate_spec(spec)
        self.assertEqual([e["code"] for e in result["errors"]], ["BAD_CALC"])  # a formula needs measures to read

    def test_a_pie_with_many_slices_keeps_the_biggest_and_groups_the_rest(self):
        people = self.env["res.partner"].create([{"name": "Levelix pie %02d" % i} for i in range(10)])
        pie = widget("w", "pie", source="res.partner", domain=[["id", "in", people.ids]], dimensions=[{"field": "name"}], measures=COUNT)
        frame = self.run_widget(pie)
        self.assertEqual(len(frame["rows"]), 8)  # 7 slices and "Others"
        self.assertEqual(frame["rows"][-1], ["Others", 3])
        self.assertEqual(sum(row[1] for row in frame["rows"]), 10)  # nothing is lost
        self.assertEqual(frame["meta"]["group_refs"][-1], [OTHERS_REF])

    def test_a_small_pie_is_left_alone(self):
        frame = self.run_widget(widget("w", "pie", domain=self.base, dimensions=[{"field": "partner_id"}], measures=COUNT))
        self.assertEqual(sorted(row[1] for row in frame["rows"]), [1, 2])
        self.assertNotIn("Others", [row[0] for row in frame["rows"]])

    def test_the_new_chart_types_run(self):
        day = [{"field": "date_order", "granularity": "day_of_week"}, {"field": "date_order", "granularity": "hour_number"}]
        two = [{"id": "m1", "agg": "count"}, {"id": "m2", "field": "amount_untaxed", "agg": "sum"}]
        cust = [{"field": "partner_id"}]
        heat = self.run_widget(widget("w", "heatmap", domain=self.base, dimensions=day, measures=COUNT))
        self.assertEqual(sum(row[2] for row in heat["rows"]), 3)
        self.assertEqual({row[1] for row in heat["rows"]}, {15, 16})  # 10:00 and 11:00 UTC are 15:00 and 16:00 in Tashkent
        for wtype, dims, measures, view in (
            ("funnel", cust, COUNT, {}), ("treemap", cust, COUNT, {}), ("waterfall", cust, COUNT, {}),
            ("scatter", cust, two, {}), ("combo", cust, two, {"line": "m2"}), ("gauge", [], COUNT, {"target": 5}),
        ):
            with self.subTest(wtype=wtype):
                frame = self.run_widget(dict(widget("w", wtype, domain=self.base, dimensions=dims, measures=measures), view=view))
                self.assertIn("rows", frame, frame)
                self.assertEqual(len([c for c in frame["columns"] if c["role"] == "measure"]), len(measures))


@tagged("post_install", "-at_install", "levelix_board")
class TestAmountsFilter(BoardCase):
    """One dashboard, amounts without tax or with tax. Orders: 3 of 10 without tax, and one of 100 with 12% tax (customer B)."""

    def setUp(self):
        super().setUp()
        self.tax = self.env["account.tax"].create({"name": "Levelix test 12%", "amount": 12, "amount_type": "percent", "type_tax_use": "sale"})
        order = self.env["sale.order"].create({
            "partner_id": self.partner_b.id, "user_id": self.admin.id, "date_order": "2024-03-11 08:00:00",
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 100, "tax_ids": [(6, 0, self.tax.ids)]})]})
        order.action_confirm()
        order.date_order = "2024-03-11 08:00:00"
        self.taxed_order = order
        base = [["state", "=", "sale"], ["partner_id", "in", self.partners.ids]]
        self.spec = {
            "v": 1,
            "filters": [{"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": "untaxed",
                         "applies_to": {"sale.order": {"untaxed": "amount_untaxed", "taxed": "amount_total"}}}],
            "widgets": [
                widget("money", "kpi", domain=base, measures=[{"id": "m1", "field": "amount_untaxed", "agg": "sum", "label": "Revenue"}]),
                widget("count", "kpi", domain=base, measures=COUNT),
                widget("both", "table", domain=base, dimensions=[{"field": "partner_id"}], order={"by": "m1", "dir": "desc"},
                       measures=[{"id": "m1", "field": "amount_untaxed", "agg": "sum", "label": "Revenue"},
                                 {"id": "m2", "field": "amount_total", "agg": "sum", "label": "Revenue with tax", "fixed": True}]),
                widget("pie", "pie", domain=base, dimensions=[{"field": "partner_id"}], measures=[{"id": "m1", "field": "amount_total", "agg": "sum"}]),
                widget("people", "kpi", source="res.partner", domain=[["id", "in", self.partners.ids]], measures=COUNT),
                widget("cust", "bar", domain=base, dimensions=[{"field": "partner_id"}], measures=[{"id": "m1", "field": "amount_untaxed", "agg": "sum"}],
                       interact={"on_click": {"action": "cross_filter"}}),
            ]}
        self.board = self.make_board(self.spec)
        self.rpc = self.as_user(self.admin)

    def run_all(self, basis=None, cross=None):
        values = {"amounts": basis} if basis is not None else None
        out = self.rpc.lx_run(self.board.id, None, values, False, cross)["widgets"]
        return {wid: res.get("frame") or res for wid, res in out.items()}

    def sums(self, partner=None):
        """``(without tax, with tax)`` of the confirmed test orders, read straight from the orders."""
        orders = self.env["sale.order"].search([("state", "=", "sale"), ("partner_id", "in", (partner or self.partners).ids)])
        return sum(orders.mapped("amount_untaxed")), sum(orders.mapped("amount_total"))

    def test_the_default_is_without_tax_and_the_switch_moves_every_money_widget(self):
        without, with_tax = self.sums()
        self.assertGreater(with_tax, without)  # there is tax in these orders
        untaxed, taxed = self.run_all(), self.run_all("taxed")
        self.assertEqual(untaxed["money"]["rows"], [[without]])
        self.assertEqual(taxed["money"]["rows"], [[with_tax]])
        self.assertEqual(self.run_all("untaxed")["money"]["rows"], [[without]])
        self.assertEqual(untaxed["count"]["rows"], taxed["count"]["rows"])  # a count has no tax
        self.assertEqual(untaxed["people"]["rows"], taxed["people"]["rows"])  # nor has a model the switch does not name

    def test_a_measure_follows_the_switch_whichever_of_the_two_fields_it_was_written_with(self):
        # the pie was written with the taxed field; it still shows what the reader chose
        (a_without, a_taxed), (b_without, b_taxed) = self.sums(self.partner_a), self.sums(self.partner_b)
        self.assertEqual(sorted(r[1] for r in self.run_all()["pie"]["rows"]), sorted([a_without, b_without]))
        self.assertEqual(sorted(r[1] for r in self.run_all("taxed")["pie"]["rows"]), sorted([a_taxed, b_taxed]))

    def test_a_pinned_measure_keeps_its_own_field(self):
        b_without, b_taxed = self.sums(self.partner_b)
        for basis, expected_first in (("untaxed", b_without), ("taxed", b_taxed)):
            with self.subTest(basis=basis):
                row = next(r for r in self.run_all(basis)["both"]["rows"] if r[0] == "Levelix drill customer B")
                self.assertEqual((row[1], row[2]), (expected_first, b_taxed))  # the second column is "always with tax"

    def test_the_explanation_says_which_amounts_it_shows(self):
        lines = lambda basis: [l["text"] for l in self.rpc.lx_explain(self.board.id, ["money"], {"amounts": basis})["money"]["explain"]]  # noqa: E731
        self.assertIn("Amounts: with tax.", lines("taxed"))
        self.assertIn("Amounts: without tax.", lines("untaxed"))
        plain = [l["text"] for l in self.rpc.lx_explain(self.board.id, ["people"], {"amounts": "taxed"})["people"]["explain"]]
        self.assertFalse(any(t.startswith("Amounts:") for t in plain))  # a widget with no money in it says nothing

    def test_a_cross_filter_reads_the_same_amounts_the_chart_shows(self):
        frames = self.run_all("taxed")
        ref = frames["cust"]["meta"]["group_refs"][[r[0] for r in frames["cust"]["rows"]].index("Levelix drill customer B")]
        b_without, b_taxed = self.sums(self.partner_b)
        self.assertEqual(self.run_all("taxed", {"widget_id": "cust", "group_ref": ref})["money"]["rows"], [[b_taxed]])
        self.assertEqual(self.run_all("untaxed", {"widget_id": "cust", "group_ref": ref})["money"]["rows"], [[b_without]])

    def test_a_bad_choice_is_refused(self):
        for bad in ("both", ["taxed"], 5):
            with self.subTest(bad=bad), self.assertRaises(BoardError) as caught:
                self.run_all(bad)
            self.assertEqual(caught.exception.code, "BAD_FILTER")

    def test_a_dashboard_whose_switch_names_a_bad_field_cannot_be_saved(self):
        self.spec["filters"][0]["applies_to"]["sale.order"]["taxed"] = "amount_nothing"
        result = self.env["levelix.board.engine"]._validate_spec(self.spec)
        self.assertEqual([e["code"] for e in result["errors"]], ["UNKNOWN_FIELD"])
