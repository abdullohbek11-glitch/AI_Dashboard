"""Integration tests on the real ORM: numbers, rights, companies, currencies."""
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

TZ = "Asia/Tashkent"  # UTC+5
RATE = 0.0001  # test currency units per company currency unit


def widget(wid, wtype, **data):
    return {"id": wid, "type": wtype, "data": dict({"source": "sale.report"}, **data)}


def spec(*widgets):
    return {"v": 1, "widgets": list(widgets)}


@tagged("post_install", "-at_install", "levelix_board")
class TestEngine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        company = env.company
        cls.foreign = env["res.currency"].with_context(active_test=False).search(
            [("name", "in", ("EUR", "CHF", "GBP")), ("id", "!=", company.currency_id.id)], limit=1)
        cls.foreign.active = True
        env["res.currency.rate"].create({"currency_id": cls.foreign.id, "company_id": company.id, "name": "2024-03-01", "rate": RATE})
        cls.partner = env["res.partner"].create({"name": "Levelix test customer"})
        cls.product_a = env["product.product"].create({"name": "Levelix test A", "list_price": 100, "type": "consu"})
        cls.product_b = env["product.product"].create({"name": "Levelix test B", "list_price": 10, "type": "consu"})
        # the order currency follows the pricelist, so each currency needs one
        cls.pricelists = {
            cur.id: env["product.pricelist"].create({"name": "Levelix test %s" % cur.name, "currency_id": cur.id, "company_id": company.id})
            for cur in (company.currency_id, cls.foreign)
        }

        cls.order_a = cls._order(cls.product_a, 1, 100, "2024-03-10 10:00:00", company.currency_id)  # 100 local
        cls.order_b = cls._order(cls.product_b, 3, 10, "2024-03-10 21:30:00", cls.foreign)  # 30 foreign; 11 March in Tashkent
        cls.order_e = cls._order(cls.product_a, 2, 50, "2024-03-12 08:00:00", company.currency_id)  # 100 local
        cls.order_draft = cls._order(cls.product_a, 1, 999, "2024-03-15 10:00:00", company.currency_id, confirm=False)
        cls.expected_total = 100 + 100 + 30 / cls.order_b.currency_rate

        cls.base_domain = [["partner_id", "=", cls.partner.id], ["state", "=", "sale"],
                           ["date", ">=", "2024-03-01"], ["date", "<", "2024-04-01"]]
        cls.admin_engine = env["levelix.board.engine"].with_context(tz=TZ)

    @classmethod
    def _order(cls, product, qty, price, when, currency, confirm=True):
        order = cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "pricelist_id": cls.pricelists[currency.id].id,
            "date_order": when,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": qty, "price_unit": price})],
        })
        if confirm:
            order.action_confirm()
            order.date_order = when
        return order

    def run_one(self, wtype, engine=None, explain=False, **data):
        engine = self.admin_engine if engine is None else engine  # an empty recordset is falsy
        data.setdefault("domain", self.base_domain)
        out = engine._run_spec(spec(widget("w1", wtype, **data)), explain=explain)["widgets"]["w1"]
        self.assertNotIn("error", out, out.get("error"))
        return out

    # -- numbers ---------------------------------------------------------------

    def test_total_matches_the_orders_in_company_currency(self):
        out = self.run_one("kpi", measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"},
                                            {"id": "m2", "field": "name", "agg": "count_distinct", "label": "Orders"}])
        total, orders = out["frame"]["rows"][0]
        self.assertAlmostEqual(total, self.expected_total, places=2)
        self.assertEqual(orders, 3)  # the draft order is not counted
        self.assertEqual(out["frame"]["meta"]["currency"]["symbol"], self.env.company.currency_id.symbol)

    def test_daily_series_uses_the_viewers_time_zone(self):
        out = self.run_one("area", dimensions=[{"field": "date", "granularity": "day"}],
                           measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])
        rows = dict((r[0], r[1]) for r in out["frame"]["rows"])
        self.assertEqual(sorted(rows), ["2024-03-10", "2024-03-11", "2024-03-12"])
        self.assertAlmostEqual(rows["2024-03-10"], 100)
        self.assertAlmostEqual(rows["2024-03-11"], 30 / self.order_b.currency_rate, places=2)  # 21:30 UTC is already the 11th in Tashkent
        utc = self.run_one("area", engine=self.env["levelix.board.engine"].with_context(tz="UTC"),
                           dimensions=[{"field": "date", "granularity": "day"}],
                           measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])
        self.assertEqual([r[0] for r in utc["frame"]["rows"]], ["2024-03-10", "2024-03-12"])

    def test_gaps_are_filled_over_the_filter_range(self):
        out = self.run_one("area", dimensions=[{"field": "date", "granularity": "day"}], fill_gaps=True,
                           measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])
        rows = out["frame"]["rows"]
        self.assertEqual(len(rows), 31)  # all of March
        self.assertEqual(rows[0], ["2024-03-01", 0])
        self.assertAlmostEqual(sum(r[1] for r in rows), self.expected_total, places=2)
        self.assertEqual(len(out["frame"]["meta"]["group_refs"]), 31)

    def test_weekly_and_monthly_buckets_line_up_with_odoo(self):
        for gran in ("week", "month"):
            plain = self.run_one("bar", dimensions=[{"field": "date", "granularity": gran}],
                                 measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])
            filled = self.run_one("bar", dimensions=[{"field": "date", "granularity": gran}], fill_gaps=True,
                                  measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])
            days = [r[0] for r in filled["frame"]["rows"]]
            self.assertEqual(len(days), len(set(days)), "%s buckets must be unique" % gran)
            existing = {r[0]: r[1] for r in plain["frame"]["rows"]}
            for day, value in existing.items():
                self.assertIn(day, days, "%s bucket %s missing after filling" % (gran, day))
                self.assertAlmostEqual(dict((r[0], r[1]) for r in filled["frame"]["rows"])[day], value, places=2)

    def test_top_n_with_others_adds_up(self):
        out = self.run_one("bar", dimensions=[{"field": "product_id"}], limit=1, others=True,
                           measures=[{"id": "m1", "field": "product_uom_qty", "agg": "sum"}],
                           order={"by": "m1", "dir": "desc"})
        rows = out["frame"]["rows"]
        self.assertEqual([r[0] for r in rows], ["Levelix test A", "Others"])
        self.assertAlmostEqual(sum(r[1] for r in rows), 1 + 2 + 3)
        self.assertEqual(rows[1][1], 3)

    def test_group_refs_find_the_group_again(self):
        out = self.run_one("bar", dimensions=[{"field": "product_id"}],
                           measures=[{"id": "m1", "agg": "count"}], order={"by": "m1", "dir": "desc"})
        ids = {self.product_a.id, self.product_b.id}
        self.assertEqual({ref[0] for ref in out["frame"]["meta"]["group_refs"]}, ids)

    # -- rights ------------------------------------------------------------------

    def test_a_user_without_sales_rights_gets_a_widget_error_and_other_widgets_still_run(self):
        user = self.env["res.users"].create({
            "name": "No sales", "login": "levelix_no_sales",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])]})
        engine = self.env["levelix.board.engine"].with_user(user)
        result = engine._run_spec(spec(
            widget("w1", "kpi", measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}]),
            widget("w2", "kpi", source="res.partner", measures=[{"id": "m1", "agg": "count"}]),
        ))["widgets"]
        self.assertEqual(result["w1"]["error"]["code"], "NO_ACCESS")
        self.assertEqual(result["w1"]["error"]["path"], "widgets[0].data.source")
        self.assertGreaterEqual(result["w2"]["frame"]["rows"][0][0], 1)
        verdict = engine._validate_spec(spec(widget("w1", "kpi", measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])))
        self.assertFalse(verdict["ok"])

    def test_record_rules_apply_company_by_company(self):
        other = self.env["res.company"].create({"name": "Levelix other company"})
        user = self.env["res.users"].create({
            "name": "Other company seller", "login": "levelix_other_company",
            "company_id": other.id, "company_ids": [(6, 0, [other.id])],
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("sales_team.group_sale_salesman").id])]})
        engine = self.env["levelix.board.engine"].with_user(user).with_context(allowed_company_ids=[other.id])
        out = self.run_one("kpi", engine=engine, measures=[{"id": "m1", "agg": "count"}])
        self.assertEqual(out["frame"]["rows"][0][0], 0)  # the three orders belong to the first company

    def test_the_database_timeout_is_restored(self):
        self.env.cr.execute("SELECT current_setting('statement_timeout')")
        before = self.env.cr.fetchone()[0]
        self.run_one("kpi", measures=[{"id": "m1", "agg": "count"}])
        self.env.cr.execute("SELECT current_setting('statement_timeout')")
        self.assertEqual(self.env.cr.fetchone()[0], before)

    # -- currencies ----------------------------------------------------------------

    def test_mixed_currencies_on_a_normal_model_are_flagged(self):
        out = self.run_one("kpi", source="sale.order", measures=[{"id": "m1", "field": "amount_untaxed", "agg": "sum"}],
                           domain=[["partner_id", "=", self.partner.id], ["state", "=", "sale"]])
        meta = out["frame"]["meta"]
        self.assertEqual(meta["currency"], {"mixed": True})
        self.assertIn("MIXED_CURRENCY", [w["code"] for w in meta["warnings"]])

    def test_a_single_currency_is_shown_without_a_warning(self):
        out = self.run_one("kpi", source="sale.order", measures=[{"id": "m1", "field": "amount_untaxed", "agg": "sum"}],
                           domain=[["partner_id", "=", self.partner.id], ["state", "=", "sale"], ["currency_id", "=", self.foreign.id]])
        meta = out["frame"]["meta"]
        self.assertEqual(meta["currency"]["symbol"], self.foreign.symbol)
        self.assertEqual(meta["warnings"], [])
        self.assertAlmostEqual(out["frame"]["rows"][0][0], 30)

    # -- errors and explanation ----------------------------------------------------

    def test_a_bad_widget_reports_a_located_error(self):
        result = self.admin_engine._run_spec(spec(
            widget("w1", "bar", dimensions=[{"field": "product_id"}], measures=[{"id": "m1", "field": "price_unit", "agg": "sum"}]),
        ))["widgets"]["w1"]
        self.assertEqual(result["error"]["code"], "NOT_AGGREGATABLE")
        self.assertEqual(result["error"]["path"], "widgets[0].data.measures[0]")

    def test_validate_spec_never_raises(self):
        self.assertFalse(self.admin_engine._validate_spec({"v": 1, "widgets": "x"})["ok"])
        self.assertFalse(self.admin_engine._validate_spec("nonsense")["ok"])
        self.assertTrue(self.admin_engine._validate_spec(spec(widget("w1", "kpi", domain=[["state", "=", "sale"]], measures=[{"id": "m1", "agg": "count"}])))["ok"])

    def test_explanation_describes_what_ran(self):
        out = self.run_one("area", explain=True, dimensions=[{"field": "date", "granularity": "day"}],
                           measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}])
        text = " ".join(line["text"] for line in out["explain"])
        self.assertIn("Sales Analysis", text)
        self.assertIn("Revenue (total)", text)
        self.assertIn("Order Date: 2024-03-01 – 2024-03-31", text)
        self.assertIn("Levelix test customer", text)  # the partner id was turned into a name
        self.assertNotIn("sale.report", text)

    def test_relative_dates_resolve_against_today(self):
        self._order(self.product_b, 1, 10, fields.Datetime.now(), self.env.company.currency_id)
        engine = self.env["levelix.board.engine"].with_context(tz="UTC")
        out = engine._run_spec(spec(widget("w1", "kpi", measures=[{"id": "m1", "field": "name", "agg": "count_distinct"}],
                                           domain=[["state", "=", "sale"], ["partner_id", "=", self.partner.id],
                                                   ["date", ">=", "today"], ["date", "<=", "today"]])))["widgets"]["w1"]
        self.assertEqual(out["frame"]["rows"][0][0], 1)  # only the order made just now, not the 2024 ones

    def test_a_table_carries_the_grand_total_even_when_cut(self):
        out = self.run_one("table", dimensions=[{"field": "date", "granularity": "day"}], limit=1, order={"by": "m1", "dir": "desc"},
                           measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}, {"id": "m2", "agg": "count"}])
        frame = out["frame"]
        self.assertEqual(len(frame["rows"]), 1)
        self.assertAlmostEqual(frame["meta"]["totals"]["m1"], self.expected_total, places=2)
        self.assertEqual(frame["meta"]["totals"]["m2"], 3)
