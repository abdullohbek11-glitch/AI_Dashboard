"""What changed between two versions of a spec (pure)."""
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import versions


def widget(wid, title="", **extra):
    return dict({"id": wid, "type": "kpi", "title": title, "data": {"source": "sale.report", "measures": [{"id": "m1", "agg": "count"}]}}, **extra)


@tagged("levelix_board")
class TestVersionSummary(BaseCase):
    def test_the_first_version_adds_everything(self):
        out = versions.summarize(None, {"v": 1, "widgets": [widget("w1", "Revenue"), widget("w2")]})
        self.assertEqual((out["added"], out["removed"], out["changed"], out["moved"]), (["Revenue", "w2"], [], [], []))

    def test_added_removed_changed_and_moved(self):
        old = {"v": 1, "title": "A", "widgets": [widget("w1", "One", grid={"x": 0, "y": 0, "w": 6, "h": 4}), widget("w2", "Two"), widget("w3", "Three")]}
        new = {"v": 1, "title": "A", "widgets": [
            widget("w1", "One", grid={"x": 6, "y": 0, "w": 6, "h": 4}),  # only moved
            dict(widget("w2", "Two"), type="bar"),  # what it shows changed
            widget("w4", "Four")]}  # w3 is gone, w4 is new
        out = versions.summarize(old, new)
        self.assertEqual((out["added"], out["removed"], out["changed"], out["moved"], out["other"]), (["Four"], ["Three"], ["Two"], ["One"], []))

    def test_a_widget_that_only_gained_a_place_counts_as_moved_not_changed(self):
        out = versions.summarize({"widgets": [widget("w1", "One")]}, {"widgets": [widget("w1", "One", grid={"x": 0, "y": 0, "w": 6, "h": 4})]})
        self.assertEqual((out["changed"], out["moved"]), ([], ["One"]))

    def test_title_filters_and_notes(self):
        old = {"title": "A", "widgets": [], "filters": [], "assumptions": ["x"]}
        new = {"title": "B", "widgets": [], "filters": [{"id": "p"}], "assumptions": ["y"]}
        self.assertEqual(versions.summarize(old, new)["other"], ["title", "filters", "notes"])
        self.assertEqual(versions.summarize(old, old), {"added": [], "removed": [], "changed": [], "moved": [], "other": []})

    def test_odd_input_does_not_break_it(self):
        self.assertEqual(versions.summarize({"widgets": ["x", {"no": "id"}]}, {"widgets": None or []})["removed"], [])
        self.assertEqual(versions.summarize(None, None)["added"], [])
