"""The "what did I do" block, written by code from the spec and the plan.

It describes the query that really runs (not what an AI claims it did), in plain
sentences without technical names. Only choices a reader may disagree with are
marked as important (status filter, date field and range, currency, cut-off);
the rest is "detail".
"""
from datetime import timedelta

from . import domain as domain_lib
from . import filters
from .catalog import ModelInfo
from .i18n import t
from .planner import Plan
from .spec import Widget

MAX_IMPORTANT = 5

_AGG_WORD = {
    "sum": "total", "avg": "average", "min": "smallest", "max": "largest",
    "count": "count", "count_distinct": "number of different values",
}
_GRANULARITY_WORD = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}
_OPERATOR_WORD = {
    "=": "is", "!=": "is not", "in": "is one of", "not in": "is none of", "<": "is less than",
    "<=": "is at most", ">": "is more than", ">=": "is at least", "like": "contains",
    "ilike": "contains", "not like": "does not contain", "not ilike": "does not contain",
    "=like": "matches", "=ilike": "matches", "child_of": "is under", "parent_of": "is above",
}


def _line(kind: str, text: str, important: bool) -> dict:
    return {"kind": kind, "text": text, "detail": not important}


class ExplainBuilder:
    def __init__(self, resolve_names=None):
        """``resolve_names(model, ids) -> [names]`` turns record ids in filters into names."""
        self.resolve_names = resolve_names

    def build(self, widget: Widget, model: ModelInfo, plan: Plan, currency=None, warnings=()) -> list:
        lines = [_line("source", t("Data source: %s.") % model.label, False)]
        lines += self._measures(plan, currency)
        lines += self._dimensions(plan)
        lines += self._filters(widget, model, plan)
        lines += self._cut(plan)
        for warning in warnings:
            lines.append(_line("warning", warning.text if hasattr(warning, "text") else warning["text"], True))
        return self._cap_important(lines)

    # -- parts --------------------------------------------------------------

    def _measures(self, plan: Plan, currency) -> list:
        lines = []
        for m in plan.measures:
            text = t("Measured: %s (%s)") % (m.label, t(_AGG_WORD.get(m.agg, m.agg)))
            if m.type == "monetary":
                if currency and currency.get("symbol"):
                    text += t(", in %s") % currency["symbol"]
                elif currency and currency.get("mixed"):
                    text += t(", in several currencies")
            lines.append(_line("measure", text + ".", m.type == "monetary"))
        return lines

    def _dimensions(self, plan: Plan) -> list:
        if not plan.dims:
            return []
        parts = []
        for d in plan.dims:
            word = _GRANULARITY_WORD.get(d.granularity)
            parts.append("%s (%s)" % (d.label, t("by %s") % t(word)) if word else d.label)
        return [_line("group", t("Grouped by: %s.") % ", ".join(parts), False)]

    def _filters(self, widget: Widget, model: ModelInfo, plan: Plan) -> list:
        lines, dated = [], set()
        for leaf in domain_lib.leaves(domain_lib.parse(plan.domain)):
            name, op, value = leaf
            info = model.field(name) if "." not in name else None
            if info is not None and info.is_temporal:
                if name not in dated:
                    dated.add(name)
                    line = self._date_line(plan, info)
                    if line:
                        lines.append(line)
                continue
            lines.append(self._leaf_line(model, name, op, value))
        return lines

    def _date_line(self, plan: Plan, info):
        start, end = filters.date_bounds(plan.domain, info.name, info.type, plan.tz)
        if start is None and end is None:
            return None
        last = end - timedelta(days=1) if end else None
        if start and last:
            span = "%s – %s" % (start.isoformat(), last.isoformat())
        elif start:
            span = t("from %s") % start.isoformat()
        else:
            span = t("until %s") % last.isoformat()
        return _line("date", "%s: %s." % (info.label, span), True)

    def _leaf_line(self, model: ModelInfo, name: str, op: str, value) -> dict:
        base = name.split(".")[0]
        info = model.field(base)
        label = info.label if info else base
        shown = self._value_text(info, value)
        important = bool(info and info.type == "selection")  # status-like choices matter most
        return _line("filter", "%s %s %s." % (label, t(_OPERATOR_WORD.get(op, op)), shown), important)

    def _value_text(self, info, value) -> str:
        values = list(value) if isinstance(value, (list, tuple)) else [value]
        if info is not None and info.type == "selection":
            labels = info.selection_labels
            values = [labels.get(v, v) for v in values]
        elif info is not None and info.type == "many2one" and self.resolve_names and all(isinstance(v, int) for v in values):
            values = self.resolve_names(info.relation, values)
        elif info is not None and info.type == "boolean":
            values = [t("Yes") if v else t("No") for v in values]
        return ", ".join(str(v) for v in values)

    def _cut(self, plan: Plan) -> list:
        if plan.top_n is None:
            return []
        by = next((m.label for m in plan.measures if plan.order and plan.order.startswith(m.key + " ")), None)
        text = t("Only the first %d") % plan.top_n
        if by:
            text += t(" by %s") % by
        if plan.others:
            text += t("; the rest is grouped as 'Others'")
        return [_line("cut", text + ".", True)]

    @staticmethod
    def _cap_important(lines: list) -> list:
        shown = 0
        for line in lines:
            if not line["detail"] and line["kind"] != "warning":
                shown += 1
                if shown > MAX_IMPORTANT:
                    line["detail"] = True
        return lines
