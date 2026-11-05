"""The dashboard record: versions, visibility, rights, and the lx_* RPC checks."""
import copy

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from ..lib.errors import BoardError, SpecInvalid
from .support import BoardCase, order_spec


@tagged("post_install", "-at_install", "levelix_board")
class TestBoardRecord(BoardCase):
    def test_create_writes_the_first_version(self):
        board = self.make_board()
        self.assertEqual(board.version, 1)
        self.assertEqual(board.version_ids.mapped("version"), [1])
        self.assertEqual(board.version_ids.origin, "manual")

    def test_a_new_spec_is_a_new_version_and_the_same_spec_is_not(self):
        board = self.make_board()
        board.spec = copy.deepcopy(board.spec)  # unchanged
        self.assertEqual(board.version, 1)
        changed = copy.deepcopy(board.spec)
        changed["title"] = "Other"
        board.write({"spec": changed, "name": "Renamed"})
        self.assertEqual((board.version, board.name), (2, "Renamed"))
        self.assertEqual(sorted(board.version_ids.mapped("version")), [1, 2])
        self.assertEqual(board.version_ids.filtered(lambda v: v.version == 1).spec["title"], "Orders")

    def test_renaming_alone_does_not_add_a_version(self):
        board = self.make_board()
        board.name = "Renamed"
        self.assertEqual(board.version, 1)

    def test_a_bad_spec_is_refused_and_nothing_changes(self):
        board = self.make_board()
        bad = copy.deepcopy(board.spec)
        bad["widgets"][0]["data"]["measures"][0] = {"id": "m1", "field": "no_such_field", "agg": "sum"}
        with self.assertRaises(SpecInvalid) as ctx:
            board.write({"spec": bad})
        self.assertEqual(ctx.exception.errors[0].code, "UNKNOWN_FIELD")
        self.assertEqual((board.version, len(board.version_ids)), (1, 1))
        with self.assertRaises(SpecInvalid):
            self.make_board(spec=bad)

    def test_the_form_text_is_parsed_and_checked(self):
        board = self.make_board()
        with self.assertRaises(BoardError) as ctx:
            board.spec_text = "{not json"
        self.assertEqual(ctx.exception.code, "BAD_SPEC")
        text = board.spec_text.replace('"Orders"', '"Edited"')
        board.spec_text = text
        self.assertEqual((board.spec["title"], board.version), ("Edited", 2))

    def test_a_huge_spec_is_refused(self):
        board = self.make_board()
        huge = copy.deepcopy(board.spec)
        huge["assumptions"] = ["x" * 1000] * 600
        with self.assertRaises(UserError) as ctx:
            board.write({"spec": huge})
        self.assertIn("KB", str(ctx.exception))

    def test_sharing_with_groups_needs_a_group(self):
        board = self.make_board()
        with self.assertRaises(UserError):
            board.share_mode = "groups"


@tagged("post_install", "-at_install", "levelix_board")
class TestBoardVisibility(BoardCase):
    def setUp(self):
        super().setUp()
        self.board = self.make_board()  # owned by admin, private

    def ids_for(self, user):
        return self.as_user(user).lx_list()

    def test_private_dashboard_is_invisible_to_others(self):
        self.assertEqual([c["id"] for c in self.ids_for(self.salesman) if c["id"] == self.board.id], [])
        with self.assertRaises(BoardError) as ctx:
            self.as_user(self.salesman).lx_load(self.board.id)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")  # not "no access": its existence is not revealed
        with self.assertRaises(BoardError) as ctx:
            self.as_user(self.salesman).lx_run(self.board.id)
        self.assertEqual(ctx.exception.code, "NOT_FOUND")

    def test_company_sharing_shows_active_dashboards_only(self):
        self.board.share_mode = "company"
        self.assertIn(self.board.id, [c["id"] for c in self.ids_for(self.salesman)])
        self.board.state = "draft"
        self.assertNotIn(self.board.id, [c["id"] for c in self.ids_for(self.salesman)])

    def test_group_sharing_reaches_only_members(self):
        self.board.write({"share_mode": "groups", "group_ids": [(6, 0, [self.env.ref("sales_team.group_sale_salesman").id])]})
        self.assertIn(self.board.id, [c["id"] for c in self.ids_for(self.salesman)])
        self.assertNotIn(self.board.id, [c["id"] for c in self.ids_for(self.warehouse)])

    def test_a_viewer_cannot_change_a_shared_dashboard(self):
        self.board.share_mode = "company"
        loaded = self.as_user(self.salesman).lx_load(self.board.id)
        self.assertEqual((loaded["can_edit"], loaded["is_owner"], loaded["own_rights"]), (False, False, True))
        with self.assertRaises(BoardError) as ctx:
            self.as_user(self.salesman).lx_save(self.board.id, self.board.spec)
        self.assertEqual(ctx.exception.code, "NO_ACCESS")
        with self.assertRaises(AccessError):
            self.board.with_user(self.salesman).write({"name": "Mine now"})
        with self.assertRaises(AccessError):
            self.board.with_user(self.salesman).unlink()

    def test_a_manager_sees_and_changes_everything(self):
        manager = new_test_user(self.env, "board_manager", groups="base.group_user,levelix_board.group_board_manager")
        self.assertIn(self.board.id, [c["id"] for c in self.ids_for(manager)])
        self.board.with_user(manager).write({"name": "Renamed by the manager"})
        self.assertEqual(self.board.name, "Renamed by the manager")
        # saving a spec is checked with the saver's own rights: this manager cannot read orders, so the spec is refused
        with self.assertRaises(SpecInvalid) as ctx:
            self.as_user(manager).lx_save(self.board.id, self.board.spec)
        self.assertEqual(ctx.exception.errors[0].code, "NO_ACCESS")

    def test_history_is_for_the_owner(self):
        self.assertTrue(self.board.with_user(self.admin).version_ids)
        self.board.share_mode = "company"
        self.assertFalse(self.env["levelix.board.version"].with_user(self.salesman).search([("board_id", "=", self.board.id)]))

    def test_other_companies_are_hidden(self):
        other = self.env["res.company"].create({"name": "Levelix other company"})
        foreign = self.env["levelix.board"].sudo().create({"name": "Foreign", "company_id": other.id, "spec": order_spec(self.partners)})
        self.assertNotIn(foreign.id, [c["id"] for c in self.as_user(self.admin).lx_list()])
        with self.assertRaises(BoardError):
            self.as_user(self.admin).lx_load(foreign.id)

    def test_numbers_follow_the_viewers_rights(self):
        self.board.share_mode = "company"
        admin_view = self.as_user(self.admin).lx_run(self.board.id, ["w3"])
        seller_view = self.as_user(self.salesman).lx_run(self.board.id, ["w3"])
        self.assertEqual(admin_view["widgets"]["w3"]["frame"]["rows"], [[3]])  # all three orders
        self.assertEqual(seller_view["widgets"]["w3"]["frame"]["rows"], [[1]])  # only the seller's own order

    def test_one_widget_without_rights_does_not_break_the_others(self):
        self.board.share_mode = "company"
        out = self.as_user(self.warehouse).lx_run(self.board.id)["widgets"]
        self.assertEqual(out["w3"]["error"]["code"], "NO_ACCESS")
        self.assertIn("frame", out["w4"])


