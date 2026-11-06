"""Editing a dashboard: stale saves, layout, history and restore, sharing, copies, archive."""
from odoo.tests import tagged

from ..lib.errors import BoardError
from .support import BoardCase, order_spec, widget


@tagged("post_install", "-at_install", "levelix_board")
class TestEditing(BoardCase):
    def setUp(self):
        super().setUp()
        self.board = self.make_board()
        self.owner = self.as_user(self.admin)

    def assertCode(self, code, method, *args, **kw):
        with self.assertRaises(BoardError) as caught:
            method(*args, **kw)
        self.assertEqual(caught.exception.code, code, caught.exception.detail)

    def spec_with_title(self, title):
        return dict(self.board.spec, title=title)

    # -- two people editing -------------------------------------------------------------------------------

    def test_a_save_made_from_an_old_version_overwrites_nothing(self):
        start = self.board.version
        self.owner.lx_save(self.board.id, self.spec_with_title("First"), None, start)
        self.assertEqual(self.board.version, start + 1)
        self.assertCode("STALE_VERSION", self.owner.lx_save, self.board.id, self.spec_with_title("Second"), None, start)  # the other window
        self.assertEqual(self.board.spec["title"], "First")  # not overwritten
        self.owner.lx_save(self.board.id, self.spec_with_title("Second"), None, start + 1)  # after reloading
        self.assertEqual(self.board.spec["title"], "Second")
        self.owner.lx_save(self.board.id, self.spec_with_title("Third"))  # no base given: the old behaviour (the assistant, scripts)
        self.assertEqual(self.board.spec["title"], "Third")

    def test_the_same_goes_for_patches_and_restores_and_the_base_must_be_a_number(self):
        start = self.board.version
        self.owner.lx_apply_patch(self.board.id, [{"op": "replace", "path": "/title", "value": "Patched"}], None, start)
        self.assertCode("STALE_VERSION", self.owner.lx_apply_patch, self.board.id, [{"op": "replace", "path": "/title", "value": "X"}], None, start)
        self.assertCode("STALE_VERSION", self.owner.lx_restore, self.board.id, 1, start)
        for bad in ("2", 1.5, True, [1]):
            with self.subTest(bad=bad):
                self.assertCode("BAD_ARGUMENT", self.owner.lx_save, self.board.id, self.board.spec, None, bad)

    # -- layout ---------------------------------------------------------------------------------------------

    def test_a_layout_changes_only_the_places(self):
        before = {w["id"]: w for w in self.board.spec["widgets"]}
        out = self.owner.lx_save_layout(self.board.id, {"w1": {"x": 0, "y": 0, "w": 16, "h": 8}, "w2": {"x": 16, "y": 0, "w": 8, "h": 8}})
        self.assertTrue(out["changed"])
        after = {w["id"]: w for w in self.board.spec["widgets"]}
        self.assertEqual(after["w1"]["grid"], {"x": 0, "y": 0, "w": 16, "h": 8})
        for wid, widget_ in after.items():  # nothing but the grid differs
            self.assertEqual({k: v for k, v in widget_.items() if k != "grid"}, {k: v for k, v in before[wid].items() if k != "grid"})
        self.assertNotIn("grid", after["w3"])  # a widget that was not named keeps what it had
        self.assertEqual(self.board.version_ids.sorted("version")[-1].note, "Layout changed")
        again = self.owner.lx_save_layout(self.board.id, {"w1": {"x": 0, "y": 0, "w": 16, "h": 8}})
        self.assertFalse(again["changed"])  # the same places: no new version

    def test_a_layout_must_fit_the_page(self):
        cell = lambda **kw: {"x": 0, "y": 0, "w": 6, "h": 4, **kw}  # noqa: E731
        for bad in ({}, {"nope": cell()}, {"w1": cell(x=-1)}, {"w1": cell(w=0)}, {"w1": cell(x=20, w=6)}, {"w1": cell(w=25)}, {"w1": cell(h=0)}, {"w1": cell(y=-2)},
                    {"w1": {"x": 0, "y": 0, "w": 6}}, {"w1": cell(x="0")}, {"w1": cell(x=True)}, {"w1": cell(x=1.5)}, {"w1": "6x4"}, [1], None):
            with self.subTest(bad=bad), self.assertRaises(BoardError):
                self.owner.lx_save_layout(self.board.id, bad)

    # -- history -------------------------------------------------------------------------------------------

    def test_the_history_lists_every_save_with_what_changed(self):
        self.owner.lx_save_layout(self.board.id, {"w1": {"x": 0, "y": 0, "w": 12, "h": 8}})
        spec = dict(self.board.spec, widgets=[w for w in self.board.spec["widgets"] if w["id"] != "w4"], title="Smaller")
        self.owner.lx_save(self.board.id, spec, "Dropped the contacts widget")
        history = self.owner.lx_versions(self.board.id)
        self.assertEqual([h["version"] for h in history], [3, 2, 1])
        self.assertEqual([h["current"] for h in history], [True, False, False])
        self.assertEqual(history[0]["note"], "Dropped the contacts widget")
        self.assertEqual((history[0]["changes"]["removed"], history[0]["changes"]["other"]), (["w4"], ["title"]))
        self.assertEqual(history[1]["changes"]["moved"], ["w1"])
        self.assertEqual(len(history[2]["changes"]["added"]), 4)  # the first version added everything
        self.assertEqual((history[0]["author"], history[0]["origin"]), (self.admin.name, "manual"))

    def test_only_the_owner_and_managers_read_the_history(self):
        self.owner.lx_share(self.board.id, "company")
        self.assertCode("NO_ACCESS", self.as_user(self.salesman).lx_versions, self.board.id)  # may open it, may not read its history
        self.assertTrue(self.as_user(self.admin).lx_versions(self.board.id))

    def test_restoring_makes_a_new_version_and_loses_no_history(self):
        original = self.board.spec
        self.owner.lx_save(self.board.id, self.spec_with_title("Changed"))
        self.owner.lx_save(self.board.id, dict(self.board.spec, widgets=self.board.spec["widgets"][:1]))
        out = self.owner.lx_restore(self.board.id, 1)
        self.assertTrue(out["changed"])
        self.assertEqual(self.board.version, 4)  # a new version on top, not a step back
        self.assertEqual(self.board.spec, original)
        self.assertEqual(self.board.version_ids.sorted("version")[-1].origin, "restore")
        self.assertEqual(self.board.version_ids.sorted("version")[-1].note, "Restored version 1")
        self.assertEqual([h["version"] for h in self.owner.lx_versions(self.board.id)], [4, 3, 2, 1])
        self.assertCode("NOT_FOUND", self.owner.lx_restore, self.board.id, 99)
        for bad in ("1", None, True, 1.5):
            with self.subTest(bad=bad):
                self.assertCode("BAD_ARGUMENT", self.owner.lx_restore, self.board.id, bad)

    def test_a_viewer_cannot_restore(self):
        self.owner.lx_share(self.board.id, "company")
        self.assertCode("NO_ACCESS", self.as_user(self.salesman).lx_restore, self.board.id, 1)

    # -- sharing ---------------------------------------------------------------------------------------------

    def listed(self, user):
        return self.as_user(user).lx_list()

    def test_the_three_levels_decide_who_sees_it(self):
        seller = self.salesman
        self.assertFalse([c for c in self.listed(seller) if c["id"] == self.board.id])  # private
        self.owner.lx_share(self.board.id, "company")
        self.assertEqual([c["share_mode"] for c in self.listed(seller) if c["id"] == self.board.id], ["company"])
        group = self.env.ref("sales_team.group_sale_salesman")
        self.owner.lx_share(self.board.id, "groups", [group.id])
        self.assertTrue([c for c in self.listed(seller) if c["id"] == self.board.id])  # the seller is in that group
        self.assertFalse([c for c in self.listed(self.warehouse) if c["id"] == self.board.id])  # the keeper is not
        self.owner.lx_share(self.board.id, "private")
        self.assertFalse([c for c in self.listed(seller) if c["id"] == self.board.id])
        self.assertEqual(self.board.group_ids.ids, [])  # going private forgets the groups

    def test_a_reader_cannot_change_who_it_is_shared_with(self):
        self.owner.lx_share(self.board.id, "company")
        self.assertCode("NO_ACCESS", self.as_user(self.salesman).lx_share, self.board.id, "private")
        self.assertEqual(self.board.share_mode, "company")

    def test_a_bad_share_is_refused(self):
        group = self.env.ref("sales_team.group_sale_salesman")
        for mode, groups in (("everyone", None), (None, None), ("groups", None), ("groups", []), ("groups", ["x"]), ("groups", [True]),
                             ("groups", list(range(1, 30))), ("groups", [99999999]), ("groups", [self.env.ref("base.group_portal").id]),
                             ("groups", [self.env.ref("base.group_system").id])):
            with self.subTest(mode=mode, groups=groups), self.assertRaises(BoardError):
                self.owner.lx_share(self.board.id, mode, groups)
        self.owner.lx_share(self.board.id, "groups", [group.id])  # a real access group is fine

    def test_the_groups_on_offer_are_access_groups_without_the_technical_ones(self):
        offered = {o["id"] for o in self.owner.lx_share_options()}
        self.assertIn(self.env.ref("sales_team.group_sale_salesman").id, offered)
        self.assertNotIn(self.env.ref("base.group_portal").id, offered)
        self.assertNotIn(self.env.ref("base.group_public").id, offered)

    def test_a_draft_cannot_be_shared_until_it_is_kept(self):
        draft = self.make_board(state="draft")
        self.assertCode("NOT_KEPT", self.owner.lx_share, draft.id, "company")
        self.owner.lx_share(draft.id, "private")  # private is always fine
        self.owner.lx_activate(draft.id)
        self.assertEqual(self.owner.lx_share(draft.id, "company")["share_mode"], "company")

    def test_a_reader_sees_his_own_numbers(self):
        self.owner.lx_share(self.board.id, "company")
        as_seller = self.as_user(self.salesman).lx_run(self.board.id, ["w3"])["widgets"]["w3"]["frame"]["rows"]
        as_owner = self.owner.lx_run(self.board.id, ["w3"])["widgets"]["w3"]["frame"]["rows"]
        self.assertEqual((as_owner, as_seller), ([[3]], [[1]]))  # the seller owns one of the three orders

    # -- copies and archive ----------------------------------------------------------------------------------

    def test_a_copy_is_private_independent_and_owned_by_who_made_it(self):
        self.owner.lx_share(self.board.id, "company")
        seller = self.as_user(self.salesman)
        card = seller.lx_clone(self.board.id)
        copy = self.env["levelix.board"].browse(card["id"])
        self.assertEqual((copy.user_id, copy.share_mode, copy.state, copy.name), (self.salesman, "private", "active", "Orders board (copy)"))
        self.assertEqual(copy.spec["widgets"], self.board.spec["widgets"])
        self.assertEqual(copy.spec["title"], "Orders board (copy)")  # the page shows the title of the spec
        self.assertEqual(copy.version_ids.note, "Copy of «Orders board»")
        seller.lx_save(copy.id, dict(copy.spec, title="Mine"))  # changing the copy leaves the original alone
        self.assertNotEqual(self.board.spec.get("title"), "Mine")
        self.assertEqual(seller.lx_clone(self.board.id, "My own name")["name"], "My own name")

    def test_one_cannot_copy_what_one_cannot_open(self):
        self.assertCode("NOT_FOUND", self.as_user(self.salesman).lx_clone, self.board.id)  # private to the owner
        for bad in ("", "  ", "x" * 200, 5):
            with self.subTest(bad=bad):
                self.assertCode("BAD_ARGUMENT", self.owner.lx_clone, self.board.id, bad)

    def test_the_assistants_options_do_not_travel_with_a_copy(self):
        spec = dict(self.board.spec, uncertain=[{"text": "Delivered instead?", "patch": [{"op": "replace", "path": "/title", "value": "x"}]}])
        self.board.write({"spec": spec})
        self.assertNotIn("uncertain", self.env["levelix.board"].browse(self.owner.lx_clone(self.board.id)["id"]).spec)

    def test_archiving_hides_it_from_the_lists(self):
        self.owner.lx_share(self.board.id, "company")
        self.assertCode("NO_ACCESS", self.as_user(self.salesman).lx_archive, self.board.id)
        self.assertTrue(self.owner.lx_archive(self.board.id))
        self.assertFalse([c for c in self.listed(self.admin) + self.listed(self.salesman) if c["id"] == self.board.id])
        self.assertCode("NOT_FOUND", self.owner.lx_load, self.board.id)
        self.assertTrue(self.board.with_context(active_test=False).exists())  # not deleted

    def test_the_editor_learns_the_shapes_from_the_server(self):
        meta = self.owner.lx_meta()
        self.assertEqual(meta["shapes"]["heatmap"], {"dimensions": [2, 2], "measures": [1, 1]})
        self.assertEqual(meta["shapes"]["kpi"]["measures"], [1, 3])
        self.assertEqual(meta["grid_columns"], 24)


