"""What the system looks up before the model starts: the hint and the fields, so the model does not spend round trips on them."""
import json

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from odoo.addons.levelix_ai_core.tests.support import AiCase

from ..lib import drill_defaults, prepared


@tagged("levelix_ai_board")
class TestPreparedText(BaseCase):
    HINT = {"model": "sale.report", "advice": "Confirmed orders: state = sale."}
    DESCRIBED = {"fields": [
        {"name": "state", "type": "selection", "label": "Status", "values": [["draft", "Quotation"], ["sale", "Sales Order"]]},
        {"name": "partner_id", "type": "many2one", "label": "Customer", "relation": "res.partner"},
        {"name": "price_subtotal", "type": "monetary", "label": "Untaxed Total", "summable": True},
    ]}

    def test_the_block_holds_the_hint_and_the_fields_compactly(self):
        text = prepared.block(self.HINT, self.DESCRIBED)
        self.assertTrue(text.startswith("[prepared:sale.report]"))
        self.assertIn("do not call get_hints or describe_model", text)
        self.assertIn("Hint: Confirmed orders: state = sale.", text)
        self.assertIn('- state: selection "Status" [draft, sale]', text)
        self.assertIn('- partner_id: many2one "Customer" -> res.partner', text)
        self.assertIn('- price_subtotal: monetary "Untaxed Total" (sum)', text)
        self.assertLess(len(text), 600)

    def test_a_bare_drill_is_completed_for_known_reporting_models(self):
        widget = {"id": "w1", "type": "bar", "data": {"source": "sale.report"}, "interact": {"on_click": {"action": "drill"}}}
        done = drill_defaults.expand_widget(widget)
        click = done["interact"]["on_click"]
        self.assertEqual((click["model"], click["map"]["date"], click["columns"][0]), ("sale.order", "date_order", "name"))
        self.assertEqual(widget["interact"]["on_click"], {"action": "drill"})  # the input is not changed
        invoices = drill_defaults.expand_widget(dict(widget, data={"source": "account.invoice.report"}))
        self.assertEqual(invoices["interact"]["on_click"]["model"], "account.move")

    def test_what_the_model_spelled_out_is_kept(self):
        mine = {"action": "drill", "model": "sale.order", "columns": ["name"], "map": {"date": "commitment_date"}}
        widget = {"id": "w1", "type": "bar", "data": {"source": "sale.report"}, "interact": {"on_click": dict(mine)}}
        self.assertEqual(drill_defaults.expand_widget(widget)["interact"]["on_click"], mine)
        partly = drill_defaults.expand_widget(dict(widget, interact={"on_click": {"action": "drill", "columns": ["name", "state"]}}))
        self.assertEqual(partly["interact"]["on_click"]["columns"], ["name", "state"])  # only the missing parts are filled
        self.assertEqual(partly["interact"]["on_click"]["model"], "sale.order")

    def test_the_model_is_told_when_a_dashboard_is_the_answer_and_when_it_is_not(self):
        from ..lib.guide import DASHBOARD_RULES
        self.assertIn("Do NOT build a dashboard for it", DASHBOARD_RULES)  # a plain question is answered in the chat
        self.assertIn("call build_dashboard even if the user did not say the word", DASHBOARD_RULES)
        self.assertIn('Never answer that a chart type or a weekday / hour breakdown "is not available"', DASHBOARD_RULES)
        self.assertIn('"today -29d"', DASHBOARD_RULES)
        self.assertIn('"granularity":"day_of_week"', DASHBOARD_RULES)

    def test_the_guide_names_every_widget_type_and_view_option_the_server_knows(self):
        """A type the server accepts but the guide never mentions is a type the model will say does not exist (it did)."""
        from odoo.addons.levelix_board.lib.spec import SHAPES
        from odoo.addons.levelix_board.lib.validator import VIEW_KEYS
        from ..lib.guide import DASHBOARD_RULES
        self.assertNotIn("not available yet", DASHBOARD_RULES)
        for widget_type in SHAPES:
            self.assertIn(widget_type, DASHBOARD_RULES, widget_type)
        for keys in VIEW_KEYS.values():
            for key in keys:
                self.assertIn('"%s"' % key, DASHBOARD_RULES, key)

    def test_nothing_else_is_touched(self):
        for odd in ({"id": "w1", "data": {"source": "res.partner"}, "interact": {"on_click": {"action": "drill"}}},  # no defaults for this model
                    {"id": "w1", "data": {"source": "sale.report"}, "interact": {"on_click": {"action": "cross_filter"}}},
                    {"id": "w1", "data": {"source": "sale.report"}}, "text", None, {"data": "x"}):
            with self.subTest(odd=odd):
                self.assertEqual(drill_defaults.expand_widget(odd), odd)
        spec = {"v": 1, "widgets": "nope"}
        self.assertEqual(drill_defaults.expand_spec(spec), spec)
        self.assertEqual(drill_defaults.expand_spec("text"), "text")


@tagged("post_install", "-at_install", "levelix_ai_board", "-standard")
class TestPreparedInTheChat(AiCase):
    def sent(self, conversation, index=0):
        """The text the vendor got for the n-th question of a conversation."""
        messages = self.env["levelix.ai.conversation"].browse(conversation).message_ids.filtered(lambda m: m.role == "user").sorted("id")
        return json.dumps(messages[index].llm_content)

    def test_a_question_about_sales_arrives_with_the_hint_and_the_fields(self):
        conversation, answer = self.ask(self.boss, "Show me the sales this month")
        text = self.sent(conversation)
        self.assertIn("[prepared:sale.report]", text)
        self.assertIn("price_subtotal: monetary", text)  # a field the model needs
        self.assertIn("Confirmed orders", text)  # the hint's advice
        self.assertEqual(answer.state, "done")

    def test_the_second_question_of_the_chat_does_not_repeat_it(self):
        conversation, _first = self.ask(self.boss, "Show me the sales this month")
        _c, _second = self.ask(self.boss, "and last month's sales?", conversation)
        self.assertIn("[prepared:", self.sent(conversation, 0))
        self.assertNotIn("[prepared:", self.sent(conversation, 1))

    def test_a_question_with_no_hint_is_left_alone(self):
        conversation, _answer = self.ask(self.boss, "What is the weather in Tashkent?")
        self.assertNotIn("[prepared:", self.sent(conversation))

    def test_a_user_who_may_not_read_sales_gets_no_hint(self):
        conversation, _answer = self.ask(self.plain, "Show me the sales this month")
        self.assertNotIn("[prepared:", self.sent(conversation))

    def test_the_vendor_sees_it_but_the_screen_shows_only_what_was_typed(self):
        conversation, _answer = self.ask(self.boss, "Show me the sales this month")
        message = self.env["levelix.ai.conversation"].browse(conversation).message_ids.filtered(lambda m: m.role == "user")
        self.assertEqual(message.text, "Show me the sales this month")