@tagged("post_install", "-at_install", "levelix_board")
class TestBoardRpc(BoardCase):
    def setUp(self):
        super().setUp()
        self.board = self.make_board()
        self.rpc = self.as_user(self.admin)

    def assertCode(self, code, call, *args, **kwargs):
        with self.assertRaises(BoardError) as ctx:
            call(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    def test_list_and_load(self):
        card = next(c for c in self.rpc.lx_list() if c["id"] == self.board.id)
        self.assertEqual((card["name"], card["version"], card["widgets"], card["is_owner"], card["can_edit"]), ("Orders board", 1, 4, True, True))
        loaded = self.rpc.lx_load(self.board.id)
        self.assertEqual(loaded["spec"]["widgets"][0]["id"], "w1")
        self.assertFalse(loaded["own_rights"])

    def test_run_returns_frames_and_the_version(self):
        out = self.rpc.lx_run(self.board.id, ["w1", "w3"])
        self.assertEqual(sorted(out["widgets"]), ["w1", "w3"])
        self.assertEqual(out["version"], 1)

    def test_explain_gives_lines_per_widget(self):
        out = self.rpc.lx_explain(self.board.id, ["w3"])
        self.assertTrue(out["w3"]["explain"])
        self.assertEqual(out["w3"]["explain"][0]["kind"], "source")

    def test_save_validates_and_versions(self):
        spec = copy.deepcopy(self.board.spec)
        spec["title"] = "Second"
        saved = self.rpc.lx_save(self.board.id, spec, "second try")
        self.assertEqual((saved["version"], saved["changed"]), (2, True))
        self.assertEqual(self.board.version_ids.filtered(lambda v: v.version == 2).note, "second try")
        self.assertEqual(self.rpc.lx_save(self.board.id, spec)["changed"], False)
        spec["widgets"][0]["data"]["source"] = "no.such"
        with self.assertRaises(SpecInvalid):
            self.rpc.lx_save(self.board.id, spec)
        self.assertEqual(self.board.version, 2)

    def test_arguments_are_checked(self):
        for bad in (None, False, True, "1", 0, -3, 1.5, [1]):
            with self.subTest(board_id=bad):
                self.assertCode("BAD_ARGUMENT", self.rpc.lx_load, bad)
        self.assertCode("NOT_FOUND", self.rpc.lx_load, 99999999)
        self.assertCode("BAD_ARGUMENT", self.rpc.lx_run, self.board.id, "w1")
        self.assertCode("BAD_ARGUMENT", self.rpc.lx_run, self.board.id, [1, 2])
        self.assertCode("BAD_ARGUMENT", self.rpc.lx_run, self.board.id, ["w1"] * 31)
        self.assertCode("UNKNOWN_WIDGET", self.rpc.lx_run, self.board.id, ["nope"])
        self.assertCode("UNSUPPORTED", self.rpc.lx_run, self.board.id, None, {"period": "this_month"})
        self.assertCode("BAD_ARGUMENT", self.rpc.lx_save, self.board.id, "not a spec")
        self.assertCode("BAD_ARGUMENT", self.rpc.lx_save, self.board.id, {}, "x" * 501)
        self.assertCode("BAD_ARGUMENT", self.rpc.lx_drill, self.board.id, None, [])
        self.assertCode("UNKNOWN_WIDGET", self.rpc.lx_drill, self.board.id, "nope", [])

    def test_an_archived_dashboard_is_gone(self):
        self.board.active = False
        self.assertCode("NOT_FOUND", self.rpc.lx_run, self.board.id)

    def test_an_unexpected_bug_stays_inside_its_widget(self):
        from unittest import mock

        from ..lib.planner import Planner
        with mock.patch.object(Planner, "plan", side_effect=TypeError("boom")):
            out = self.rpc.lx_run(self.board.id, ["w3", "w4"])["widgets"]
        self.assertEqual(out["w3"]["error"]["code"], "INTERNAL")
        self.assertEqual(out["w4"]["error"]["code"], "INTERNAL")  # reported per widget, the call itself succeeds
        self.assertNotIn("boom", str(out))  # no internals leak to the browser
