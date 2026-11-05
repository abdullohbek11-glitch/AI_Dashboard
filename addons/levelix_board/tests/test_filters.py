from datetime import date, datetime

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import filters

TODAY = date(2026, 11, 5)
TZ = "Asia/Tashkent"  # UTC+5, no DST
NOW = datetime(2026, 11, 5, 10, 0, 0)  # naive UTC


@tagged("levelix_board")
class TestRelativeDates(BaseCase):
    def test_expressions(self):
        cases = {
            "today": date(2026, 11, 5),
            "today -7d": date(2026, 10, 29),
            "today +1w": date(2026, 11, 12),
            "today =1d": date(2026, 11, 1),
            "today =1d -1m": date(2026, 10, 1),
            "today =1m =1d": date(2026, 1, 1),
            "today -1y": date(2025, 11, 5),
            "  TODAY   -1D ": date(2026, 11, 4),
        }
        for expr, expected in cases.items():
            self.assertEqual(filters.resolve_relative(expr, TODAY), expected, expr)

    def test_month_arithmetic_clamps(self):
        self.assertEqual(filters.resolve_relative("today -1m", date(2026, 3, 31)), date(2026, 2, 28))
        self.assertEqual(filters.resolve_relative("today =31d", date(2026, 2, 10)), date(2026, 2, 28))
        self.assertEqual(filters.resolve_relative("today -1y", date(2024, 2, 29)), date(2023, 2, 28))

    def test_bad_expressions(self):
        for expr in ("yesterday", "today +x", "today =13m", "today =0d", "today =1w", "today 7d", ""):
            with self.assertRaises(ValueError, msg=expr):
                filters.resolve_relative(expr, TODAY)

    def test_today_in_time_zone(self):
        late = datetime(2026, 11, 5, 20, 0, 0)  # 01:00 next day in Tashkent
        self.assertEqual(filters.today_in(TZ, late), date(2026, 11, 6))
        self.assertEqual(filters.today_in("UTC", late), date(2026, 11, 5))

    def test_local_day_boundaries(self):
        self.assertEqual(filters.local_start_utc(date(2026, 11, 6), TZ), "2026-11-05 19:00:00")
        self.assertEqual(filters.local_start_utc(date(2026, 11, 6), "UTC"), "2026-11-06 00:00:00")
        self.assertEqual(filters.local_date_of("2026-11-05 19:00:00", "datetime", TZ), date(2026, 11, 6))
        self.assertEqual(filters.local_date_of("2026-11-05 18:59:59", "datetime", TZ), date(2026, 11, 5))
        self.assertEqual(filters.local_date_of("2026-11-05", "date", TZ), date(2026, 11, 5))

    def test_dst_zone(self):
        # New York leaves DST on 2026-11-01: midnight local is UTC-4 before, UTC-5 after.
        self.assertEqual(filters.local_start_utc(date(2026, 10, 31), "America/New_York"), "2026-10-31 04:00:00")
        self.assertEqual(filters.local_start_utc(date(2026, 11, 2), "America/New_York"), "2026-11-02 05:00:00")

    def test_buckets(self):
        d = date(2026, 11, 5)  # Thursday
        self.assertEqual(filters.start_of(d, "day"), d)
        self.assertEqual(filters.start_of(d, "week", 1), date(2026, 11, 2))
        self.assertEqual(filters.start_of(d, "week", 7), date(2026, 11, 1))
        self.assertEqual(filters.start_of(d, "month"), date(2026, 11, 1))
        self.assertEqual(filters.start_of(d, "quarter"), date(2026, 10, 1))
        self.assertEqual(filters.start_of(d, "year"), date(2026, 1, 1))
        self.assertEqual(filters.next_bucket(date(2026, 12, 1), "month"), date(2027, 1, 1))
        self.assertEqual(filters.next_bucket(date(2026, 10, 1), "quarter"), date(2027, 1, 1))


