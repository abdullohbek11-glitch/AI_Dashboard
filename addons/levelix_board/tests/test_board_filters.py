"""Dashboard filters (pure): periods, the check of a spec's filters, and the conditions a reader's choices become."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import board_filters as bf
from ..lib.errors import BoardError
from ..lib.spec import Widget
from .fixtures import catalog

FRIDAY = date(2026, 11, 6)  # a Friday


def period(applies=None, **extra):
    return dict({"id": "period", "type": "date_range", "label": "Period", "applies_to": {"sale.report": "date"} if applies is None else applies}, **extra)


def codes(errors):
    return sorted({e.code for e in errors})


@tagged("levelix_board")
class TestPeriods(BaseCase):
    def test_presets(self):
        expected = {
            "today": (date(2026, 11, 6), date(2026, 11, 6)),
            "yesterday": (date(2026, 11, 5), date(2026, 11, 5)),
            "this_week": (date(2026, 11, 2), date(2026, 11, 8)),
            "last_week": (date(2026, 10, 26), date(2026, 11, 1)),
            "last_7_days": (date(2026, 10, 31), date(2026, 11, 6)),
            "last_30_days": (date(2026, 10, 8), date(2026, 11, 6)),
            "last_90_days": (date(2026, 8, 9), date(2026, 11, 6)),
            "this_month": (date(2026, 11, 1), date(2026, 11, 30)),
            "last_month": (date(2026, 10, 1), date(2026, 10, 31)),
            "this_quarter": (date(2026, 10, 1), date(2026, 12, 31)),
            "last_quarter": (date(2026, 7, 1), date(2026, 9, 30)),
            "this_year": (date(2026, 1, 1), date(2026, 12, 31)),
            "last_year": (date(2025, 1, 1), date(2025, 12, 31)),
            "all": (None, None),
        }
        for name, bounds in expected.items():
            with self.subTest(name=name):
                self.assertEqual(bf.preset_range(name, FRIDAY), bounds)
        self.assertEqual(set(expected), set(bf.PRESETS))

    def test_the_week_starts_where_the_language_says(self):
        self.assertEqual(bf.preset_range("this_week", FRIDAY, week_start=7), (date(2026, 11, 1), date(2026, 11, 7)))  # Sunday first

    def test_month_ends_and_leap_years(self):
        self.assertEqual(bf.preset_range("this_month", date(2024, 2, 10)), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(bf.preset_range("last_month", date(2024, 3, 31)), (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(bf.preset_range("last_year", date(2025, 3, 1)), (date(2024, 1, 1), date(2024, 12, 31)))
        self.assertEqual(bf.preset_range("last_quarter", date(2026, 1, 15)), (date(2025, 10, 1), date(2025, 12, 31)))

    def test_custom_periods_and_their_errors(self):
        self.assertEqual(bf.period_range({"from": "2026-10-01", "to": "2026-10-31"}, FRIDAY), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(bf.period_range({"from": "2026-10-01"}, FRIDAY), (date(2026, 10, 1), None))
        self.assertEqual(bf.period_range({"to": "2026-10-31"}, FRIDAY), (None, date(2026, 10, 31)))
        self.assertEqual(bf.period_range(None, FRIDAY), (None, None))
        for bad in ("next_year", {"from": "2026-13-01"}, {"from": "yesterday"}, {"from": 5}, {"from": "2026-10-31", "to": "2026-10-01"}, {"start": "2026-10-01"}, 5, ["today"]):
            with self.subTest(bad=bad), self.assertRaises(BoardError):
                bf.period_range(bad, FRIDAY)

    def test_a_period_in_words(self):
        self.assertEqual(bf.describe_period("last_30_days", FRIDAY), "Last 30 days (2026-10-08 – 2026-11-06)")
        self.assertEqual(bf.describe_period("all", FRIDAY), "All time")
        self.assertEqual(bf.describe_period({"from": "2026-10-01", "to": "2026-10-31"}, FRIDAY), "2026-10-01 – 2026-10-31")
        self.assertEqual(bf.describe_period({"from": "2026-10-01"}, FRIDAY), "from 2026-10-01")


@tagged("levelix_board")
class TestCheckingFilters(BaseCase):
    def setUp(self):
        super().setUp()
        self.catalog = catalog()

    def check(self, *filters):
        return bf.check(list(filters), self.catalog)

    def test_good_filters_pass(self):
        errors = self.check(
            period({"sale.report": "date", "sale.order": "date_order"}, default="last_30_days"),
            {"id": "seller", "type": "select", "label": "Salesperson", "applies_to": {"sale.report": "user_id"}},
            {"id": "status", "type": "select", "label": "Status", "applies_to": {"sale.report": "state"}, "default": "sale"},
            {"id": "company", "type": "company", "label": "Company", "applies_to": {"sale.report": "company_id"}},
        )
        self.assertEqual(errors, [])

    def test_what_is_wrong_is_named(self):
        cases = [
            ({"id": "x", "type": "slider", "label": "X", "applies_to": {"sale.report": "date"}}, ["BAD_FILTER"]),
            (period({"sale.report": "state"}), ["BAD_FILTER"]),  # a period needs a date
            (period({"sale.report": "nothing"}), ["UNKNOWN_FIELD"]),
            (period({"no.such": "date"}), ["UNKNOWN_MODEL"]),
            (period({"secret.model": "date"}), ["NO_ACCESS"]),
            (period({}), ["BAD_FILTER"]),
            (period(None, default="soon"), ["BAD_FILTER"]),
            (period(label=""), ["BAD_FILTER"]),
            ({"id": "c", "type": "company", "label": "C", "applies_to": {"sale.report": "partner_id"}}, ["BAD_FILTER"]),  # not a link to companies
            ({"id": "s", "type": "select", "label": "S", "applies_to": {"sale.report": "price_subtotal"}}, ["BAD_FILTER"]),
            ({"id": "s", "type": "select", "label": "S", "applies_to": {"sale.report": "user_id"}, "mystery": 1}, ["UNKNOWN_KEY"]),
            ({"id": "Bad Id", "type": "select", "label": "S", "applies_to": {"sale.report": "user_id"}}, ["BAD_FILTER"]),
            ("nope", ["BAD_FILTER"]),
        ]
        for item, expected in cases:
            with self.subTest(item=item):
                self.assertEqual(codes(self.check(item)), expected)

    def test_ids_are_unique_and_there_are_not_too_many(self):
        self.assertEqual(codes(self.check(period(), period())), ["DUPLICATE_ID"])
        many = [dict(period(), id="f%d" % i) for i in range(bf.MAX_FILTERS + 1)]
        self.assertEqual(codes(bf.check(many, self.catalog)), ["BAD_FILTER"])
        self.assertEqual(codes(bf.check("nope", self.catalog)), ["BAD_FILTER"])


@tagged("levelix_board")
class TestResolvingChoices(BaseCase):
    def setUp(self):
        super().setUp()
        self.catalog = catalog()
        self.filters = [
            period({"sale.report": "date", "sale.order": "date_order"}, default="last_7_days"),
            {"id": "seller", "type": "select", "label": "Salesperson", "applies_to": {"sale.report": "user_id"}},
            {"id": "status", "type": "select", "label": "Status", "applies_to": {"sale.report": "state"}},
            {"id": "company", "type": "company", "label": "Company", "applies_to": {"sale.report": "company_id"}},
        ]

    def resolve(self, values, **kw):
        return bf.resolve(self.filters, values, self.catalog, FRIDAY, **kw)

    def test_the_default_applies_until_the_reader_chooses(self):
        leaves, _parsed = self.resolve({})
        self.assertEqual(leaves["sale.report"], [["date", ">=", "2026-10-31"], ["date", "<=", "2026-11-06"]])
        self.assertEqual(leaves["sale.order"], [["date_order", ">=", "2026-10-31"], ["date_order", "<=", "2026-11-06"]])
        leaves, _parsed = self.resolve({"period": "this_month"})
        self.assertEqual(leaves["sale.report"], [["date", ">=", "2026-11-01"], ["date", "<=", "2026-11-30"]])

    def test_empty_means_no_filter(self):
        leaves, parsed = self.resolve({"period": "all", "seller": [], "status": None, "company": ""})
        self.assertEqual(leaves, {})
        self.assertEqual(set(parsed.values()), {None})

    def test_choices_become_conditions_on_the_named_models_only(self):
        leaves, _parsed = self.resolve({"period": "all", "seller": [7, 9], "status": "sale", "company": [1]})
        self.assertEqual(leaves, {"sale.report": [["user_id", "in", [7, 9]], ["state", "in", ["sale"]], ["company_id", "in", [1]]]})
        self.assertNotIn("sale.order", leaves)  # the period was "all"; a model with no condition gets no entry

    def test_a_choice_must_be_a_real_value(self):
        with self.assertRaises(BoardError) as caught:
            self.resolve({"status": "frozen"})
        self.assertIn("is not a value of", caught.exception.detail)
        for bad in ({"nothing": 1}, {"seller": {"a": 1}}, {"seller": [[1]]}, {"seller": True}, {"company": ["x"]}, {"period": "someday"}):
            with self.subTest(bad=bad), self.assertRaises(BoardError):
                self.resolve(bad)
        with self.assertRaises(BoardError):
            self.resolve({"seller": list(range(bf.MAX_CHOICES + 1))})

    def test_a_company_the_reader_does_not_work_in_is_refused(self):
        self.resolve({"company": [1, 2]}, allowed_companies=[1, 2, 3])
        with self.assertRaises(BoardError) as caught:
            self.resolve({"company": [1, 4]}, allowed_companies=[1, 2, 3])
        self.assertEqual(caught.exception.code, "NO_ACCESS")


BASIS = {"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": "untaxed",
         "applies_to": {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_total"}}}


def money_widget(*measures, source="sale.report"):
    return Widget.from_raw({"id": "w1", "type": "table", "data": {"source": source, "dimensions": [{"field": "product_id"}], "measures": list(measures)}}, "widgets[0]")


@tagged("levelix_board")
class TestAmountsSwitch(BaseCase):
    def setUp(self):
        super().setUp()
        self.catalog = catalog()

    def test_a_good_amounts_filter_passes(self):
        self.assertEqual(bf.check([BASIS], self.catalog), [])
        self.assertEqual(bf.check([dict(BASIS, default="taxed")], self.catalog), [])
        self.assertEqual(bf.check([{k: v for k, v in BASIS.items() if k != "default"}], self.catalog), [])

    def test_what_is_wrong_with_it_is_named(self):
        def with_pair(pair, **extra):
            return dict(BASIS, applies_to={"sale.report": pair}, **extra)
        cases = {
            "BAD_FILTER": [with_pair({"untaxed": "price_subtotal"}), with_pair({"untaxed": "price_subtotal", "taxed": "price_subtotal"}),
                           with_pair("price_total"), dict(BASIS, applies_to={}), dict(BASIS, default="both"),
                           with_pair({"untaxed": "price_subtotal", "taxed": "price_total", "extra": "x"})],
            "UNKNOWN_FIELD": [with_pair({"untaxed": "price_subtotal", "taxed": "nothing"}),
                              with_pair({"untaxed": "price_subtotal", "taxed": "price_unit"}),  # a price is averaged, never added up
                              with_pair({"untaxed": "price_subtotal", "taxed": "partner_id"}),
                              with_pair({"untaxed": "price_subtotal", "taxed": "computed_total"})],
            "UNKNOWN_MODEL": [dict(BASIS, applies_to={"no.such": {"untaxed": "a", "taxed": "b"}})],
            "NO_ACCESS": [dict(BASIS, applies_to={"secret.model": {"untaxed": "a", "taxed": "b"}})],
        }
        for code, items in cases.items():
            for item in items:
                with self.subTest(code=code, item=item):
                    self.assertIn(code, codes(bf.check([item], self.catalog)))
        self.assertIn("BAD_FILTER", codes(bf.check([BASIS, dict(BASIS, id="again")], self.catalog)))  # one switch per dashboard

    def test_the_choice_decides_which_field_is_read_instead(self):
        _leaves, parsed = bf.resolve([BASIS], {}, self.catalog, FRIDAY)
        self.assertEqual(parsed["amounts"], ("basis", "untaxed"))
        self.assertEqual(bf.swaps([BASIS], parsed), {"sale.report": {"price_total": "price_subtotal"}})
        for value, expected in (("taxed", {"price_subtotal": "price_total"}), ("untaxed", {"price_total": "price_subtotal"}), (None, {"price_total": "price_subtotal"})):
            with self.subTest(value=value):
                leaves, parsed = bf.resolve([BASIS], {"amounts": value}, self.catalog, FRIDAY)
                self.assertEqual(leaves, {})  # a switch, not a condition
                self.assertEqual(bf.swaps([BASIS], parsed), {"sale.report": expected})
        _leaves, parsed = bf.resolve([dict(BASIS, default="taxed")], {}, self.catalog, FRIDAY)
        self.assertEqual(parsed["amounts"], ("basis", "taxed"))
        for bad in ("both", "Taxed", 1, ["taxed"], True):
            with self.subTest(bad=bad), self.assertRaises(BoardError):
                bf.resolve([BASIS], {"amounts": bad}, self.catalog, FRIDAY)

    def test_only_money_measures_that_follow_the_switch_are_changed(self):
        revenue = {"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}
        orders = {"id": "m2", "agg": "count"}
        pinned = {"id": "m3", "field": "price_subtotal", "agg": "sum", "fixed": True}
        margin = {"id": "m4", "calc": "m1 - m2"}
        widget = money_widget(revenue, orders, pinned, margin)
        taxed = bf.swap_measures(widget, {"price_subtotal": "price_total"})
        self.assertEqual([m.field for m in taxed.data.measures], ["price_total", None, "price_subtotal", None])  # a pinned measure keeps its own field
        self.assertEqual(taxed.data.measures[0].label, "Revenue")
        self.assertIs(bf.swap_measures(widget, {"price_unit": "price_total"}), widget)  # nothing to change: the same widget
        self.assertIs(bf.swap_measures(widget, {}), widget)
        other = money_widget(revenue, source="res.partner")
        self.assertTrue(bf.follows_basis(widget, [BASIS]))
        self.assertFalse(bf.follows_basis(other, [BASIS]))  # a model the switch does not name
        self.assertFalse(bf.follows_basis(money_widget(pinned, orders), [BASIS]))
        self.assertEqual(bf.basis_mapping([BASIS], "sale.report", "taxed"), {"price_subtotal": "price_total"})
        self.assertEqual(bf.basis_mapping([BASIS], "res.partner", "taxed"), {})
