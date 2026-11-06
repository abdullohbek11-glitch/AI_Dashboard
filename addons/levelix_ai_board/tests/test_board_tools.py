"""The three board tools on real data: hints, preview, build (with its draft)."""
import json

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.levelix_ai_core.tests.fake_ai import sales_dashboard
from odoo.addons.levelix_ai_core.tests.support import TZ, AiCase


class BoardToolsCase(AiCase):
    def setUp(self):
        super().setUp()
        self.today_order = self.order(when=fields.Datetime.now())  # something to show "this month"
        self.tools = self.env["levelix.ai.tools"].with_user(self.boss).with_context(tz=TZ)
        self.conversation = self.env["levelix.ai.conversation"].with_user(self.boss).create({"name": "tools"})
        self.message = self.env["levelix.ai.message"].sudo().create({"conversation_id": self.conversation.id, "role": "assistant"})

    def run_tool(self, name, **args):
        return self.tools._run(name, args, self.message)

    def widget(self, **data):
        return {"id": "w1", "type": "kpi", "data": dict({"source": "sale.report", "domain": [["state", "=", "sale"]],
                                                         "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"}]}, **data)}


@tagged("post_install", "-at_install", "levelix_ai_board", "-standard")
class TestHintsTool(BoardToolsCase):
    def test_a_question_finds_its_reporting_model(self):
        result, _side = self.run_tool("get_hints", query="sales by day this month")
        self.assertEqual(result["hints"][0]["model"], "sale.report")
        advice = result["hints"][0]["advice"]
        self.assertIn('["state","=","sale"]', advice)
        self.assertIn("no \"done\" state", advice)
        self.assertEqual(result["note"], "")

    def test_other_languages_work(self):
        for query in ("shu oy sotuvni ko'rsat", "продажи по дням", "revenue"):
            result, _side = self.run_tool("get_hints", query=query)
            self.assertEqual([h["model"] for h in result["hints"]][:1], ["sale.report"], query)

    def test_no_match_says_so(self):
        result, _side = self.run_tool("get_hints", query="the weather in Tashkent")
        self.assertEqual(result["hints"], [])
        self.assertIn("find_models", result["note"])

    def test_a_hint_for_a_model_that_is_not_here_or_not_readable_is_not_given(self):
        self.env["levelix.ai.hint"].create({"name": "Ghost", "keywords": "ghostly", "model": "no.such.model", "advice": "x"})
        result, _side = self.run_tool("get_hints", query="ghostly sales")
        self.assertEqual([h["model"] for h in result["hints"]], ["sale.report"])
        plain = self.env["levelix.ai.tools"].with_user(self.plain)  # may chat, may not read sales
        result, _side = plain._run("get_hints", {"query": "sales"}, self.message)
        self.assertEqual(result["hints"], [])

    def test_every_shipped_hint_names_real_fields(self):
        """A hint is advice about real data: the fields it names must exist on its model (checked where the app is installed)."""
        wanted = {
            "sale.report": ["state", "date", "price_subtotal", "price_total", "product_uom_qty", "qty_delivered", "qty_invoiced", "name",
                            "product_id", "product_tmpl_id", "categ_id", "partner_id", "user_id", "team_id", "country_id"],
            "account.invoice.report": ["state", "move_type", "payment_state", "invoice_date", "invoice_date_due", "price_subtotal", "price_total",
                                       "quantity", "move_id", "partner_id", "invoice_user_id", "product_id", "product_categ_id", "team_id"],
        }
        for model, names in wanted.items():
            if model in self.env:
                missing = [n for n in names if n not in self.env[model]._fields]
                self.assertEqual(missing, [], model)
        sale_states = [k for k, _ in self.env["sale.report"]._fields["state"].selection]
        self.assertEqual(sale_states, ["draft", "sent", "sale", "cancel"])


