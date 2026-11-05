import copy

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.errors import BoardError
from ..lib.spec import MAX_SPEC_BYTES, Dimension, Spec, migrate
from .fixtures import sample_spec


@tagged("levelix_board")
class TestSpec(BaseCase):
    def code(self, raw):
        with self.assertRaises(BoardError) as ctx:
            Spec.from_raw(raw)
        return ctx.exception

    def test_round_trip_is_stable(self):
        spec = Spec.from_raw(sample_spec())
        again = Spec.from_raw(spec.to_raw())
        self.assertEqual(spec, again)
        self.assertEqual(spec.to_raw(), again.to_raw())

    def test_round_trip_keeps_content(self):
        raw = sample_spec()
        self.assertEqual(Spec.from_raw(raw).to_raw(), raw)

    def test_dimension_short_form(self):
        self.assertEqual(Dimension.from_raw("date:day", "p"), Dimension("date", "day"))
        self.assertEqual(Dimension("date", "day").key, "date:day")
        self.assertEqual(Dimension("product_id").key, "product_id")

    def test_unknown_keys_are_rejected_with_path(self):
        raw = sample_spec()
        raw["widgets"][0]["data"]["domian"] = []
        error = self.code(raw)
        self.assertEqual(error.code, "UNKNOWN_KEY")
        self.assertEqual(error.path, "widgets[0].data")
        self.assertIn("domian", error.detail)

    def test_wrong_types(self):
        for mutate, path in (
            (lambda r: r["widgets"][0]["data"].update(domain="x"), "widgets[0].data.domain"),
            (lambda r: r["widgets"][0]["data"].update(limit="3"), "widgets[0].data.limit"),
            (lambda r: r["widgets"][0]["data"]["measures"].append("m"), "widgets[0].data.measures[1]"),
            (lambda r: r["widgets"][0].update(id="W 1"), "widgets[0]"),
            (lambda r: r.update(widgets="x"), "widgets"),
        ):
            raw = copy.deepcopy(sample_spec())
            mutate(raw)
            error = self.code(raw)
            self.assertEqual(error.code, "BAD_SPEC", error.detail)
            self.assertEqual(error.path, path)

    def test_boolean_is_not_a_number(self):
        raw = sample_spec()
        raw["widgets"][0]["data"]["limit"] = True
        self.assertEqual(self.code(raw).code, "BAD_SPEC")

    def test_measure_needs_field_or_count(self):
        raw = sample_spec()
        raw["widgets"][0]["data"]["measures"] = [{"id": "m1"}]
        self.assertEqual(self.code(raw).code, "BAD_SPEC")
        raw["widgets"][0]["data"]["measures"] = [{"id": "m1", "agg": "count"}]
        self.assertTrue(Spec.from_raw(raw).widgets[0].data.measures[0].is_count)
        raw["widgets"][0]["data"]["measures"] = [{"id": "m1", "field": "__count"}]
        self.assertTrue(Spec.from_raw(raw).widgets[0].data.measures[0].is_count)

    def test_version(self):
        raw = sample_spec()
        del raw["v"]
        self.assertEqual(self.code(raw).code, "BAD_SPEC")
        raw["v"] = 99
        self.assertEqual(self.code(raw).code, "UNSUPPORTED_VERSION")
        raw["v"] = 0
        self.assertEqual(self.code(raw).code, "BAD_SPEC")

    def test_migrate_does_not_mutate(self):
        raw = sample_spec()
        before = copy.deepcopy(raw)
        migrate(raw)
        self.assertEqual(raw, before)

    def test_not_a_dict(self):
        self.assertEqual(self.code([]).code, "BAD_SPEC")
        self.assertEqual(self.code("x").code, "BAD_SPEC")

    def test_size(self):
        spec = Spec.from_raw(sample_spec())
        self.assertLess(spec.size_bytes(), MAX_SPEC_BYTES)
