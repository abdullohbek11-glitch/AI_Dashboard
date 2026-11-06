"""Turns one validated widget into a ``Plan``: exactly what the runner will ask Odoo.

The plan is plain data. It carries the metadata (labels, types, selection
values) the frame builder needs, so the frame builder never touches the database.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from datetime import timedelta

from . import calc, compare, filters
from . import domain as domain_lib
from .catalog import Catalog, ModelInfo
from .errors import BoardError
from .i18n import t
from .spec import DATE_PARTS, GRANULARITIES, Dimension, Measure, Widget

DEFAULT_GROUP_CAP = 200  # more groups than this are cut and reported
DEFAULT_GRANULARITY = "month"  # a date axis without a granularity is grouped by month
PIE_MAX_SLICES = 8  # a pie with more slices keeps the biggest PIE_KEEP and groups the rest as "Others"
PIE_KEEP = 7


@dataclass(frozen=True)
class DimMeta:
    key: str  # the groupby spec sent to Odoo, e.g. "date:day"
    field: str  # as written in the spec, e.g. "partner_id.country_id"
    type: str  # field type of the value (after following a link)
    label: str
    granularity: Optional[str] = None
    selection: dict = field(default_factory=dict)

    @property
    def is_temporal(self) -> bool:
        return self.type in ("date", "datetime")

    @property
    def is_bucket(self) -> bool:
        """A calendar bucket (day/week/...), as opposed to a numeric date part."""
        return self.is_temporal and self.granularity in GRANULARITIES

    @property
    def is_part(self) -> bool:
        return self.is_temporal and self.granularity in DATE_PARTS


@dataclass(frozen=True)
class MeasureMeta:
    id: str
    key: Optional[str]  # the aggregate spec Odoo returns, e.g. "price_subtotal:sum" or "__count"; None for a calculated measure
    label: str
    type: str  # "monetary" | "number" | "percent"
    agg: str  # "sum", "avg", ..., "count", "calc"
    field: Optional[str] = None
    formula: Optional[tuple] = None  # the parsed ``calc`` of a calculated measure

    @property
    def is_calc(self) -> bool:
        return self.formula is not None

    @property
    def additive(self) -> bool:
        return self.agg in ("sum", "count")

    @property
    def empty_value(self):
        """Value of a filled-in empty bucket: zero for totals, unknown for averages."""
        return 0 if self.agg in ("sum", "count", "count_distinct") else None


@dataclass(frozen=True)
class FillSpec:
    granularity: str
    start: Optional[date]
    end_excl: Optional[date]
    direction: str = "asc"


@dataclass(frozen=True)
class ComparePlan:
    """The earlier period a widget is compared with (whole local days, end exclusive) and the query for it."""
    kind: str
    field: str
    start: date
    end_excl: date
    domain: list
    fill: Optional[FillSpec] = None


@dataclass
class Plan:
    widget_id: str
    model: str
    domain: list
    groupby: list
    aggregates: list
    having: list
    order: Optional[str]
    query_limit: Optional[int]
    cap: int
    dims: list
    measures: list
    top_n: Optional[int] = None
    others: bool = False
    totals: bool = False  # a table also gets the grand total of its additive measures
    fill: Optional[FillSpec] = None
    tz: str = "UTC"
    week_start: int = 1
    auto_others: bool = False  # a pie: more than PIE_MAX_SLICES slices become the biggest PIE_KEEP plus "Others"
    compare: Optional[ComparePlan] = None
    compare_skipped: Optional[str] = None  # why a requested comparison could not be made (shown as a warning)


class Planner:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def plan(self, widget: Widget, model: ModelInfo, tz: str, now_utc: datetime, week_start: int = 1,
             extra=(), cross: bool = False) -> Plan:
        """``extra``: conditions added to the widget's own (dashboard filters, a cross-filter). ``cross``: a cross-filter is on,
        which switches comparison off (the comparison period would not carry the clicked group)."""
        data = widget.data

        def field_type(name):
            info = model.field(name) if "." not in name else None
            return info.type if info else None

        spec_domain = list(data.domain) + [list(item) if isinstance(item, (list, tuple)) else item for item in extra]
        domain = filters.resolve_domain(spec_domain, field_type, tz, now_utc)
        dims = [self._dim_meta(d, model) for d in data.dimensions]
        measures = self._with_types([self._measure_meta(m, model) for m in data.measures])
        aggregates = list(dict.fromkeys(m.key for m in measures if m.key))

        order = self._order(data, dims, measures)
        cap = DEFAULT_GROUP_CAP
        query_limit = data.limit if data.limit is not None else cap + 1

        fill = None
        if data.fill_gaps and dims and dims[0].is_bucket:
            start, end = filters.date_bounds(domain, dims[0].field, dims[0].type, tz)
            direction = (data.order or {}).get("dir", "asc") if data.order else "asc"
            fill = FillSpec(dims[0].granularity, start, end, direction)

        compare_plan, skipped = None, None
        if data.compare and not cross:
            compare_plan, skipped = self._compare(data, spec_domain, domain, dims, fill, tz, now_utc, field_type)

        return Plan(
            widget_id=widget.id,
            model=data.source,
            domain=domain,
            groupby=[d.key for d in dims],
            aggregates=aggregates,
            having=[(self._measure_by_id(measures, mid).key, op, value) for mid, op, value in data.having],
            order=order,
            query_limit=query_limit,
            cap=cap,
            dims=dims,
            measures=measures,
            top_n=data.limit,
            others=data.others,
            totals=widget.type == "table" and not data.having and any(m.additive for m in measures),
            fill=fill,
            tz=tz,
            week_start=week_start,
            auto_others=widget.type == "pie" and not data.others and data.limit is None,
            compare=compare_plan,
            compare_skipped=skipped,
        )

    # -- comparison ----------------------------------------------------------------

    def _compare(self, data, spec_domain, domain, dims, fill, tz, now_utc, field_type):
        """``(ComparePlan, None)`` or ``(None, reason)``: the same query over the earlier period."""
        today = filters.today_in(tz, now_utc)
        flat = [leaf for leaf in spec_domain if domain_lib.is_leaf(leaf)]
        if len(flat) != len(spec_domain):
            return None, t("The comparison needs a plain list of conditions (no OR / NOT).")
        field = self._compare_field(domain, dims, field_type, tz)
        if field is None:
            return None, t("The comparison needs a start date in the filters; there is none.")
        start, end = filters.date_bounds(domain, field, field_type(field), tz)
        if end is None:
            end = today + timedelta(days=1)  # "so far": up to and including today
        try:
            before_start, before_end = compare.shift(start, end, data.compare)
        except ValueError:
            return None, t("The period is empty, so there is nothing to compare with.")
        earlier = [leaf for leaf in spec_domain if leaf[0] != field] + [[field, ">=", before_start.isoformat()], [field, "<", before_end.isoformat()]]
        earlier_fill = None
        if fill is not None:
            earlier_fill = FillSpec(fill.granularity, before_start, before_end, fill.direction)
        return ComparePlan(
            data.compare, field, before_start, before_end,
            filters.resolve_domain(earlier, field_type, tz, now_utc), earlier_fill), None

    @staticmethod
    def _compare_field(domain, dims, field_type, tz):
        """The date field whose range is shifted: the date axis if there is one, else the one date field with a start."""
        if dims and dims[0].is_temporal:
            names = [dims[0].field]
        else:
            names = list(dict.fromkeys(
                leaf[0] for leaf in domain_lib.always_true_leaves(domain_lib.parse(domain)) if field_type(leaf[0]) in ("date", "datetime")))
        for name in names:
            if "." in name or field_type(name) not in ("date", "datetime"):
                continue
            if filters.date_bounds(domain, name, field_type(name), tz)[0] is not None:
                return name
        return None

    # -- helpers --------------------------------------------------------------

    def _dim_meta(self, dim: Dimension, model: ModelInfo) -> DimMeta:
        base, _, sub = dim.field.partition(".")
        info = model.field(base)
        if sub:
            info = self.catalog.model(info.relation).field(sub)
        gran = dim.granularity
        if info.is_temporal and gran is None:
            gran = DEFAULT_GRANULARITY
        key = "%s:%s" % (dim.field, gran) if gran else dim.field
        return DimMeta(key, dim.field, info.type, info.label, gran, info.selection_labels)

    def _measure_meta(self, measure: Measure, model: ModelInfo) -> MeasureMeta:
        if measure.calc is not None:
            ftype = {"currency": "monetary", "percent": "percent", "number": "number"}.get(measure.format)
            return MeasureMeta(measure.id, None, measure.label or measure.id, ftype or "number", "calc", None, calc.parse(measure.calc))
        if measure.is_count:
            return MeasureMeta(measure.id, "__count", measure.label or "Count", "number", "count")
        info = model.field(measure.field)
        agg = measure.agg or info.aggregator
        ftype = "monetary" if info.type == "monetary" else "number"
        if measure.format == "currency":
            ftype = "monetary"
        elif measure.format == "percent":
            ftype = "percent"
        elif measure.format == "number":
            ftype = "number"
        return MeasureMeta(measure.id, "%s:%s" % (measure.field, agg), measure.label or info.label, ftype, agg, measure.field)

    @staticmethod
    def _with_types(measures: list) -> list:
        """A calculated measure with no explicit format is money when it only adds and subtracts money."""
        by_id = {m.id: m for m in measures}
        out = []
        for m in measures:
            if m.is_calc and m.type == "number":
                refs = [by_id[name] for name in calc.names(m.formula) if name in by_id]
                if refs and all(r.type == "monetary" for r in refs) and calc.operators(m.formula) <= {"+", "-", "neg"}:
                    m = MeasureMeta(m.id, m.key, m.label, "monetary", m.agg, m.field, m.formula)
            out.append(m)
        return out

    @staticmethod
    def _measure_by_id(measures, measure_id) -> MeasureMeta:
        return next(m for m in measures if m.id == measure_id)

    def _order(self, data, dims, measures) -> Optional[str]:
        if data.order:
            by, direction = data.order["by"], data.order.get("dir", "asc")
            for measure in measures:
                if measure.id == by:
                    return "%s %s" % (measure.key, direction)
            for dim in dims:
                if by in (dim.field, dim.key):
                    return "%s %s" % (dim.key, direction)
        if dims and dims[0].is_temporal:
            return "%s asc" % dims[0].key
        real = next((m for m in measures if m.key), None)
        if dims and real:
            return "%s desc" % real.key
        return None