@tagged("post_install", "-at_install", "levelix_ai_board", "-standard")
class TestPreviewTool(BoardToolsCase):
    def test_a_good_widget_shows_its_shape_and_a_sample(self):
        result, _side = self.run_tool("preview_widget", widget=json.dumps(sales_dashboard("")["widgets"][1]))
        self.assertTrue(result["ok"])
        self.assertRegex(result["shape"], r"^\d+ rows?, 2 columns \(Product Variant, Quantity\)$")
        self.assertLessEqual(len(result["sample"]), 10)
        self.assertEqual(result["columns"], ["Product Variant", "Quantity"])

    def test_a_wrong_widget_gives_errors_to_fix(self):
        result, _side = self.run_tool("preview_widget", widget=json.dumps(self.widget(measures=[{"id": "m1", "field": "price_subtotl", "agg": "sum"}])))
        self.assertFalse(result["ok"])
        self.assertEqual((result["errors"][0]["code"], result["errors"][0]["path"]), ("UNKNOWN_FIELD", "widgets[0].data.measures[0]"))
        self.assertIn("Did you mean 'price_subtotal'", result["errors"][0]["message"])

    def test_the_new_chart_types_preview(self):
        two = [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}, {"id": "m2", "field": "name", "agg": "count_distinct", "label": "Orders"}]
        cases = {
            "heatmap": dict(dimensions=[{"field": "date", "granularity": "day_of_week"}, {"field": "date", "granularity": "hour_number"}], measures=two[1:]),
            "pie": dict(dimensions=[{"field": "partner_id"}], measures=two[:1]),
            "scatter": dict(dimensions=[{"field": "partner_id"}], measures=two),
            "combo": dict(dimensions=[{"field": "partner_id"}], measures=two),
            "funnel": dict(dimensions=[{"field": "partner_id"}], measures=two[1:]),
        }
        for wtype, data in cases.items():
            with self.subTest(wtype=wtype):
                result, _side = self.run_tool("preview_widget", widget=json.dumps(dict(self.widget(**data), type=wtype)))
                self.assertTrue(result["ok"], result)

    def test_a_comparison_the_model_got_wrong_says_how_to_fix_it(self):
        day = [{"field": "date", "granularity": "day"}]
        wrong = dict(self.widget(dimensions=day, compare="previous_period", domain=[["state", "=", "sale"], ["date", ">=", "today =1d"]]), type="line")
        result, _side = self.run_tool("preview_widget", widget=json.dumps(wrong))
        self.assertFalse(result["ok"])
        self.assertIn("fill_gaps", result["errors"][0]["message"])
        wrong["data"]["fill_gaps"] = True
        wrong["data"]["order"] = {"by": "date", "dir": "asc"}
        result, _side = self.run_tool("preview_widget", widget=json.dumps(wrong))
        self.assertTrue(result["ok"], result)

    def test_a_misspelt_view_option_is_an_error_not_silence(self):
        result, _side = self.run_tool("preview_widget", widget=json.dumps(dict(self.widget(dimensions=[{"field": "partner_id"}]), type="bar", view={"horizontal": True})))
        self.assertFalse(result["ok"])
        self.assertIn("orientation", result["errors"][0]["message"])

    def test_warnings_are_passed_on(self):
        result, _side = self.run_tool("preview_widget", widget=json.dumps(self.widget(domain=[])))
        self.assertTrue(result["ok"])
        self.assertTrue(any("status" in w.lower() or "state" in w.lower() for w in result["warnings"]), result["warnings"])

    def test_bad_input_is_a_readable_error(self):
        for bad in ("{not json", "[]", "5", None, "x" * 70000):
            with self.subTest(bad=str(bad)[:20]), self.assertRaises(UserError):
                self.run_tool("preview_widget", widget=bad)
        result, _side = self.run_tool("preview_widget", widget=json.dumps({"id": "Bad Id", "type": "kpi", "data": {}}))
        self.assertFalse(result["ok"])

    def test_the_schema_mode_hides_the_sample_from_the_model(self):
        result, _side = self.run_tool("preview_widget", widget=json.dumps(sales_dashboard("")["widgets"][1]))
        self.assertIn("sample", result)
        self.use("anthropic", privacy="schema")
        shaped = self.tools._to_ai("preview_widget", result)
        self.assertNotIn("sample", shaped)
        self.assertEqual(shaped["shape"], result["shape"])
        self.use("anthropic", privacy="aggregates")
        self.assertIn("sample", self.tools._to_ai("preview_widget", result))

    def test_the_user_without_sales_rights_gets_no_access(self):
        tools = self.env["levelix.ai.tools"].with_user(self.plain)
        result, _side = tools._run("preview_widget", {"widget": json.dumps(self.widget())}, self.message)
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], "NO_ACCESS")


