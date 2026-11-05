import copy

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.spec import Spec, Widget
from ..lib.validator import Validator, allowed_aggregates
from . import fixtures
from .fixtures import SALE_REPORT, sample_spec


def widget(**data):
    base = {"source": "sale.report", "domain": [["state", "=", "sale"]],
            "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"}]}
    base.update(data)
    wtype = base.pop("_type", "kpi")
    view = base.pop("_view", {})
    return Widget.from_raw({"id": "w1", "type": wtype, "view": view, "data": base}, "widgets[0]")


@tagged("levelix_board")
class TestValidator(BaseCase):
    def setUp(self):
        super().setUp()
        self.validator = Validator(fixtures.catalog())

    def check(self, **data):
        return self.validator.validate_widget(widget(**data), "widgets[0]")

    def codes(self, **data):
        return [e.code for e in self.check(**data).errors]

    def test_sample_spec_is_valid(self):
        result = self.validator.validate_spec(Spec.from_raw(sample_spec()))
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        result.raise_if_invalid()

    # -- models and fields ------------------------------------------------

    def test_unknown_model_and_no_access(self):
        self.assertEqual(self.codes(source="nope.nope"), ["UNKNOWN_MODEL"])
        self.assertEqual(self.codes(source="secret.model"), ["NO_ACCESS"])

    def test_unknown_field_suggests_a_neighbour(self):
        errors = self.check(dimensions=[{"field": "order_date", "granularity": "day"}], _type="bar").errors
        self.assertEqual([e.code for e in errors], ["UNKNOWN_FIELD"])
        self.assertEqual(errors[0].path, "widgets[0].data.dimensions[0]")
        errors = self.check(measures=[{"id": "m1", "field": "price_subtotl", "agg": "sum"}]).errors
        self.assertIn("Did you mean 'price_subtotal'", errors[0].detail)

    def test_measure_must_be_aggregatable(self):
        errors = self.check(measures=[{"id": "m1", "field": "price_unit", "agg": "sum"}]).errors
        self.assertEqual([e.code for e in errors], ["NOT_AGGREGATABLE"])
        self.assertIn("avg", errors[0].detail)
        self.assertEqual(self.codes(measures=[{"id": "m1", "field": "price_unit", "agg": "avg"}]), [])
        self.assertEqual(self.codes(measures=[{"id": "m1", "field": "state", "agg": "sum"}]), ["NOT_AGGREGATABLE"])
        self.assertEqual(self.codes(measures=[{"id": "m1", "field": "name", "agg": "count_distinct"}]), [])
        # no agg given: the field's own aggregator is used; none exists for a char field
        self.assertEqual(self.codes(measures=[{"id": "m1", "field": "name"}]), ["NOT_AGGREGATABLE"])
        self.assertEqual(self.codes(measures=[{"id": "m1", "field": "price_subtotal"}]), [])

    def test_count_needs_no_field(self):
        self.assertEqual(self.codes(measures=[{"id": "m1", "field": "__count"}]), [])
        self.assertEqual(self.codes(measures=[{"id": "m1", "agg": "count"}]), [])

    def test_allowed_aggregates(self):
        self.assertEqual(allowed_aggregates(SALE_REPORT.field("price_subtotal")), ("sum", "avg", "min", "max", "count_distinct"))
        self.assertEqual(allowed_aggregates(SALE_REPORT.field("price_unit")), ("avg", "min", "max", "count_distinct"))
        self.assertEqual(allowed_aggregates(SALE_REPORT.field("is_paid")), ())

    def test_level_mismatch(self):
        for measure in ({"id": "m1", "field": "partner_id.name", "agg": "count_distinct"},
                        {"id": "m1", "field": "computed_total", "agg": "sum"}):
            self.assertEqual(self.codes(measures=[measure]), ["LEVEL_MISMATCH"], measure)
        self.assertEqual(self.codes(dimensions=[{"field": "computed_total"}], _type="bar"), ["LEVEL_MISMATCH"])
        self.assertEqual(self.codes(dimensions=[{"field": "price_subtotal.x"}], _type="bar"), ["LEVEL_MISMATCH"])

    def test_dimension_may_follow_one_link(self):
        self.assertEqual(self.codes(dimensions=[{"field": "partner_id.country_id"}], _type="bar"), [])
        self.assertEqual(self.codes(dimensions=[{"field": "partner_id.nope"}], _type="bar"), ["UNKNOWN_FIELD"])
        self.assertEqual(self.codes(dimensions=[{"field": "partner_id.country_id.name"}], _type="bar"), ["LEVEL_MISMATCH"])

    def test_granularity(self):
        self.assertEqual(self.codes(dimensions=[{"field": "product_id", "granularity": "day"}], _type="bar"), ["BAD_GRANULARITY"])
        self.assertEqual(self.codes(dimensions=[{"field": "date", "granularity": "fortnight"}], _type="bar"), ["BAD_GRANULARITY"])
        self.assertEqual(self.codes(dimensions=[{"field": "date", "granularity": "hour_number"}], _type="bar"), [])
        self.assertEqual(self.codes(dimensions=[{"field": "partner_id.birthday", "granularity": "hour_number"}], _type="bar"), ["BAD_GRANULARITY"])

    # -- domain -------------------------------------------------------------

    def test_domain(self):
        self.assertEqual(self.codes(domain=[["state", "=", "sale"], ["nope", "=", 1]]), ["UNKNOWN_FIELD"])
        self.assertEqual(self.codes(domain=[["state", "===", "sale"]]), ["BAD_OPERATOR"])
        self.assertEqual(self.codes(domain=["|", ["state", "=", "sale"]]), ["INVALID_DOMAIN"])
        self.assertEqual(self.codes(domain=["%", ["state", "=", "sale"]]), ["INVALID_DOMAIN"])
        self.assertEqual(self.codes(domain=[["date", ">=", "today -7x"]]), ["BAD_DATE"])
        self.assertEqual(self.codes(domain=[["state", "=", "sale"], ["date", ">=", "today =1d -1m"]]), [])

    # -- order, limit, others, having ---------------------------------------

    def test_order(self):
        self.assertEqual(self.codes(order={"by": "zzz"}), ["BAD_ORDER"])
        self.assertEqual(self.codes(order={"by": "m1", "dir": "up"}), ["BAD_ORDER"])
        self.assertEqual(self.codes(order={"by": "m1", "dir": "desc"}), [])

    def test_others_rules(self):
        base = dict(dimensions=[{"field": "product_id"}], _type="bar", limit=5, others=True)
        self.assertEqual(self.codes(**base), [])
        avg = dict(base, measures=[{"id": "m1", "field": "price_unit", "agg": "avg"}])
        self.assertEqual(self.codes(**avg), ["NON_ADDITIVE_OTHERS"])
        no_limit = dict(base)
        del no_limit["limit"]
        self.assertEqual(self.codes(**no_limit), ["BAD_SHAPE"])
        two_dims = dict(base, dimensions=[{"field": "product_id"}, {"field": "partner_id"}])
        self.assertEqual(self.codes(**two_dims), ["BAD_SHAPE"])
        with_having = dict(base, having=[["m1", ">", 1]])
        self.assertEqual(self.codes(**with_having), ["BAD_SHAPE"])
        self.assertEqual(self.codes(limit=0), ["BAD_LIMIT"])
        self.assertEqual(self.codes(limit=10_000), ["BAD_LIMIT"])

    def test_having(self):
        self.assertEqual(self.codes(having=[["m1", ">", 100]]), [])
        self.assertEqual(self.codes(having=[["m9", ">", 100]]), ["UNKNOWN_MEASURE"])
        self.assertEqual(self.codes(having=[["m1", "~", 100]]), ["BAD_HAVING"])
        self.assertEqual(self.codes(having=[["m1", ">", "x"]]), ["BAD_HAVING"])
        self.assertEqual(self.codes(having=[["m1", ">"]]), ["BAD_HAVING"])

    # -- shape -----------------------------------------------------------------

    def test_shapes(self):
        date_dim = [{"field": "date", "granularity": "day"}]
        self.assertEqual(self.codes(_type="area"), ["BAD_SHAPE"])  # needs an axis
        self.assertEqual(self.codes(_type="area", dimensions=date_dim), [])
        self.assertEqual(self.codes(_type="area", dimensions=[{"field": "product_id"}]), ["BAD_SHAPE"])  # axis is not a date
        self.assertEqual(self.codes(_type="pie", dimensions=[{"field": "product_id"}], limit=9), ["BAD_SHAPE"])
        self.assertEqual(self.codes(_type="heatmap", dimensions=date_dim), ["BAD_SHAPE"])
        two_dates = [{"field": "date", "granularity": "day"}, {"field": "date", "granularity": "month"}]
        self.assertEqual(self.codes(_type="kpi", dimensions=two_dates), ["BAD_SHAPE"])  # a KPI has at most one (time) dimension
        self.assertEqual(self.codes(_type="kpi", dimensions=[{"field": "product_id"}]), ["BAD_SHAPE"])  # and it must be a date
        self.assertEqual(self.codes(_type="gauge"), ["BAD_SHAPE"])
        self.assertEqual(self.codes(_type="gauge", _view={"target": 100}), [])
        self.assertEqual(self.codes(_type="sankey"), ["UNKNOWN_TYPE"])
        five = [{"id": "m%d" % i, "field": "price_subtotal", "agg": "sum"} for i in range(5)]
        self.assertIn("BAD_SHAPE", self.codes(_type="table", dimensions=[{"field": "product_id"}], measures=five))

    def test_fill_gaps_needs_a_date_axis(self):
        day = [{"field": "date", "granularity": "day"}]
        self.assertEqual(self.codes(_type="area", dimensions=day, fill_gaps=True), [])
        self.assertEqual(self.codes(_type="bar", dimensions=[{"field": "product_id"}], fill_gaps=True), ["BAD_SHAPE"])
        self.assertEqual(self.codes(_type="bar", dimensions=[{"field": "date", "granularity": "hour_number"}], fill_gaps=True), ["BAD_SHAPE"])
        self.assertEqual(self.codes(_type="area", dimensions=day, fill_gaps=True, order={"by": "m1"}), ["BAD_SHAPE"])

    def test_not_available_yet(self):
        self.assertEqual(self.codes(compare="previous_period"), ["UNSUPPORTED"])
        self.assertEqual(self.codes(measures=[{"id": "m1", "calc": "m2 - m3"}]), ["UNSUPPORTED"])

    # -- warnings ------------------------------------------------------------------

    def test_state_filter_warning(self):
        result = self.check(domain=[])
        self.assertEqual(result.errors, [])
        self.assertEqual([w.code for w in result.warnings], ["STATE_FILTER_MISSING"])
        self.assertEqual(self.check(domain=[["state", "!=", "cancel"]]).warnings, [])
        # a model without a status has nothing to warn about
        partner = widget(source="res.partner", domain=[], measures=[{"id": "m1", "agg": "count"}])
        self.assertEqual(self.validator.validate_widget(partner).warnings, [])

    def test_suspicious_date_warning(self):
        result = self.check(_type="bar", dimensions=[{"field": "create_date", "granularity": "month"}])
        self.assertIn("SUSPICIOUS_DATE", [w.code for w in result.warnings])
        result = self.check(domain=[["state", "=", "sale"], ["create_date", ">=", "today"]])
        self.assertIn("SUSPICIOUS_DATE", [w.code for w in result.warnings])
        self.assertEqual(self.check().warnings, [])

    # -- whole spec ----------------------------------------------------------------

    def test_spec_level_limits(self):
        raw = sample_spec()
        raw["widgets"][1]["id"] = "w1"
        result = self.validator.validate_spec(Spec.from_raw(raw))
        self.assertEqual([e.code for e in result.errors], ["DUPLICATE_ID"])
        raw = sample_spec()
        raw["widgets"] = [dict(copy.deepcopy(raw["widgets"][1]), id="w%d" % i) for i in range(31)]
        result = self.validator.validate_spec(Spec.from_raw(raw))
        self.assertEqual([e.code for e in result.errors], ["SPEC_TOO_LARGE"])

    def test_errors_carry_paths_into_the_spec(self):
        raw = sample_spec()
        raw["widgets"][1]["data"]["measures"][0].update(field="price_unit", agg="sum")
        result = self.validator.validate_spec(Spec.from_raw(raw))
        self.assertEqual([(e.code, e.path) for e in result.errors], [("NOT_AGGREGATABLE", "widgets[1].data.measures[0]")])
        with self.assertRaises(Exception) as ctx:
            result.raise_if_invalid()
        self.assertEqual(ctx.exception.errors[0].code, "NOT_AGGREGATABLE")

    # -- values of conditions ------------------------------------------------

    def test_a_selection_value_must_exist(self):
        self.assertEqual(self.codes(domain=[["state", "=", "done"]]), ["UNKNOWN_VALUE"])  # Odoo 19 has no "done"
        self.assertEqual(self.codes(domain=[["state", "in", ["sale", "done"]]]), ["UNKNOWN_VALUE"])
        message = self.check(domain=[["state", "=", "done"]]).errors[0].detail
        self.assertIn("sale (Sales Order)", message)  # the way out is in the message
        for ok in ([["state", "=", "sale"]], [["state", "!=", False]], [["state", "in", ["sale", "cancel"]]]):
            self.assertEqual(self.codes(domain=ok), [], ok)

    def test_in_needs_a_list_and_other_operators_one_value(self):
        self.assertEqual(self.codes(domain=[["state", "in", "sale"]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["state", "not in", "abc"]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["state", "=", ["sale"]]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["partner_id", "in", 5]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["partner_id", "in", [5, 6]]]), [])

    def test_values_must_be_plain(self):
        self.assertEqual(self.codes(domain=[["state", "=", {"a": 1}]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["state", "in", [["sale"]]]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["partner_id", "=", [1, 2]]]), ["BAD_VALUE"])

    def test_numbers_and_booleans_are_checked(self):
        self.assertEqual(self.codes(domain=[["price_subtotal", ">", "lots"]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["price_subtotal", ">", True]]), ["BAD_VALUE"])
        for ok in ([["price_subtotal", ">", 100]], [["price_subtotal", ">", "100.5"]], [["price_subtotal", "=", False]]):
            self.assertEqual(self.codes(domain=ok), [], ok)
        self.assertEqual(self.codes(domain=[["is_paid", "=", "yes"]]), ["BAD_VALUE"])
        self.assertEqual(self.codes(domain=[["is_paid", "=", True]]), [])

    def test_patterns_and_relational_searches_are_left_alone(self):
        for ok in ([["name", "ilike", "S00"]], [["partner_id", "child_of", 3]], [["partner_id", "=", "Ali"]]):
            self.assertEqual(self.codes(domain=ok), [], ok)

    # -- wrongly typed JSON never crashes ------------------------------------------

    def test_order_and_having_with_wrong_types_are_errors_not_crashes(self):
        self.assertEqual(self.codes(order={"by": ["m1"]}), ["BAD_ORDER"])
        self.assertEqual(self.codes(order={"by": 5}), ["BAD_ORDER"])
        self.assertEqual(self.codes(having=[[["m1"], ">", 1]]), ["BAD_HAVING"])
        self.assertEqual(self.codes(having=[["m1", [">"], 1]]), ["BAD_HAVING"])
