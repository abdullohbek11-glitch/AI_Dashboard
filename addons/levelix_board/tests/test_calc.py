"""Calculated measures: the parser reads arithmetic and nothing else."""
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import calc


def run(text, **values):
    return calc.evaluate(calc.parse(text), values)


@tagged("levelix_board")
class TestCalc(BaseCase):
    def test_arithmetic_and_precedence(self):
        self.assertEqual(run("1 + 2 * 3"), 7)
        self.assertEqual(run("(1 + 2) * 3"), 9)
        self.assertEqual(run("m1 - m2", m1=10, m2=4), 6)
        self.assertEqual(run("m1 / m2 * 100", m1=1, m2=4), 25)
        self.assertEqual(run("-m1 + 5", m1=2), 3)
        self.assertEqual(run("- -m1", m1=2), 2)
        self.assertEqual(run("10 - 3 - 2"), 5)  # left to right
        self.assertEqual(run("8 / 4 / 2"), 1)
        self.assertEqual(run("1.5 * 2"), 3)

    def test_no_value_stays_no_value(self):
        self.assertIsNone(run("m1 / m2", m1=1, m2=0))  # division by zero
        self.assertIsNone(run("m1 + 1", m1=None))
        self.assertIsNone(run("m1 + m2", m1=1))  # an unknown id has no value
        self.assertIsNone(run("1 / (m1 - m1)", m1=5))
        self.assertEqual(run("0 / m1", m1=3), 0)

    def test_what_is_used(self):
        tree = calc.parse("(m1 - m2) / m3 * 2")
        self.assertEqual(calc.names(tree), {"m1", "m2", "m3"})
        self.assertEqual(calc.operators(tree), {"-", "/", "*"})
        self.assertEqual(calc.operators(calc.parse("-m1")), {"neg"})

    def test_anything_else_is_rejected(self):
        for text in (
            "", "   ", "1 +", "(1", "1)", "m1 m2", "1 2", "m1 ** 2", "m1 ^ 2", "m1 % 2", "m1; 1", "__import__('os')",
            "open('x')", "m1.real", "m1[0]", "'a'", "m1 if 1 else 2", "lambda: 1", "1e5", "M1", "1 / / 2", "()",
        ):
            with self.subTest(text=text), self.assertRaises(calc.CalcError):
                calc.parse(text)
        with self.assertRaises(calc.CalcError):
            calc.parse("m1 + " * 60 + "1")  # too long
        with self.assertRaises(calc.CalcError):
            calc.parse("(" * 20 + "1" + ")" * 20)  # too deep
        with self.assertRaises(calc.CalcError):
            calc.parse(None)

    def test_the_error_points_at_the_problem(self):
        with self.assertRaises(calc.CalcError) as caught:
            calc.parse("m1 + $")
        self.assertEqual(caught.exception.position, 5)
