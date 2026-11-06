"""The patch language (pure) and the "unsure" options that carry a ready patch."""
import copy

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.errors import BoardError
from ..lib.patch import MAX_OPS, apply_patch
from ..lib.spec import Spec
from ..lib.validator import Validator
from . import fixtures
from .fixtures import sample_spec


def code(patch, spec=None):
    with BaseCase().assertRaises(BoardError) as ctx:
        apply_patch(spec or sample_spec(), patch)
    return ctx.exception.code


@tagged("levelix_board")
class TestPatch(BaseCase):
    def test_replace_add_remove(self):
        spec = sample_spec()
        out = apply_patch(spec, [
            {"op": "replace", "path": "/widgets/1/data/limit", "value": 5},
            {"op": "add", "path": "/title", "value": "New title"},
            {"op": "add", "path": "/widgets/-", "value": {"id": "w3", "type": "kpi", "data": {"source": "sale.report", "measures": []}}},
            {"op": "remove", "path": "/widgets/0/view"},
        ])
        self.assertEqual(out["widgets"][1]["data"]["limit"], 5)
        self.assertEqual(out["title"], "New title")
        self.assertEqual([w["id"] for w in out["widgets"]], ["w1", "w2", "w3"])
        self.assertNotIn("view", out["widgets"][0])

    def test_the_input_is_never_modified(self):
        spec = sample_spec()
        before = copy.deepcopy(spec)
        apply_patch(spec, [{"op": "replace", "path": "/widgets/1/data/limit", "value": 3}])
        self.assertEqual(spec, before)

    def test_widget_ids_are_kept(self):
        self.assertEqual(code([{"op": "replace", "path": "/widgets/0/id", "value": "other"}]), "BAD_PATCH")
        self.assertEqual(code([{"op": "remove", "path": "/widgets/0/id"}]), "BAD_PATCH")
        self.assertEqual(code([{"op": "replace", "path": "/widgets/0", "value": {"id": "w9", "type": "kpi", "data": {}}}]), "BAD_PATCH")
        ok = apply_patch(sample_spec(), [{"op": "replace", "path": "/widgets/0", "value": {"id": "w1", "type": "kpi", "data": {}}}])
        self.assertEqual(ok["widgets"][0]["type"], "kpi")
        self.assertEqual(code([{"op": "add", "path": "/widgets/-", "value": {"type": "kpi"}}]), "BAD_PATCH")  # a new widget needs an id

    def test_only_the_dashboard_content_can_be_changed(self):
        for path in ("/v", "/uncertain", "/uncertain/0", "/", "", "widgets/0", "/widgets", "/nope"):
            with self.subTest(path=path):
                self.assertEqual(code([{"op": "remove", "path": path}]), "BAD_PATCH")
        self.assertEqual(code([{"op": "replace", "path": "/widgets", "value": []}]), "BAD_PATCH")
        self.assertEqual(code([{"op": "add", "path": 5, "value": 1}]), "BAD_PATCH")

    def test_places_that_do_not_exist_are_refused(self):
        for step in (
            {"op": "replace", "path": "/widgets/9/data/limit", "value": 1},
            {"op": "remove", "path": "/widgets/9"},
            {"op": "replace", "path": "/widgets/0/data/nothing", "value": 1},
            {"op": "remove", "path": "/widgets/0/data/nothing"},
            {"op": "add", "path": "/widgets/x/title", "value": "t"},
            {"op": "add", "path": "/widgets/0/title/deeper/still", "value": 1},
        ):
            with self.subTest(step=step):
                self.assertEqual(code([step]), "BAD_PATCH")

    def test_the_shape_of_a_patch(self):
        for patch in ([], None, "x", {"op": "add"}, [5], [{"op": "move", "path": "/title", "value": 1}],
                      [{"op": "add", "path": "/title"}], [{"op": "add", "path": "/title", "value": 1, "extra": 1}]):
            with self.subTest(patch=patch):
                self.assertEqual(code(patch), "BAD_PATCH")
        self.assertEqual(code([{"op": "add", "path": "/title", "value": "t"}] * (MAX_OPS + 1)), "BAD_PATCH")

    def test_escaped_keys(self):
        out = apply_patch({"v": 1, "widgets": [], "filters": [{"a/b": 1}]}, [{"op": "replace", "path": "/filters/0/a~1b", "value": 2}])
        self.assertEqual(out["filters"][0], {"a/b": 2})


@tagged("levelix_board")
class TestUncertainOptions(BaseCase):
    def setUp(self):
        super().setUp()
        self.validator = Validator(fixtures.catalog())

    def codes(self, **extra):
        raw = sample_spec()
        raw.update(extra)
        return [e.code for e in self.validator.validate_spec(Spec.from_raw(raw)).errors]

    GOOD = {"text": "Maybe you meant the quantity.", "patch": [{"op": "replace", "path": "/widgets/0/data/measures/0/field", "value": "product_uom_qty"}]}

    def test_a_good_option_passes(self):
        self.assertEqual(self.codes(uncertain=[self.GOOD], assumptions=["Sales = confirmed orders"]), [])

    def test_an_option_that_would_break_the_dashboard_is_refused_up_front(self):
        broken = {"text": "Use a field that does not exist.", "patch": [{"op": "replace", "path": "/widgets/0/data/measures/0/field", "value": "nope"}]}
        self.assertEqual(self.codes(uncertain=[broken]), ["UNCERTAIN_PATCH_INVALID"])

    def test_a_bad_patch_in_an_option_is_located(self):
        wrong = {"text": "x", "patch": [{"op": "replace", "path": "/widgets/0/id", "value": "z"}]}
        raw = sample_spec()
        raw["uncertain"] = [wrong]
        errors = self.validator.validate_spec(Spec.from_raw(raw)).errors
        self.assertEqual([(e.code, e.path) for e in errors], [("BAD_PATCH", "uncertain[0].patch")])

    def test_the_shape_of_options_and_assumptions(self):
        self.assertEqual(self.codes(uncertain=[{"text": "x" * 161, "patch": self.GOOD["patch"]}]), ["BAD_SPEC"])
        self.assertEqual(self.codes(uncertain=[{"patch": self.GOOD["patch"]}]), ["BAD_SPEC"])
        self.assertEqual(self.codes(uncertain=[{"text": "x", "patch": "no"}]), ["BAD_SPEC"])
        self.assertEqual(self.codes(uncertain=[{"text": "x", "patch": [], "extra": 1}]), ["BAD_SPEC"])
        self.assertEqual(self.codes(uncertain=[self.GOOD] * 6), ["BAD_SPEC"])
        self.assertEqual(self.codes(assumptions=[1]), ["BAD_SPEC"])
        self.assertEqual(self.codes(assumptions=["x" * 201]), ["BAD_SPEC"])
        self.assertEqual(self.codes(assumptions=["ok"] * 11), ["BAD_SPEC"])
