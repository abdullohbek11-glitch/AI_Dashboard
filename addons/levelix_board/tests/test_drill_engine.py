"""Drill-down on the real ORM: the opened records must be exactly the clicked group."""
from unittest import mock

from odoo.tests import tagged

from ..lib import drill as drill_lib
from ..lib.errors import BoardError, SpecInvalid
from .support import BoardCase, order_spec, widget


@tagged("post_install", "-at_install", "levelix_board")
class TestDrillEngine(BoardCase):
    def setUp(self):
        super().setUp()
        self.board = self.make_board()
        self.rpc = self.as_user(self.admin)

    def frame(self, wid):
        return self.rpc.lx_run(self.board.id, [wid])["widgets"][wid]["frame"]

    def drill(self, wid, ref, rpc=None):
        return (self.rpc if rpc is None else rpc).lx_drill(self.board.id, wid, ref)  # an empty recordset is falsy

    def assertCode(self, code, *args):
        with self.assertRaises(BoardError) as ctx:
            self.drill(*args)
        self.assertEqual(ctx.exception.code, code)

    def test_every_day_opens_exactly_its_orders(self):
        frame = self.frame("w1")
        self.assertEqual([r[0] for r in frame["rows"]], ["2024-03-10", "2024-03-11"])
        for row, ref in zip(frame["rows"], frame["meta"]["group_refs"]):
            result = self.drill("w1", ref)
            self.assertEqual(result["total"], row[1], row)
            self.assertEqual(len(result["rows"]), row[1])
        # 10 March in Tashkent holds both admin orders
        first = self.drill("w1", frame["meta"]["group_refs"][0])
        self.assertCountEqual(first["ids"], (self.order_1 + self.order_2).ids)

    def test_every_customer_opens_exactly_its_orders(self):
        frame = self.frame("w2")
        by_name = dict(zip((r[0] for r in frame["rows"]), frame["meta"]["group_refs"]))
        result = self.drill("w2", by_name["Levelix drill customer A"])
        self.assertCountEqual(result["ids"], (self.order_1 + self.order_3).ids)
        self.assertEqual(result["total"], 2)

    def test_an_empty_filled_in_day_opens_nothing_but_a_made_up_day_is_refused(self):
        spec = order_spec(self.partners)
        base = spec["widgets"][0]["data"]["domain"] + [["date_order", ">=", "2024-03-10"], ["date_order", "<=", "2024-03-13"]]
        spec["widgets"][0]["data"].update(domain=base, fill_gaps=True)
        board = self.make_board(spec=spec)
        frame = self.rpc.lx_run(board.id, ["w1"])["widgets"]["w1"]["frame"]
        self.assertEqual([r[0] for r in frame["rows"]], ["2024-03-10", "2024-03-11", "2024-03-12", "2024-03-13"])
        empty = self.rpc.lx_drill(board.id, "w1", frame["meta"]["group_refs"][2])
        self.assertEqual((empty["total"], empty["rows"]), (0, []))
        self.assertEqual(self.env["sale.order"].search_count(empty["action"]["domain"]), 0)
        with self.assertRaises(BoardError):
            self.rpc.lx_drill(board.id, "w1", ["2024-03-30 19:00:00"])

    def test_a_widget_without_axes_opens_all_its_records(self):
        result = self.drill("w3", [])
        self.assertEqual(result["total"], 3)
        self.assertEqual([c["id"] for c in result["columns"]], ["name", "partner_id", "state", "date_order"])
        name, partner, state, when = result["rows"][0]
        self.assertTrue(name.startswith("S"))
        self.assertIn("Levelix drill customer", partner)
        self.assertEqual(state, "Sales Order")
        self.assertRegex(when, r"^2024-03-1\d \d\d:\d\d$")  # shown in the viewer's time zone

    def test_the_result_carries_an_action_that_opens_the_same_records(self):
        result = self.drill("w3", [])
        action = result["action"]
        self.assertEqual((action["type"], action["res_model"]), ("ir.actions.act_window", "sale.order"))
        self.assertEqual(self.env["sale.order"].search_count(action["domain"]), result["total"])

    def test_a_report_widget_can_open_the_orders_behind_it(self):
        spec = order_spec(self.partners)
        spec["widgets"] = [widget(
            "w1", "area", source="sale.report",
            domain=[["state", "=", "sale"], ["partner_id", "in", self.partners.ids]],
            dimensions=[{"field": "date", "granularity": "day"}],
            measures=[{"id": "m1", "field": "name", "agg": "count_distinct"}],
            interact={"on_click": {"action": "drill", "model": "sale.order", "map": {"date": "date_order"}, "columns": ["name"]}})]
        board = self.make_board(spec=spec)
        frame = self.rpc.lx_run(board.id)["widgets"]["w1"]["frame"]
        for row, ref in zip(frame["rows"], frame["meta"]["group_refs"]):
            self.assertEqual(self.rpc.lx_drill(board.id, "w1", ref)["total"], row[1], row)

    def test_the_reader_sees_only_the_records_he_may_read(self):
        self.board.share_mode = "company"
        seller = self.as_user(self.salesman)
        self.assertEqual(self.drill("w3", [], seller)["ids"], self.order_3.ids)

    def test_the_list_is_cut_and_says_so(self):
        with mock.patch.object(drill_lib, "MAX_DRILL_ROWS", 2):
            result = self.drill("w3", [])
        self.assertEqual((len(result["rows"]), result["total"], result["truncated"]), (2, 3, True))

    def test_a_made_up_group_is_refused(self):
        self.assertCode("DRILL_BAD_REF", "w1", ["2024-03-08 19:00:00"])
        self.assertCode("DRILL_BAD_REF", "w1", [])
        self.assertCode("DRILL_BAD_REF", "w1", "2024-03-10 19:00:00")
        self.assertCode("DRILL_BAD_REF", "w2", [987654321])
        self.assertCode("DRILL_BAD_REF", "w2", [[1, 2]])

    def test_the_client_cannot_slip_a_domain_in(self):
        # a domain-looking ref is just a ref that matches no group
        self.assertCode("DRILL_BAD_REF", "w2", [["id", ">", 0]])
        self.assertCode("DRILL_BAD_REF", "w3", [["id", ">", 0]])

    def test_others_cannot_be_opened(self):
        self.assertCode("DRILL_OTHERS", "w2", ["__others__"])

    def test_a_widget_that_does_not_drill(self):
        self.assertCode("DRILL_NOT_CONFIGURED", "w4", [])

    def test_a_missing_map_is_caught_when_saving(self):
        spec = order_spec(self.partners)
        spec["widgets"] = [widget(
            "w1", "area", source="sale.report", domain=[["state", "=", "sale"]],
            dimensions=[{"field": "date", "granularity": "day"}], measures=[{"id": "m1", "agg": "count"}],
            interact={"on_click": {"action": "drill", "model": "sale.order", "columns": ["name"]}})]
        with self.assertRaises(SpecInvalid) as ctx:
            self.rpc.lx_save(self.board.id, spec)
        self.assertEqual(ctx.exception.errors[0].code, "DRILL_UNMAPPED")