@tagged("levelix_board")
class TestResolveDomain(BaseCase):
    types = {"date_order": "datetime", "invoice_date": "date", "state": "selection"}

    def resolve(self, domain):
        return filters.resolve_domain(domain, self.types.get, TZ, NOW)

    def test_datetime_comparisons_use_local_days(self):
        self.assertEqual(self.resolve([["date_order", ">=", "today -29d"]]),
                         [["date_order", ">=", "2026-10-06 19:00:00"]])
        # "up to today" must include today: strictly before tomorrow's local midnight
        self.assertEqual(self.resolve([["date_order", "<=", "today"]]),
                         [["date_order", "<", "2026-11-05 19:00:00"]])
        self.assertEqual(self.resolve([["date_order", ">", "today"]]),
                         [["date_order", ">=", "2026-11-05 19:00:00"]])
        self.assertEqual(self.resolve([["date_order", "<", "today"]]),
                         [["date_order", "<", "2026-11-04 19:00:00"]])

    def test_equal_becomes_a_range(self):
        self.assertEqual(self.resolve([["date_order", "=", "2026-11-05"]]), [
            "&", ["date_order", ">=", "2026-11-04 19:00:00"], ["date_order", "<", "2026-11-05 19:00:00"]])
        self.assertEqual(self.resolve([["date_order", "!=", "2026-11-05"]]), [
            "|", ["date_order", "<", "2026-11-04 19:00:00"], ["date_order", ">=", "2026-11-05 19:00:00"]])

    def test_date_field_stays_a_date(self):
        self.assertEqual(self.resolve([["invoice_date", "<=", "today =1d"]]), [["invoice_date", "<=", "2026-11-01"]])

    def test_exact_datetimes_and_other_fields_are_untouched(self):
        domain = [["date_order", ">=", "2026-11-01 08:30:00"], ["state", "=", "sale"], ["x.y", "=", "today"]]
        self.assertEqual(self.resolve(domain), [list(leaf) for leaf in domain])

    def test_lists_and_logic_operators(self):
        out = self.resolve(["|", ["invoice_date", "in", ["today", "2026-01-01"]], ["state", "=", "draft"]])
        self.assertEqual(out[0], "|")
        self.assertEqual(out[1], ["invoice_date", "in", ["2026-11-05", "2026-01-01"]])

    def test_input_is_not_modified(self):
        domain = [["date_order", ">=", "today"]]
        self.resolve(domain)
        self.assertEqual(domain, [["date_order", ">=", "today"]])

    def test_check_date_value(self):
        filters.check_date_value("today -7d")
        filters.check_date_value("2026-02-28")
        filters.check_date_value("2026-02-28 10:00:00")  # not a day-only string: left alone
        for bad in ("today -7x", "2026-02-30"):
            with self.assertRaises(ValueError, msg=bad):
                filters.check_date_value(bad)


@tagged("levelix_board")
class TestDateBounds(BaseCase):
    def bounds(self, domain):
        return filters.date_bounds(domain, "date", "datetime", TZ)

    def test_range(self):
        domain = [["date", ">=", "2026-10-06 19:00:00"], ["date", "<", "2026-11-05 19:00:00"]]
        self.assertEqual(self.bounds(domain), (date(2026, 10, 7), date(2026, 11, 6)))

    def test_open_ended(self):
        self.assertEqual(self.bounds([["date", ">=", "2026-10-06 19:00:00"]]), (date(2026, 10, 7), None))
        self.assertEqual(self.bounds([["date", "<", "2026-10-06 19:00:00"]]), (None, date(2026, 10, 7)))
        self.assertEqual(self.bounds([]), (None, None))

    def test_alternatives_do_not_bound(self):
        domain = ["|", ["date", ">=", "2026-10-06 19:00:00"], ["state", "=", "x"]]
        self.assertEqual(self.bounds(domain), (None, None))

    def test_ands_are_followed(self):
        domain = ["&", ["date", ">=", "2026-10-06 19:00:00"], ["date", "<", "2026-11-05 19:00:00"]]
        self.assertEqual(self.bounds(domain), (date(2026, 10, 7), date(2026, 11, 6)))
