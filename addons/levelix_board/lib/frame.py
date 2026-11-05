"""Turns the runner's raw groups into a ``Frame``: what the browser draws.

Columns, rows and meta. Values are already readable (selection labels, record
names, local ISO dates); the frontend only formats and draws, it never computes.
Empty days/months are filled here (Odoo's own ``fill_temporal`` fails with time
zones and cannot be combined with a limit).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import filters
from .errors import BoardWarning
from .i18n import t
from .planner import DimMeta, Plan

NOT_SET = "Not set"
OTHERS = "Others"
OTHERS_REF = "__others__"  # group_refs entry of the "Others" row (not a real group, cannot be drilled)
MAX_FILL_BUCKETS = 3700
_EPSILON = 1e-9


@dataclass
class Frame:
    columns: list
    rows: list
    meta: dict

    def to_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows, "meta": self.meta}


class FrameBuilder:
    def build(self, plan: Plan, groups: list, total=None, currency=None, warnings=()) -> Frame:
        warnings = list(warnings)
        truncated = False
        if plan.top_n is None and len(groups) > plan.cap:
            groups, truncated = groups[: plan.cap], True
            warnings.append(BoardWarning(
                "TOO_MANY_GROUPS", "data",
                t("There are more than %d groups; only the first %d are shown. Narrow the filters or use 'limit'.") % (plan.cap, plan.cap)))

        rows, refs = [], []
        for group in groups:
            rows.append([self._dim_cell(d, group.get(d.key), plan.tz) for d in plan.dims]
                        + [self._measure_cell(m, group.get(m.key)) for m in plan.measures])
            refs.append([self.dim_ref(group.get(d.key)) for d in plan.dims])

        if plan.fill is not None:
            rows, refs = self._fill(plan, rows, refs)
        if plan.others and total is not None:
            extra = self._others_row(plan, rows, total)
            if extra:
                rows.append(extra)
                refs.append([OTHERS_REF])

        meta = {
            "count": len(rows),
            "totals": self._totals(plan, total),
            "truncated": truncated,
            "currency": currency,
            "warnings": [w.to_dict() for w in warnings],
            "group_refs": refs,
        }
        return Frame(self._columns(plan), rows, meta)

    # -- columns / cells ----------------------------------------------------

    @staticmethod
    def _columns(plan: Plan) -> list:
        cols = []
        for d in plan.dims:
            col = {"id": d.field, "label": d.label, "role": "dimension", "type": d.type}
            if d.granularity:
                col["granularity"] = d.granularity
            cols.append(col)
        for m in plan.measures:
            cols.append({"id": m.id, "label": m.label, "role": "measure", "type": m.type})
        return cols

    @staticmethod
    def _dim_cell(dim: DimMeta, value, tz: str):
        if dim.type == "boolean":
            return t("Yes") if value else (t("No") if value is False else t(NOT_SET))
        if value is False or value is None:
            return t(NOT_SET)
        if dim.is_part:
            return int(value)
        if dim.is_bucket:
            return local_day(value[0] if isinstance(value, (list, tuple)) else value, dim.type, tz)
        if isinstance(value, (list, tuple)):  # many2one: (id, display_name)
            return value[1]
        if dim.selection:
            return dim.selection.get(value, value)
        return value

    @staticmethod
    def dim_ref(value):
        """What identifies the group later (drill-down): the raw key, JSON-safe."""
        if value is False or value is None:
            return None
        if isinstance(value, (list, tuple)):
            return value[0]
        if isinstance(value, (date, datetime)):
            return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
        return value

    @staticmethod
    def _measure_cell(measure, value):
        if value is None or value is False:
            return measure.empty_value
        return value

    # -- gaps ---------------------------------------------------------------

    def _fill(self, plan: Plan, rows: list, refs: list):
        fill, tz = plan.fill, plan.tz
        dim0 = plan.dims[0]
        not_set = t(NOT_SET)
        dated = [(r, f) for r, f in zip(rows, refs) if r[0] != not_set]
        undated = [(r, f) for r, f in zip(rows, refs) if r[0] == not_set]
        existing = {date.fromisoformat(r[0]) for r, _ in dated}

        start = filters.start_of(fill.start, fill.granularity, plan.week_start) if fill.start else (min(existing) if existing else None)
        end = (fill.end_excl - timedelta(days=1)) if fill.end_excl else (max(existing) if existing else None)
        if start is None or end is None or start > end:
            return rows, refs

        buckets = []
        day = start
        while day <= end:
            buckets.append(day)
            day = filters.next_bucket(day, fill.granularity)
            if len(buckets) > MAX_FILL_BUCKETS:
                return rows, refs

        two = len(plan.dims) == 2
        series, series_ref = [], {}
        for row, ref in dated:
            value = row[1] if two else None
            if value not in series_ref:
                series.append(value)
                series_ref[value] = ref[1] if two else None
        if not series:
            series = [None]
        taken = {(r[0], r[1] if two else None) for r, _ in dated}

        empty = [m.empty_value for m in plan.measures]
        added = []
        for bucket in buckets:
            iso = bucket.isoformat()
            ref_key = filters.local_start_utc(bucket, tz) if dim0.type == "datetime" else iso
            for value in series:
                if (iso, value) in taken:
                    continue
                added.append(([iso] + ([value] if two else []) + empty, [ref_key] + ([series_ref[value]] if two else [])))

        merged = dated + added
        order = {value: index for index, value in enumerate(series)}
        merged.sort(key=lambda pair: order.get(pair[0][1] if two else None, 0))  # stable: series order
        merged.sort(key=lambda pair: pair[0][0], reverse=fill.direction == "desc")
        merged += undated
        return [r for r, _ in merged], [f for _, f in merged]

    @staticmethod
    def _totals(plan: Plan, total):
        """``{measure id: grand total}`` for a table; only sums and counts can be totalled."""
        if not plan.totals or total is None:
            return None
        out = {}
        for measure in plan.measures:
            if measure.additive:
                value = total.get(measure.key) or 0
                out[measure.id] = round(value) if measure.agg == "count" else value
        return out

    # -- others -------------------------------------------------------------

    @staticmethod
    def _others_row(plan: Plan, rows: list, total: dict):
        offset = len(plan.dims)
        rest = []
        for index, measure in enumerate(plan.measures):
            top = sum((row[offset + index] or 0) for row in rows)
            value = (total.get(measure.key) or 0) - top
            rest.append(round(value) if measure.agg == "count" else value)
        if all(abs(v) < _EPSILON for v in rest):
            return None
        return [t(OTHERS)] + rest


def local_day(key, field_type: str, tz: str) -> str:
    """ISO date (in the viewer's time zone) of an Odoo group key."""
    if isinstance(key, datetime):
        key = key.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(key, date):
        key = key.isoformat()
    return filters.local_date_of(key, field_type, tz).isoformat()
