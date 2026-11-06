"""The earlier period a number is compared with: month ends, quarters, years, leap days."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import compare

D = date


@tagged("levelix_board")
class TestCompare(BaseCase):
    def test_a_whole_month_compares_with_the_month_before(self):
        self.assertEqual(compare.shift(D(2026, 11, 1), D(2026, 12, 1), "previous_period"), (D(2026, 10, 1), D(2026, 11, 1)))
        # 31 days against 30: the month, not "the 30 days before"
        self.assertEqual(compare.shift(D(2026, 3, 1), D(2026, 4, 1), "previous_period"), (D(2026, 2, 1), D(2026, 3, 1)))
        self.assertEqual(compare.shift(D(2026, 1, 1), D(2026, 2, 1), "previous_period"), (D(2025, 12, 1), D(2026, 1, 1)))

    def test_quarters_and_years_move_by_their_own_length(self):
        self.assertEqual(compare.shift(D(2026, 7, 1), D(2026, 10, 1), "previous_period"), (D(2026, 4, 1), D(2026, 7, 1)))
        self.assertEqual(compare.shift(D(2026, 1, 1), D(2027, 1, 1), "previous_period"), (D(2025, 1, 1), D(2026, 1, 1)))
        self.assertEqual(compare.shift(D(2026, 1, 1), D(2026, 7, 1), "previous_period"), (D(2025, 7, 1), D(2026, 1, 1)))  # a half year

    def test_any_other_stretch_moves_back_by_its_length(self):
        # the first 6 days of a month (a month to date) against the 6 days before them
        self.assertEqual(compare.shift(D(2026, 11, 1), D(2026, 11, 7), "previous_period"), (D(2026, 10, 26), D(2026, 11, 1)))
        self.assertEqual(compare.shift(D(2026, 11, 8), D(2026, 11, 15), "previous_period"), (D(2026, 11, 1), D(2026, 11, 8)))  # a week
        self.assertEqual(compare.shift(D(2026, 11, 5), D(2026, 11, 6), "previous_period"), (D(2026, 11, 4), D(2026, 11, 5)))  # one day

    def test_the_same_days_a_year_earlier(self):
        self.assertEqual(compare.shift(D(2026, 11, 1), D(2026, 12, 1), "previous_year"), (D(2025, 11, 1), D(2025, 12, 1)))
        # a leap year: 29 February has no twin, it becomes 28 February (and the day after the range follows)
        self.assertEqual(compare.shift(D(2024, 2, 1), D(2024, 3, 1), "previous_year"), (D(2023, 2, 1), D(2023, 3, 1)))
        self.assertEqual(compare.shift(D(2024, 2, 29), D(2024, 3, 1), "previous_year"), (D(2023, 2, 28), D(2023, 3, 1)))
        self.assertEqual(compare.shift(D(2025, 2, 1), D(2025, 3, 1), "previous_year"), (D(2024, 2, 1), D(2024, 3, 1)))  # into a leap year

    def test_nonsense_is_refused(self):
        with self.assertRaises(ValueError):
            compare.shift(D(2026, 11, 1), D(2026, 12, 1), "next_year")
        with self.assertRaises(ValueError):
            compare.shift(D(2026, 11, 5), D(2026, 11, 5), "previous_period")
