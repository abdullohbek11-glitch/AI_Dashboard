"""Drill configuration and the pure parts of drill-down (no database)."""
from copy import deepcopy

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import drill
from ..lib.errors import BoardError
from ..lib.frame import FrameBuilder
from ..lib.planner import DimMeta
from ..lib.spec import Spec
from ..lib.validator import Validator
from .fixtures import SALE_ORDER, catalog, sample_spec


def codes(widget_patch=None, click_patch=None):
    raw = deepcopy(sample_spec())
    if widget_patch:
        raw["widgets"][0].update(widget_patch)
    if click_patch:
        raw["widgets"][0]["interact"]["on_click"].update(click_patch)
    result = Validator(catalog()).validate_widget(Spec.from_raw(raw).widgets[0], "w")
    return [(e.code, e.path) for e in result.errors]


@tagged("levelix_board", "-at_install", "post_install")
class TestDrillConfig(BaseCase):
    def test_sample_drill_is_valid(self):
        self.assertEqual(codes(), [])

    def test_unknown_interact_and_click_keys(self):
        self.assertEqual(codes({"interact": {"on_hover": {}}}), [("UNKNOWN_KEY", "w.interact")])
        self.assertEqual(codes(click_patch={"colour": "red"}), [("UNKNOWN_KEY", "w.interact.on_click")])

    def test_unknown_action_and_not_built_actions(self):
        self.assertEqual(codes(click_patch={"action": "explode"}), [("BAD_ACTION", "w.interact.on_click.action")])
        self.assertEqual(codes(click_patch={"action": "filter"}), [("UNSUPPORTED", "w.interact.on_click.action")])
        self.assertEqual(codes({"interact": {"on_click": {"action": "none"}}}), [])

    def test_open_as_must_be_known(self):
        self.assertEqual(codes(click_patch={"open_as": "popup"}), [("BAD_ACTION", "w.interact.on_click.open_as")])

    def test_model_must_exist_and_be_readable(self):
        self.assertEqual(codes(click_patch={"model": "no.such"}), [("UNKNOWN_MODEL", "w.interact.on_click.model")])
        self.assertEqual(codes(click_patch={"model": "secret.model"}), [("NO_ACCESS", "w.interact.on_click.model")])
        raw = deepcopy(sample_spec())
        del raw["widgets"][0]["interact"]["on_click"]["model"]
        errors = Validator(catalog()).validate_widget(Spec.from_raw(raw).widgets[0], "w").errors
        self.assertEqual([e.code for e in errors], ["BAD_SPEC"])

    def test_columns_must_exist_and_be_showable(self):
        self.assertEqual(codes(click_patch={"columns": ["nmae"]}), [("UNKNOWN_FIELD", "w.interact.on_click.columns")])
        self.assertEqual(codes(click_patch={"columns": ["order_line"]}), [("DRILL_BAD_COLUMN", "w.interact.on_click.columns")])
        self.assertEqual(codes(click_patch={"columns": []}), [("BAD_SPEC", "w.interact.on_click.columns")])
        self.assertEqual(codes(click_patch={"columns": ["name"] * 2}), [("BAD_SPEC", "w.interact.on_click.columns")])

    def test_map_fields_must_exist_on_both_sides(self):
        self.assertEqual(codes(click_patch={"map": {"date": "date_ordr"}}), [("UNKNOWN_FIELD", "w.interact.on_click.map")])
        self.assertEqual(codes(click_patch={"map": {"dat": "date_order"}})[0][0], "UNKNOWN_FIELD")

    def test_unmapped_dimension_or_domain_field_is_found_at_save_time(self):
        # the date axis has no counterpart without the map entry: sale.order has no 'date'
        self.assertEqual(codes(click_patch={"map": {}}), [("DRILL_UNMAPPED", "w.interact.on_click.map")])
        # a domain field with no counterpart
        data = deepcopy(sample_spec()["widgets"][0]["data"])
        data["domain"] = [["state", "=", "sale"], ["price_subtotal", ">", 0]]
        self.assertEqual(codes({"data": data}), [("DRILL_UNMAPPED", "w.interact.on_click.map")])


@tagged("levelix_board", "-at_install", "post_install")
class TestDrillTranslation(BaseCase):
    MAP = {"date": "date_order"}

    def test_names_follow_the_map_and_keep_date_parts(self):
        self.assertEqual(drill.translate_name("date", self.MAP, SALE_ORDER), "date_order")
        self.assertEqual(drill.translate_name("date.day_of_week", self.MAP, SALE_ORDER), "date_order.day_of_week")
        self.assertEqual(drill.translate_name("partner_id", self.MAP, SALE_ORDER), "partner_id")  # same name exists
        self.assertIsNone(drill.translate_name("product_id", self.MAP, SALE_ORDER))

    def test_domain_is_renamed_and_logic_is_kept(self):
        domain = ["|", ["date", ">=", "2026-01-01 00:00:00"], ("state", "=", "sale")]
        out = drill.translate_domain(domain, self.MAP, SALE_ORDER)
        self.assertEqual(out, ["|", ["date_order", ">=", "2026-01-01 00:00:00"], ["state", "=", "sale"]])

    def test_unmapped_field_raises(self):
        with self.assertRaises(BoardError) as ctx:
            drill.translate_domain([["product_id", "=", 5]], self.MAP, SALE_ORDER)
        self.assertEqual(ctx.exception.code, "DRILL_UNMAPPED")


@tagged("levelix_board", "-at_install", "post_install")
class TestFindGroup(BaseCase):
    DIMS = [DimMeta("date:day", "date", "datetime", "Date", "day"), DimMeta("state", "state", "selection", "Status")]
    GROUPS = [
        {"date:day": "2026-10-06 19:00:00", "state": "sale", "__extra_domain": ["a"]},
        {"date:day": "2026-10-07 19:00:00", "state": False, "__extra_domain": ["b"]},
    ]

    def find(self, ref):
        return drill.find_group(self.GROUPS, self.DIMS, ref, FrameBuilder.dim_ref)

    def test_the_group_is_found_by_its_ref(self):
        self.assertEqual(self.find(["2026-10-06 19:00:00", "sale"])["__extra_domain"], ["a"])
        self.assertEqual(self.find(["2026-10-07 19:00:00", None])["__extra_domain"], ["b"])

    def test_a_made_up_ref_is_refused(self):
        for ref in (["2026-10-06 19:00:00", "draft"], ["2026-10-06 19:00:00"], "sale", None, [["x"], "sale"], [{"a": 1}, "sale"]):
            with self.subTest(ref=ref), self.assertRaises(BoardError) as ctx:
                self.find(ref)
            self.assertEqual(ctx.exception.code, "DRILL_BAD_REF")

    def test_a_widget_without_axes_has_one_group(self):
        group = drill.find_group([{"__extra_domain": []}], [], [], FrameBuilder.dim_ref)
        self.assertEqual(group["__extra_domain"], [])
