"""The generic tools, as the current user, on real models."""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_engine import TZ, AiCase


@tagged("post_install", "-at_install", "levelix_ai_core", "-standard")
class TestTools(AiCase):
    def setUp(self):
        super().setUp()
        self.tools = self.env["levelix.ai.tools"].with_user(self.boss).with_context(tz=TZ)
        self.message = self.env["levelix.ai.message"]

    def run_tool(self, name, **args):
        return self.tools._run(name, args, self.message)

    # -- finding and describing -------------------------------------------------------------------------

    def test_reporting_models_come_first(self):
        result, _side = self.run_tool("find_models", query="sales")
        models = result["models"]
        self.assertTrue(models[0]["report"], models[:3])
        self.assertEqual(models[0]["model"], "sale.report")
        self.assertIn("sale.order", [m["model"] for m in models])

    def test_technical_models_are_never_listed_or_described(self):
        for query in ("config parameter", "ir model access", "api keys", "conversation"):
            result, _side = self.run_tool("find_models", query=query)
            self.assertFalse([m for m in result["models"] if m["model"].startswith(("ir.", "levelix.ai.", "res.users.apikeys"))], query)
        for name in ("ir.config_parameter", "res.users.apikeys", "levelix.ai.message", "res.config.settings", "nope.nope", None, 5):
            with self.subTest(model=name), self.assertRaises(UserError):
                self.run_tool("describe_model", model=name)

    def test_a_model_the_user_may_not_read_is_not_offered(self):
        tools = self.env["levelix.ai.tools"].with_user(self.plain)
        result, _side = tools._run("find_models", {"query": "sales order"}, self.message)
        self.assertNotIn("sale.order", [m["model"] for m in result["models"]])

    def test_describe_lists_stored_fields_and_what_can_be_summed(self):
        result, _side = self.run_tool("describe_model", model="sale.report")
        self.assertTrue(result["report"])
        by_name = {f["name"]: f for f in result["fields"]}
        self.assertTrue(by_name["price_subtotal"]["summable"])
        self.assertFalse(by_name["price_unit"]["summable"])  # Odoo marks a price as averaged, never added up
        self.assertEqual(by_name["state"]["type"], "selection")
        self.assertIn(["sale", "Sales Order"], by_name["state"]["values"])
        self.assertEqual(by_name["partner_id"]["relation"], "res.partner")
        stored = self.env["sale.report"].fields_get(attributes=["store"])
        self.assertTrue(all(stored[name]["store"] for name in by_name))  # computed-only fields are left out

    # -- counting and grouping -------------------------------------------------------------------------------

    def test_a_count_matches_the_orm(self):
        self.order("2024-03-10 10:00:00")
        self.order("2024-03-12 10:00:00")
        domain = '[["partner_id","=",%d],["state","=","sale"]]' % self.customer.id
        result, side = self.run_tool("aggregate", model="sale.order", domain=domain, aggregates=["__count"], show="kpi")
        self.assertEqual(result["groups"], [[2]])
        self.assertEqual(side["block"]["items"][0]["value"], 2)

    def test_a_day_without_a_time_is_the_whole_local_day(self):
        self.order("2024-03-10 21:30:00")  # 11 March 02:30 in Tashkent
        base = '[["partner_id","=",%d],["state","=","sale"],["date_order",">=","2024-03-11"],["date_order","<=","2024-03-11"]]' % self.customer.id
        result, _side = self.run_tool("aggregate", model="sale.order", domain=base, aggregates=["__count"])
        self.assertEqual(result["groups"], [[1]])
        before = base.replace("2024-03-11", "2024-03-10")
        result, _side = self.run_tool("aggregate", model="sale.order", domain=before, aggregates=["__count"])
        self.assertEqual(result["groups"], [[0]])

    def test_relative_dates_follow_the_users_today(self):
        result, _side = self.run_tool("aggregate", model="sale.order", domain='[["date_order",">=","today =1d"]]', aggregates=["__count"])
        self.assertEqual(len(result["groups"]), 1)

    def test_grouping_labels_and_ordering(self):
        other = self.env["res.partner"].create({"name": "AI test other"})
        self.order(qty=1, price=10)
        self.order(partner=other, qty=1, price=500)
        domain = '[["partner_id","in",[%d,%d]],["state","=","sale"]]' % (self.customer.id, other.id)
        result, side = self.run_tool("aggregate", model="sale.order", domain=domain, groupby=["partner_id"],
                                     aggregates=["amount_untaxed:sum"], order="amount_untaxed:sum desc", show="chart", title="Totals")
        self.assertEqual([g[0] for g in result["groups"]], ["AI test other", "AI test customer"])
        self.assertEqual(result["column_labels"], ["Customer", "Untaxed Amount"])
        self.assertEqual(side["block"]["labels"], ["AI test other", "AI test customer"])
        self.assertEqual(side["block"]["datasets"][0]["data"], [500.0, 10.0])
        self.assertEqual(side["block"]["unit"]["symbol"], self.env.company.currency_id.symbol)

    def test_selection_groups_show_labels_and_empty_ones_say_not_set(self):
        self.order(confirm=False)
        domain = '[["partner_id","=",%d]]' % self.customer.id
        result, _side = self.run_tool("aggregate", model="sale.order", domain=domain, groupby=["state"], aggregates=["__count"])
        self.assertEqual(result["groups"], [["Quotation", 1]])

    def test_nonsense_requests_become_readable_errors(self):
        for args, needle in (
            ({"aggregates": ["price_unit:sum"], "model": "sale.report"}, "cannot be added up"),
            ({"aggregates": ["nope:sum"], "model": "sale.order"}, "no stored field"),
            ({"aggregates": ["amount_total:median"], "model": "sale.order"}, "one of"),
            ({"aggregates": ["__count"], "groupby": ["nope"], "model": "sale.order"}, "Cannot group"),
            ({"aggregates": ["__count"], "groupby": ["partner_id:day"], "model": "sale.order"}, "cannot be grouped by"),
            ({"aggregates": ["__count"], "domain": '[["date_order",">=","today -x"]]', "model": "sale.order"}, "date"),
            ({"aggregates": ["__count"], "domain": "not json", "model": "sale.order"}, "Not valid JSON"),
        ):
            with self.subTest(args=args), self.assertRaises(UserError) as ctx:
                self.run_tool("aggregate", **dict({"domain": "[]"}, **args))
            self.assertIn(needle, str(ctx.exception))

    def test_a_money_total_over_several_currencies_is_flagged(self):
        company = self.env.company
        foreign = self.env["res.currency"].with_context(active_test=False).search([("name", "in", ("EUR", "CHF", "GBP")), ("id", "!=", company.currency_id.id)], limit=1)
        foreign.active = True
        self.env["res.currency.rate"].create({"currency_id": foreign.id, "company_id": company.id, "name": "2024-03-01", "rate": 0.5})
        pricelist = self.env["product.pricelist"].create({"name": "AI test foreign", "currency_id": foreign.id, "company_id": company.id})
        self.order()
        foreign_order = self.env["sale.order"].create({
            "partner_id": self.customer.id, "pricelist_id": pricelist.id, "date_order": "2024-03-10 10:00:00",
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1, "price_unit": 10})]})
        foreign_order.action_confirm()
        domain = '[["partner_id","=",%d],["state","=","sale"]]' % self.customer.id
        result, side = self.run_tool("aggregate", model="sale.order", domain=domain, aggregates=["amount_total:sum"], show="kpi")
        self.assertTrue(result["warnings"])
        self.assertFalse(side["block"]["unit"])  # no unit is better than a wrong one
        reported, _side = self.run_tool("aggregate", model="sale.report", domain='[["partner_id","=",%d]]' % self.customer.id,
                                        aggregates=["price_subtotal:sum"])
        self.assertEqual(reported["warnings"], [])  # reporting models convert to the company currency already

    # -- reading records -------------------------------------------------------------------------------------------

    def test_search_returns_rows_and_a_table_for_the_screen(self):
        order = self.order()
        result, side = self.run_tool("search_records", model="sale.order", domain='[["partner_id","=",%d]]' % self.customer.id,
                                     fields=["name", "amount_total", "partner_id", "state", "nope"], show="table")
        self.assertEqual(result["columns"], ["name", "amount_total", "partner_id", "state"])
        self.assertEqual(result["rows"][0][0], order.id)
        self.assertEqual(result["rows"][0][3:], ["AI test customer", "Sales Order"])
        self.assertEqual(side["block"]["ids"], [order.id])
        self.assertEqual(side["block"]["columns"][2]["label"], "Customer")

    def test_search_is_limited(self):
        result, _side = self.run_tool("search_records", model="res.partner", domain="[]", limit=100000)
        self.assertLessEqual(result["returned"], 50)

    # -- the registry -------------------------------------------------------------------------------------------------------

    def test_only_offered_tools_can_run(self):
        for name in ("_tool_find_models", "find_models; drop", "", None, "run", "to_ai"):
            with self.subTest(name=name), self.assertRaises(UserError):
                self.tools._run(name, {}, self.message)
        with self.assertRaises(UserError):
            self.tools._run("find_models", "not a dict", self.message)

    def test_every_tool_is_declared_for_the_model(self):
        for tool in self.tools._tool_defs():
            self.assertEqual(set(tool), {"name", "description", "parameters"}, tool["name"])
            self.assertTrue(callable(getattr(self.tools, "_tool_%s" % tool["name"], None)), tool["name"])
            self.assertEqual(tool["parameters"]["type"], "object")

    def test_pick_and_ask_talk_to_the_user_not_the_model(self):
        result, side = self.run_tool("pick_record", model="res.partner", query="AI test")
        self.assertEqual(result["status"], "waiting_for_the_user")
        self.assertNotIn("AI test", str(result))
        self.assertEqual(side["block"]["type"], "choices")
        none, _side = self.run_tool("pick_record", model="res.partner", query="zzzz-no-such-record")
        self.assertEqual(none["found"], 0)
        _result, side = self.run_tool("ask_user", question="Which period?", options=["This month", "Last month", 5])
        self.assertEqual([o["label"] for o in side["block"]["options"]], ["This month", "Last month", "5"])
        with self.assertRaises(UserError):
            self.run_tool("ask_user", question="?", options=["only one"])

    def test_suggestions_follow_the_screen(self):
        here = self.tools._suggestions({"model": "sale.order"})
        self.assertTrue(any("sale" in s.lower() or "Sales" in s for s in here), here)
        generic = self.tools._suggestions({})
        self.assertTrue(generic)
        self.assertEqual(self.env["levelix.ai.tools"].with_user(self.plain)._suggestions({"model": "sale.order"})[0:0], [])
