"""Which hint fits a question (pure)."""
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import hints, json_help

ROWS = [
    (10, "sales, revenue, orders, sotuv, savdo, продажи", {"model": "sale.report"}),
    (20, "invoice, invoices, faktura, счет", {"model": "account.invoice.report"}),
    (30, "purchase, vendor, xarid", {"model": "purchase.report"}),
]


def models(query):
    return [h["model"] for h in hints.match(ROWS, query)]


@tagged("levelix_ai_board")
class TestHintMatching(BaseCase):
    def test_english_and_other_languages(self):
        self.assertEqual(models("show me this month's sales"), ["sale.report"])
        self.assertEqual(models("shu oy sotuvni kunlar bo'yicha"), ["sale.report"])  # "sotuvni" holds "sotuv"
        self.assertEqual(models("продажи за месяц"), ["sale.report"])

    def test_the_best_match_comes_first(self):
        self.assertEqual(models("unpaid invoices and sales orders")[0], "sale.report")  # sales, orders: two words against one
        self.assertEqual(models("invoice invoices faktura"), ["account.invoice.report"])

    def test_nothing_matches_nothing(self):
        for query in ("weather in Tashkent", "", None, "   "):
            self.assertEqual(models(query), [], query)

    def test_a_short_word_does_not_match_by_accident(self):
        self.assertEqual(models("the or in"), [])  # words under four letters are not matched inside keywords

    def test_at_most_five(self):
        many = [(i, "common", {"model": "m%d" % i}) for i in range(9)]
        self.assertEqual(len(hints.match(many, "common")), 5)

    def test_keywords_split(self):
        self.assertEqual(hints.keywords("A, b ;c\n d,, "), ["a", "b", "c", "d"])


@tagged("levelix_ai_board")
class TestJsonHelp(BaseCase):
    BROKEN = '{"v":1,"widgets":[{"id":"w1","interact":{"on_click":{"action":"drill"}},{"id":"w2","type":"bar"}]}'

    def explain(self, text):
        import json
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            return json_help.explain(text, error)
        self.fail("the text is valid")

    def test_a_widget_left_open_is_named(self):
        message = self.explain(self.BROKEN)
        self.assertIn("inside widgets[0]", message)
        self.assertIn('}},<<HERE>>{"id":"w2"', message)
        self.assertIn("so it must be closed first: insert a } before the comma that comes just before <<HERE>>", message)

    def test_the_path_follows_objects_and_arrays(self):
        text = '{"widgets":[{"id":"a"},{"id":"b","data":{"measures":[{"id":"m1"} {"id":"m2"}]}}]}'
        self.assertIn("inside widgets[1].data.measures[0]", self.explain(text))

    def test_a_missing_closer_before_the_next_one_says_which_and_where(self):
        message = self.explain('{"widgets":[{"id":"a","interact":{"on_click":{"x":1}}]}')
        self.assertIn("The object widgets[0] is still open here: insert a } at <<HERE>>, before the ].", message)
        message = self.explain('{"a":[1,2}')
        self.assertIn("The list a is still open here: insert a ] at <<HERE>>, before the }.", message)

    def test_other_slips_and_non_json_errors(self):
        self.assertIn("inside the top level", self.explain('{"a":1,}'))
        self.assertIn("Unterminated string", self.explain('{"a":"x'))
        self.assertEqual(json_help.explain("x", ValueError("odd")), "odd")


@tagged("levelix_ai_board")
class TestJsonRepair(BaseCase):
    def test_a_missing_closer_is_put_back(self):
        # a widget left open before the next one, and one left open before the list ends: the two slips seen in real answers
        self.assertEqual(json_help.repair('{"w":[{"id":1,"i":{"a":{"x":1}},{"id":2}]}'), ({"w": [{"id": 1, "i": {"a": {"x": 1}}}, {"id": 2}]}, 1))
        self.assertEqual(json_help.repair('{"w":[{"id":1,"i":{"a":{"x":1}}]}'), ({"w": [{"id": 1, "i": {"a": {"x": 1}}}]}, 1))
        self.assertEqual(json_help.repair('{"w":[{"id":1}'), ({"w": [{"id": 1}]}, 2))  # the text just ends
        self.assertEqual(json_help.repair('{"a":1}'), ({"a": 1}, 0))

    def test_nothing_else_is_guessed(self):
        for broken in ('{"a":1,}', '{"a":"x', '{"a":1}}', '{"a" 1}', 'nonsense', '{"a":[1 2]}'):
            self.assertIsNone(json_help.repair(broken), broken)
