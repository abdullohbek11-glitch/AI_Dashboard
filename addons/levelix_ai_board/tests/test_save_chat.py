"""Keeping a chat answer as a dashboard: the offer, what the widget is made of, rights, and pressing the button twice."""
import json

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.levelix_ai_core.tests.fake_ai import call, say
from odoo.addons.levelix_ai_core.tests.support import TZ, AiCase

from ..lib import amounts, from_chat

DATES = {"date": True, "date_order": True, "create_date": True}
is_date = lambda model, field: field in DATES  # noqa: E731
LAST_30 = [["state", "=", "sale"], ["date", ">=", "today -30d"], ["date", "<=", "today"]]


def block(kind="chart", chart="bar", **query):
    base = {"model": "sale.report", "domain": LAST_30, "groupby": ["partner_id"], "aggregates": ["price_subtotal:sum"], "labels": ["Revenue"], "order": None, "limit": None}
    out = {"type": kind, "title": "Revenue", "query": dict(base, **query)}
    if kind == "chart":
        out["chart"] = chart
    return out


@tagged("levelix_ai_board")
class TestWidgetFromQuery(BaseCase):
    def widget(self, *args, **kw):
        return from_chat.widget_from_block(block(*args, **kw), 1, is_date)

    def test_only_blocks_with_a_query_can_be_kept(self):
        self.assertTrue(from_chat.savable(block()))
        self.assertFalse(from_chat.savable({"type": "table", "title": "Records", "rows": []}))  # a list of records, not a calculation
        self.assertFalse(from_chat.savable({"type": "choices", "query": {"model": "x", "aggregates": ["__count"]}}))
        self.assertFalse(from_chat.savable(block(aggregates=[])))
        self.assertFalse(from_chat.savable("text"))

    def test_the_dates_stay_relative_so_the_dashboard_stays_current(self):
        widget, _notes = self.widget()
        self.assertEqual(widget["data"]["domain"], LAST_30)
        self.assertEqual(widget["data"]["source"], "sale.report")
        self.assertEqual(widget["title"], "Revenue")

    def test_a_chart_a_number_and_a_table(self):
        bar, _ = self.widget("chart", "bar")
        self.assertEqual((bar["type"], bar["data"]["dimensions"]), ("bar", [{"field": "partner_id"}]))
        kpi, _ = self.widget("kpi", groupby=[], aggregates=["__count"], labels=["Orders"])
        self.assertEqual((kpi["type"], kpi["data"]["measures"]), ("kpi", [{"id": "m1", "agg": "count", "label": "Orders"}]))
        self.assertNotIn("dimensions", kpi["data"])
        table, _ = self.widget("table", aggregates=["price_subtotal:sum", "name:count_distinct"], labels=["Revenue", "Orders"])
        self.assertEqual((table["type"], [m["field"] for m in table["data"]["measures"]]), ("table", ["price_subtotal", "name"]))

    def test_a_line_over_time_fills_the_gaps_and_a_line_over_names_becomes_bars(self):
        line, notes = self.widget("chart", "line", groupby=["date:day"], order="price_subtotal:sum desc")
        self.assertEqual(line["type"], "line")
        self.assertEqual(line["data"]["dimensions"], [{"field": "date", "granularity": "day"}])
        self.assertTrue(line["data"]["fill_gaps"])
        self.assertEqual(line["data"]["order"], {"by": "date", "dir": "asc"})  # time runs left to right
        self.assertEqual(notes, [])
        bars, notes = self.widget("chart", "line", groupby=["partner_id"])
        self.assertEqual(bars["type"], "bar")
        self.assertIn("date axis", notes[0])
        month, _ = self.widget("chart", "bar", groupby=["date"])
        self.assertEqual(month["data"]["dimensions"], [{"field": "date", "granularity": "month"}])  # what the chat used

    def test_a_pie_has_one_measure_and_one_grouping(self):
        pie, notes = self.widget("chart", "pie", aggregates=["price_subtotal:sum", "price_total:sum"], labels=["Without tax", "With tax"])
        self.assertEqual((pie["type"], len(pie["data"]["measures"])), ("pie", 1))
        self.assertEqual(notes, [])  # the second money field is covered by the dashboard's Amounts switch, nothing was lost
        self.assertEqual(pie["data"]["measures"][0], {"id": "m1", "field": "price_subtotal", "agg": "sum"})  # no fixed name: it follows the switch
        flat, notes = self.widget("chart", "pie", groupby=["partner_id", "user_id"])
        self.assertEqual(flat["type"], "bar")
        self.assertTrue(any("one grouping" in n for n in notes))
        big, _ = self.widget("chart", "pie", limit=12)
        self.assertNotIn("limit", big["data"])  # a pie shows its biggest slices by itself
        small, _ = self.widget("chart", "pie", limit=5)
        self.assertEqual(small["data"]["limit"], 5)

    def test_money_in_an_answer_becomes_the_amounts_switch(self):
        both = block(aggregates=["price_subtotal:sum", "price_total:sum", "name:count_distinct"], labels=["Without tax", "With tax", "Orders"], order="price_total:sum desc")
        spec, notes = from_chat.spec_from_blocks([both], "Sales", is_date)
        self.assertEqual(spec["filters"], [{"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": "untaxed",
                                            "applies_to": {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_total"}}}])
        data = spec["widgets"][0]["data"]
        self.assertEqual([(m.get("field"), m.get("agg"), m.get("label")) for m in data["measures"]], [("price_subtotal", "sum", None), ("name", "count_distinct", "Orders")])
        self.assertEqual(data["order"], {"by": "m1", "dir": "desc"})  # the sort on the dropped field sorts the kept one
        self.assertEqual(notes, [])
        # what the reader looked at decides where the switch starts
        taxed, _ = from_chat.spec_from_blocks([block(aggregates=["price_total:sum"], labels=["Total"])], "Sales", is_date)
        self.assertEqual(taxed["filters"][0]["default"], "taxed")
        # no money, no switch; and a model with no pair gets none
        plain, _ = from_chat.spec_from_blocks([block("kpi", groupby=[], aggregates=["__count"], labels=["Orders"])], "Sales", is_date)
        self.assertNotIn("filters", plain)
        other, _ = from_chat.spec_from_blocks([block(model="res.partner", aggregates=["credit:sum"])], "Partners", is_date)
        self.assertNotIn("filters", other)

    def test_one_switch_covers_every_model_in_the_answer(self):
        spec, _ = from_chat.spec_from_blocks([block(), block(model="account.invoice.report", aggregates=["price_total:sum"], title="Invoiced")], "Mix", is_date)
        self.assertEqual(sorted(spec["filters"][0]["applies_to"]), ["account.invoice.report", "sale.report"])
        self.assertEqual(spec["filters"][0]["default"], "untaxed")  # the first money the reader saw

    def test_the_pairs_agree_with_what_the_hints_tell_the_model(self):
        import os
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "hints.xml")) as handle:
            text = handle.read()
        for model in ("sale.report", "account.invoice.report", "purchase.report", "report.pos.order"):
            untaxed, taxed = amounts.PAIRS[model]
            self.assertIn('"%s":{"untaxed":"%s","taxed":"%s"}' % (model, untaxed, taxed), text, model)

    def test_the_sort_and_the_cut_come_along(self):
        widget, _ = self.widget("table", limit=10, order="price_subtotal:sum desc")
        self.assertEqual((widget["data"]["order"], widget["data"]["limit"]), ({"by": "m1", "dir": "desc"}, 10))
        by_name, _ = self.widget("table", order="partner_id asc")
        self.assertEqual(by_name["data"]["order"], {"by": "partner_id", "dir": "asc"})
        none, _ = self.widget("table", order="m1 desc")  # an order that maps to nothing is dropped, not guessed
        self.assertNotIn("order", none["data"])

    def test_a_spec_has_at_most_so_many_widgets_and_says_what_was_left_out(self):
        blocks = [block(), {"type": "table", "title": "Records"}, block(), block()]
        spec, notes = from_chat.spec_from_blocks(blocks, "Mine", is_date, max_widgets=2)
        self.assertEqual([w["id"] for w in spec["widgets"]], ["w1", "w2"])
        self.assertTrue(any("left out" in n for n in notes))
        self.assertEqual((spec["title"], spec["v"]), ("Mine", 1))


@tagged("post_install", "-at_install", "levelix_ai_board", "-standard")
class TestSavingAnAnswer(AiCase):
    def chart_answer(self, user=None, **args):
        arguments = dict(model="sale.report", domain=json.dumps(LAST_30), groupby=["partner_id"], aggregates=["price_subtotal:sum", "price_total:sum"],
                         labels=["Without tax", "With tax"], show="chart", chart_type="pie", title="Top customers", limit=5)
        arguments.update(args)
        self.ai.server.script = lambda request: (call("aggregate", **arguments) if not any(b["type"] == "tool_result" for _r, bl in request["messages"] for b in bl)
                                                  else say(request, "Here it is."))
        return self.ask(user or self.boss, "Sales of the last 30 days as a pie chart")[1]

    def save(self, answer, user=None, **kw):
        return self.env["levelix.board"].with_user(user or self.boss).with_context(tz=TZ).lx_save_chat_answer(answer.id, **kw)

    def test_a_calculated_answer_carries_an_offer_to_keep_it(self):
        self.order()
        answer = self.chart_answer()
        offer = answer.blocks[-1]
        self.assertEqual((offer["type"], offer["count"], offer["board_id"], offer["message_id"]), ("save_offer", 1, None, answer.id))
        self.assertEqual([b["type"] for b in answer.blocks], ["chart", "save_offer"])

    def test_a_list_of_records_and_a_plain_text_answer_carry_no_offer(self):
        self.ai.server.script = None  # the pretend assistant's own scenarios
        _c, records = self.ask(self.boss, "Show orders of customer Levelix")
        self.assertNotIn("save_offer", [b["type"] for b in records.blocks or []])
        _c, text = self.ask(self.boss, "hello")
        self.assertNotIn("save_offer", [b["type"] for b in text.blocks or []])

    def test_a_dashboard_answer_has_its_own_buttons_and_no_offer(self):
        self.ai.server.script = None
        _c, answer = self.ask(self.boss, "Build a dashboard of sales this month by day and the top 10 products")
        self.assertIn("board_draft", [b["type"] for b in answer.blocks])
        self.assertNotIn("save_offer", [b["type"] for b in answer.blocks])

    def test_keeping_it_makes_a_dashboard_that_runs_with_todays_data(self):
        self.order()
        answer = self.chart_answer()
        saved = self.save(answer)
        board = self.env["levelix.board"].browse(saved["board_id"])
        self.assertEqual((board.state, board.user_id, board.name, saved["widgets"]), ("active", self.boss, "Top customers", 1))
        self.assertEqual(board.source_conversation_id, answer.conversation_id)
        widget = board.spec["widgets"][0]
        self.assertEqual((widget["type"], widget["data"]["domain"], widget["data"]["limit"]), ("pie", LAST_30, 5))
        self.assertEqual(len(widget["data"]["measures"]), 1)
        self.assertEqual(saved["notes"], [])
        switch = board.spec["filters"][0]
        self.assertEqual((switch["type"], switch["default"], switch["applies_to"]), ("amount_basis", "untaxed", {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_total"}}))
        engine = self.env["levelix.board.engine"].with_user(self.boss).with_context(tz=TZ)
        for basis in ("untaxed", "taxed"):  # the saved pie runs both ways
            self.assertIn("frame", engine._run_spec(board.spec, None, False, {"amounts": basis})["widgets"]["w1"])
        ran = self.env["levelix.board.engine"].with_user(self.boss).with_context(tz=TZ)._run_spec(board.spec)["widgets"]["w1"]
        self.assertIn("frame", ran, ran)
        self.assertEqual(board.version_ids.origin, "ai")

    def test_pressing_twice_opens_the_same_dashboard(self):
        self.order()
        answer = self.chart_answer()
        first, second = self.save(answer), self.save(answer)
        self.assertEqual(first["board_id"], second["board_id"])
        self.assertEqual(self.env["levelix.board"].sudo().search_count([("source_conversation_id", "=", answer.conversation_id.id)]), 1)
        self.assertEqual(answer.blocks[-1]["board_id"], first["board_id"])  # the chat shows "Saved" when opened again

    def test_a_name_can_be_chosen(self):
        self.order()
        self.assertEqual(self.save(self.chart_answer(), name="Monthly pie")["name"], "Monthly pie")

    def test_an_answer_belongs_to_its_asker(self):
        self.order()
        answer = self.chart_answer()
        for user in (self.plain, self.nobody):
            with self.subTest(user=user.login), self.assertRaises(UserError):
                self.save(answer, user=user)
        for bad in (None, True, "1", 0, 99999999):
            with self.subTest(bad=bad), self.assertRaises(UserError):
                self.env["levelix.board"].with_user(self.boss).lx_save_chat_answer(bad)
        with self.assertRaises(UserError):
            self.save(answer, name="x" * 200)

    def test_only_what_the_server_stored_is_kept(self):
        """The browser names an answer; it cannot hand in a query of its own."""
        self.order()
        answer = self.chart_answer()
        answer.sudo().blocks = [dict(answer.blocks[0], query=dict(answer.blocks[0]["query"], model="res.users")), answer.blocks[-1]]
        with self.assertRaises(UserError):  # res.users is not a reporting model the boss may group by partner_id: nothing valid is left
            self.save(answer)

    def test_a_widget_that_cannot_be_kept_is_left_out_and_said_so(self):
        self.order()
        answer = self.chart_answer()
        good = answer.blocks[0]
        bad = dict(good, title="Broken", query=dict(good["query"], groupby=["no_such_field"]))
        answer.sudo().blocks = [good, bad, dict(answer.blocks[-1], count=2)]
        saved = self.save(answer)
        self.assertEqual(saved["widgets"], 1)
        self.assertTrue(any(n.startswith("Broken: left out") for n in saved["notes"]), saved["notes"])