@tagged("post_install", "-at_install", "levelix_board")
class TestAddingAWidget(BoardCase):
    def setUp(self):
        super().setUp()
        self.rpc = self.as_user(self.admin)

    def test_the_sources_are_reporting_models_the_user_may_read(self):
        sources = {o["model"] for o in self.rpc.lx_sources()}
        self.assertIn("sale.report", sources)
        self.assertNotIn("sale.order", sources)  # an ordinary model is not a source offered here
        self.assertNotIn("ir.config_parameter", sources)
        self.assertNotIn("sale.report", {o["model"] for o in self.as_user(self.warehouse).lx_sources()})  # a keeper may not read sales

    def test_the_fields_say_what_can_be_grouped_and_measured(self):
        out = self.rpc.lx_fields("sale.report")
        dims = {d["name"]: d["type"] for d in out["dimensions"]}
        self.assertEqual((dims["date"], dims["partner_id"], dims["state"]), ("datetime", "many2one", "selection"))
        measures = {m["name"]: m["aggregates"] for m in out["measures"]}
        self.assertIn("sum", measures["price_subtotal"])
        self.assertNotIn("sum", measures["price_unit"])  # a price is averaged, never added up
        self.assertIn(["sale", "Sales Order"], out["state"]["values"])
        self.assertEqual(out["label"], "Sales Analysis Report")

    def test_the_fields_of_a_model_one_may_not_read_are_refused(self):
        with self.assertRaises(BoardError) as caught:
            self.as_user(self.warehouse).lx_fields("sale.report")
        self.assertEqual(caught.exception.code, "NO_ACCESS")
        for bad in (None, 5, "no.such.model"):
            with self.subTest(bad=bad), self.assertRaises(BoardError):
                self.rpc.lx_fields(bad)

    def test_a_widget_that_is_not_saved_yet_can_be_previewed(self):
        good = widget("n1", "bar", source="sale.report", domain=[["state", "=", "sale"]], dimensions=[{"field": "partner_id"}],
                      measures=[{"id": "m1", "field": "price_subtotal", "agg": "sum"}])
        frame = self.rpc.lx_preview_widget(good)["frame"]
        self.assertEqual([c["id"] for c in frame["columns"]], ["partner_id", "m1"])
        bad = widget("n1", "bar", source="sale.report", dimensions=[{"field": "nope"}], measures=[{"id": "m1", "agg": "count"}])
        with self.assertRaises(BoardError) as caught:
            self.rpc.lx_preview_widget(bad)
        self.assertEqual(caught.exception.code, "UNKNOWN_FIELD")
        for odd in (None, [], {"type": "kpi"}, {"id": 5}):
            with self.subTest(odd=odd), self.assertRaises(BoardError):
                self.rpc.lx_preview_widget(odd)
