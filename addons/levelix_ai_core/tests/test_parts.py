"""Date parts and the order of a grouped question (pure)."""
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import parts


@tagged("levelix_ai_core")
class TestDateParts(BaseCase):
    def test_weekdays_read_monday_first(self):
        self.assertEqual([parts.label(v, "day_of_week") for v in (1, 2, 3, 4, 5, 6, 0)], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        self.assertEqual(sorted([0, 1, 6, 3], key=parts.monday_first), [1, 3, 6, 0])  # Odoo counts Sunday as 0
        self.assertEqual(parts.label(1.0, "day_of_week", day_names=["Dush", "Sesh"] + ["x"] * 5), "Dush")  # floats and the reader's names

    def test_other_parts(self):
        self.assertEqual(parts.label(15.0, "hour_number"), "15:00")
        self.assertEqual(parts.label(7, "hour_number"), "07:00")
        self.assertEqual(parts.label(3, "month_number"), "Mar")
        self.assertEqual(parts.label(3, "month_number", month_names=["y", "f", "mart"] + ["x"] * 9), "mart")
        self.assertEqual(parts.label(2, "quarter_number"), "Q2")
        self.assertEqual(parts.label(18, "iso_week_number"), "18")
        self.assertEqual(parts.label(None, "hour_number"), "Not set")
        self.assertEqual(parts.label("odd", "hour_number"), "odd")


@tagged("levelix_ai_core")
class TestOrder(BaseCase):
    GROUP = ["date:day"]
    AGG = ["price_subtotal:sum", "__count"]

    def order(self, text, groupby=None, aggregates=None):
        return parts.normalise_order(text, self.GROUP if groupby is None else groupby, self.AGG if aggregates is None else aggregates)

    def test_what_is_right_is_kept(self):
        self.assertEqual(self.order("price_subtotal:sum desc"), "price_subtotal:sum desc")
        self.assertEqual(self.order("date:day asc"), "date:day asc")
        self.assertEqual(self.order("__count desc"), "__count desc")
        self.assertEqual(self.order("date:day"), "date:day asc")  # a missing direction is ascending
        self.assertEqual(self.order("price_subtotal:sum desc, date:day asc"), "price_subtotal:sum desc, date:day asc")
        self.assertIsNone(self.order(None))
        self.assertIsNone(self.order(""))

    def test_the_usual_slips_are_understood(self):
        self.assertEqual(self.order("date:asc"), "date:day asc")  # the case that cost a step in a real chat
        self.assertEqual(self.order("date desc"), "date:day desc")
        self.assertEqual(self.order("price_subtotal desc"), "price_subtotal:sum desc")
        self.assertEqual(self.order("price_subtotal:desc"), "price_subtotal:sum desc")
        self.assertEqual(self.order("DATE:DAY ASC".lower()), "date:day asc")

    def test_what_cannot_be_ordered_says_what_can(self):
        for bad in ("m1 desc", "revenue", "date:day sideways", "price_subtotal:sum desc extra", "nothing:asc"):
            with self.subTest(bad=bad), self.assertRaises(parts.OrderError) as caught:
                self.order(bad)
            self.assertIn("date:day, price_subtotal:sum, __count", str(caught.exception))
            self.assertIn("asc or desc", str(caught.exception))
        with self.assertRaises(parts.OrderError):
            self.order("price_subtotal desc", aggregates=["price_subtotal:sum", "price_subtotal:avg"])  # two readings: not guessed
