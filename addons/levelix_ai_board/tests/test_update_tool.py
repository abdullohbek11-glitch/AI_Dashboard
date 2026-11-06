"""Changing a dashboard from the chat: small patches, the right target, the rights, the repair limit and what the model is handed."""
import json

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.levelix_ai_core.tests.fake_ai import sales_dashboard
from odoo.addons.levelix_ai_core.tests.support import TZ

from .test_board_tools import BoardToolsCase


@tagged("post_install", "-at_install", "levelix_ai_board", "-standard")
class TestUpdateTool(BoardToolsCase):
    def build(self):
        result, _side = self.tools._run("build_dashboard", {"spec": json.dumps(sales_dashboard(""))}, self.message)
        self.assertTrue(result["ok"], result)
        return self.env["levelix.board"].browse(result["board_id"])

    def update(self, patch, board=None, user=None):
        tools = (self.env["levelix.ai.tools"].with_user(user) if user else self.tools).with_context(tz=TZ)
        args = {"patch": json.dumps(patch)}
        if board:
            args["board_id"] = board.id
        return tools._run("update_dashboard", args, self.message)

    def test_a_patch_changes_only_what_it_names_and_keeps_the_ids(self):
        board = self.build()
        before = board.spec["widgets"]
        result, side = self.update([{"op": "replace", "path": "/widgets/1/type", "value": "table"}])
        self.assertTrue(result["ok"], result)
        board = board.with_user(self.boss)
        self.assertEqual([w["id"] for w in board.spec["widgets"]], ["w1", "w2"])
        self.assertEqual(board.spec["widgets"][1]["type"], "table")
        self.assertEqual(board.spec["widgets"][0], before[0])
        self.assertEqual(board.version_ids.sorted("version")[-1].origin, "ai")
        self.assertEqual([b["type"] for b in side["blocks"]], ["board_draft", "board_explain"])

    def test_a_period_change_keeps_the_rest_of_the_widget(self):
        board = self.build()
        result, _side = self.update([{"op": "replace", "path": "/widgets/0/data/domain/1", "value": ["date", ">=", "today -89d"]}])
        self.assertTrue(result["ok"], result)
        widget = board.with_user(self.boss).spec["widgets"][0]
        self.assertEqual(widget["data"]["domain"][1], ["date", ">=", "today -89d"])
        self.assertEqual(widget["view"], {"smooth": True})

    def test_a_widget_can_be_added_and_removed(self):
        board = self.build()
        kpi = {"id": "w3", "type": "kpi", "title": "Revenue", "data": {"source": "sale.report", "domain": [["state", "=", "sale"]],
                                                                     "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"}]}}
        result, _side = self.update([{"op": "add", "path": "/widgets/-", "value": kpi}])
        self.assertTrue(result["ok"], result)
        self.assertEqual([w["id"] for w in board.with_user(self.boss).spec["widgets"]], ["w1", "w2", "w3"])
        result, _side = self.update([{"op": "remove", "path": "/widgets/0"}])
        self.assertTrue(result["ok"], result)
        self.assertEqual([w["id"] for w in board.with_user(self.boss).spec["widgets"]], ["w2", "w3"])

    def test_a_kept_dashboard_is_changed_by_its_id_and_the_history_can_undo_it(self):
        board = self.build()
        self.env["levelix.board"].with_user(self.boss).lx_activate(board.id)
        old = board.version
        result, _side = self.update([{"op": "replace", "path": "/title", "value": "Sales, three months"}], board=board)
        self.assertTrue(result["ok"], result)
        board = board.with_user(self.boss)
        self.assertEqual((board.name, board.version), ("Sales, three months", old + 1))
        self.env["levelix.board"].with_user(self.boss).lx_restore(board.id, old)
        self.assertEqual(board.spec["title"], "Sales this month")

    def test_without_a_target_nothing_is_guessed(self):
        with self.assertRaises(UserError):
            self.update([{"op": "replace", "path": "/title", "value": "x"}])

    def test_someone_who_may_not_write_it_cannot_change_it(self):
        board = self.build()
        self.env["levelix.board"].with_user(self.boss).lx_activate(board.id)
        with self.assertRaises(UserError):
            self.update([{"op": "replace", "path": "/title", "value": "x"}], board=board, user=self.plain)
        self.assertEqual(board.with_user(self.boss).spec["title"], "Sales this month")

    def test_a_bad_patch_is_sent_back_and_the_dashboard_stays(self):
        board = self.build()
        for path in ("/widgets/0/id", "/version"):
            result, _side = self.update([{"op": "replace", "path": path, "value": "w9" if "id" in path else 3}])
            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "BAD_PATCH")
        self.assertEqual([w["id"] for w in board.with_user(self.boss).spec["widgets"]], ["w1", "w2"])

    def test_a_patch_that_breaks_a_widget_is_refused_by_the_checks(self):
        board = self.build()
        result, _side = self.update([{"op": "replace", "path": "/widgets/1/data/measures/0/field", "value": "no_such_field"}])
        self.assertFalse(result["ok"])
        self.assertEqual(board.with_user(self.boss).spec["widgets"][1]["data"]["measures"][0]["field"], "product_uom_qty")

    def test_the_repairs_run_out(self):
        self.build()
        calls = self.env["levelix.ai.tool.call"].sudo()
        bad = [{"op": "replace", "path": "/widgets/0/id", "value": "x"}]
        last = None
        for _ in range(5):
            last, side = self.update(bad)
            calls.create({"message_id": self.message.id, "name": "update_dashboard", "is_error": True, "error": side.get("error")})
            if last.get("give_up"):
                break
        self.assertTrue(last.get("give_up"))

    def test_the_model_is_handed_the_spec_of_a_dashboard_the_chat_is_about(self):
        board = self.build()
        self.env["levelix.board"].with_user(self.boss).lx_activate(board.id)
        engine = self.env["levelix.ai.engine"].with_user(self.boss)
        line = engine._context_line({"mentions": [{"model": "levelix.board", "id": board.id}]})
        self.assertIn("[dashboard #%d" % board.id, line)
        self.assertIn('"Daily sales"', line)
        other = self.env["levelix.ai.engine"].with_user(self.plain)._context_line({"mentions": [{"model": "levelix.board", "id": board.id}]})
        self.assertNotIn("[dashboard #", other)

    def test_structure_only_mode_hands_over_no_titles_or_values(self):
        board = self.build()
        self.env["ir.config_parameter"].sudo().set_param("levelix_ai.privacy", "schema")
        line = self.env["levelix.ai.engine"].with_user(self.boss)._context_line({"mentions": [{"model": "levelix.board", "id": board.id}]})
        self.assertIn("[dashboard #%d" % board.id, line)
        self.assertIn('"w2"', line)
        self.assertIn("product_uom_qty", line)
        self.assertNotIn("Daily sales", line)
        self.assertNotIn("today -89d", line)

    def test_the_guide_says_last_months_are_days(self):
        from ..lib.guide import DASHBOARD_RULES
        self.assertIn("today -89d", DASHBOARD_RULES)

    def test_the_chat_that_made_a_dashboard_is_listed_for_it(self):
        board = self.build()
        chats = self.env["levelix.ai.conversation"].with_user(self.boss).lx_pinned("levelix.board", board.id)
        self.assertEqual([(c["id"], c["made_it"]) for c in chats], [(self.conversation.id, True)])
        self.assertEqual(self.env["levelix.ai.conversation"].with_user(self.plain).lx_pinned("levelix.board", board.id), [])