@tagged("post_install", "-at_install", "levelix_ai_board", "-standard")
class TestBuildTool(BoardToolsCase):
    def build(self, spec=None, user=None):
        tools = (self.env["levelix.ai.tools"].with_user(user) if user else self.tools).with_context(tz=TZ)
        return tools._run("build_dashboard", {"spec": json.dumps(spec or sales_dashboard(""))}, self.message)

    def test_a_good_spec_becomes_a_draft_owned_by_the_user(self):
        result, side = self.build()
        self.assertTrue(result["ok"])
        board = self.env["levelix.board"].browse(result["board_id"])
        self.assertEqual((board.state, board.user_id, board.name), ("draft", self.boss, "Sales this month"))
        self.assertEqual(board.source_conversation_id, self.conversation)
        self.assertEqual([w["id"] for w in board.spec["widgets"]], ["w1", "w2"])
        self.assertEqual(board.version_ids.origin, "ai")
        self.assertEqual([b["type"] for b in side["blocks"]], ["board_draft", "board_explain"])

    def test_a_dashboard_with_the_amounts_switch_is_built_and_runs_both_ways(self):
        spec = sales_dashboard("")
        spec["filters"] = [{"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": "untaxed",
                            "applies_to": {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_total"}}}]
        result, _side = self.build(spec)
        self.assertTrue(result["ok"], result)
        board = self.env["levelix.board"].browse(result["board_id"])
        engine = self.env["levelix.board.engine"].with_user(self.boss).with_context(tz=TZ)
        for basis in ("untaxed", "taxed"):
            ran = engine._run_spec(board.spec, None, False, {"amounts": basis})["widgets"]
            self.assertTrue(all("frame" in r for r in ran.values()), ran)

    def test_a_switch_with_a_wrong_field_is_sent_back_to_be_fixed(self):
        spec = sales_dashboard("")
        spec["filters"] = [{"id": "amounts", "type": "amount_basis", "label": "Amounts", "applies_to": {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_totl"}}}]
        result, _side = self.build(spec)
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], "UNKNOWN_FIELD")
        self.assertIn("price_totl", result["errors"][0]["message"])

    def test_what_the_model_is_told_holds_no_data(self):
        result, _side = self.build()
        self.assertEqual(set(result), {"ok", "board_id", "widgets", "warnings", "note"})
        self.assertNotIn("Revenue", json.dumps(result))

    def test_the_blocks_carry_what_the_screen_needs(self):
        _result, side = self.build()
        draft, explain = side["blocks"]
        self.assertEqual(draft["assumptions"], ["Sales means confirmed orders.", "The date is the order date."])
        self.assertEqual(draft["uncertain"], [{"index": 0, "text": "Did you mean delivered quantities?"}])
        self.assertEqual([w["title"] for w in draft["widgets"]], ["Daily sales", "Top 10 products"])
        lines = " ".join(line["text"] for w in explain["widgets"] for line in w["lines"])
        for technical in ("sale.report", "price_subtotal", "product_uom_qty", "__count"):
            self.assertNotIn(technical, lines)
        self.assertIn("Status is Sales Order", lines)  # the plain-language version of the filter
        self.assertTrue(any(l["detail"] for w in explain["widgets"] for l in w["lines"]))  # the rest sits under "Details"
        for widget in explain["widgets"]:
            self.assertLessEqual(len([l for l in widget["lines"] if not l["detail"]]), 5)

    def test_a_question_in_the_same_conversation_rebuilds_the_draft(self):
        first, _side = self.build()
        changed = sales_dashboard("")
        changed["title"] = "Sales, changed"
        second, _side = self.build(changed)
        self.assertEqual(second["board_id"], first["board_id"])
        board = self.env["levelix.board"].browse(first["board_id"])
        self.assertEqual((board.name, board.version), ("Sales, changed", 2))
        board.state = "active"  # kept
        third, _side = self.build()
        self.assertNotEqual(third["board_id"], first["board_id"])  # the kept one is left alone

    def test_a_spec_with_errors_creates_nothing_and_says_what_to_fix(self):
        broken = sales_dashboard("")
        broken["widgets"][0]["data"]["measures"][0]["field"] = "price_subtotl"
        before = self.env["levelix.board"].search_count([])
        result, side = self.build(broken)
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["path"], "widgets[0].data.measures[0]")
        self.assertEqual(result["repairs_left"], 3)
        self.assertTrue(side["error"])
        self.assertEqual(self.env["levelix.board"].search_count([]), before)

    def test_a_spec_that_validates_but_cannot_run_is_not_kept(self):
        spec = sales_dashboard("")
        spec["widgets"][0]["data"]["domain"] = [["state", "=", "sale"], ["partner_id.nonexistent", "=", 1]]  # only the first path part is checked up front
        before = self.env["levelix.board"].search_count([])
        result, _side = self.build(spec)
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], "QUERY_FAILED")  # found by running it, and reported so the model can fix it
        self.assertEqual(self.env["levelix.board"].search_count([]), before)

    def test_a_widget_the_user_may_not_read_is_not_kept(self):
        spec = sales_dashboard("")
        spec["widgets"][1]["data"]["source"] = "ir.config_parameter"
        result, _side = self.build(spec)
        self.assertEqual((result["ok"], result["errors"][0]["code"]), (False, "NO_ACCESS"))  # the model is told the user may not read it

    def test_the_repairs_are_limited_and_the_last_failure_says_stop(self):
        broken = sales_dashboard("")
        broken["widgets"][0]["data"]["measures"][0]["field"] = "price_subtotl"
        left = []
        for attempt in range(4):
            result, side = self.build(broken)
            self.env["levelix.ai.tool.call"].sudo().create({"message_id": self.message.id, "name": "build_dashboard", "is_error": True})
            left.append((result["repairs_left"], result.get("give_up", False)))
        self.assertEqual(left, [(3, False), (2, False), (1, False), (0, True)])
        result, side = self.build(sales_dashboard(""))  # even a good spec is refused after that
        self.assertTrue(result["give_up"] and not result["ok"])
        self.assertFalse(self.env["levelix.board"].search([("source_conversation_id", "=", self.conversation.id)]))

    def test_too_many_widgets(self):
        spec = sales_dashboard("")
        spec["widgets"] = [dict(spec["widgets"][1], id="w%d" % i) for i in range(1, 10)]
        result, _side = self.build(spec)
        self.assertEqual(result["errors"][0]["code"], "TOO_MANY_WIDGETS")
        self.assertEqual(self.build({"v": 1, "widgets": []})[0]["errors"][0]["code"], "BAD_SHAPE")

    def test_bad_json_is_a_readable_error(self):
        for bad in ("{oops", "[]", 5, None):
            with self.subTest(bad=bad), self.assertRaises(UserError):
                self.run_tool("build_dashboard", spec=bad)

    def test_a_warning_is_shown_not_hidden(self):
        _result, side = self.build(sales_dashboard("cancelled"))
        codes = [w["code"] for w in side["blocks"][0]["warnings"]]
        self.assertIn("STATE_FILTER_MISSING", codes)

    def test_the_options_the_model_was_unsure_about_are_buttons_that_work(self):
        result, _side = self.build()
        rpc = self.env["levelix.board"].with_user(self.boss).with_context(tz=TZ)
        rpc.lx_apply_uncertain(result["board_id"], 0)
        board = self.env["levelix.board"].browse(result["board_id"])
        self.assertEqual(board.spec["widgets"][1]["data"]["measures"][0]["field"], "qty_delivered")
        self.assertEqual(board.version, 2)
        out = rpc.lx_run(board.id)["widgets"]
        self.assertTrue(all("frame" in w for w in out.values()), out)  # the changed dashboard still runs

    def test_an_unsure_option_that_would_break_the_dashboard_is_refused_at_build_time(self):
        spec = sales_dashboard("")
        spec["uncertain"][0]["patch"][0]["value"] = "no_such_field"
        result, _side = self.build(spec)
        self.assertEqual((result["ok"], result["errors"][0]["code"]), (False, "UNCERTAIN_PATCH_INVALID"))

    def test_the_tool_changes_no_business_data(self):
        counts = {m: self.env[m].sudo().search_count([]) for m in ("sale.order", "sale.order.line", "res.partner", "product.product", "account.move")}
        self.build()
        self.run_tool("preview_widget", widget=json.dumps(self.widget()))
        self.run_tool("get_hints", query="sales")
        self.assertEqual(counts, {m: self.env[m].sudo().search_count([]) for m in counts})
