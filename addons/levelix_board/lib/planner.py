"""Turns one validated widget into a ``Plan``: exactly what the runner will ask Odoo.

The plan is plain data. It carries the metadata (labels, types, selection
values) the frame builder needs, so the frame builder never touches the database.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from . import filters
from .catalog import Catalog, ModelInfo
from .spec import DATE_PARTS, GRANULARITIES, Dimension, Measure, Widget

DEFAULT_GROUP_CAP = 200  # more groups than this are cut and reported
DEFAULT_GRANULARITY = "month"  # a date axis without a granularity is grouped by month


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
    key: str  # the aggregate spec Odoo returns, e.g. "price_subtotal:sum" or "__count"
    label: str
    type: str  # "monetary" | "number" | "percent"
    agg: str  # "sum", "avg", ..., "count"
    field: Optional[str] = None

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
    fill: Optional[FillSpec] = None
    tz: str = "UTC"
    week_start: int = 1


class Planner:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def plan(self, widget: Widget, model: ModelInfo, tz: str, now_utc: datetime, week_start: int = 1) -> Plan:
        data = widget.data

        def field_type(name):
            info = model.field(name) if "." not in name else None
            return info.type if info else None

        domain = filters.resolve_domain(list(data.domain), field_type, tz, now_utc)
        dims = [self._dim_meta(d, model) for d in data.dimensions]
        measures = [self._measure_meta(m, model) for m in data.measures]
        aggregates = list(dict.fromkeys(m.key for m in measures))

        order = self._order(data, dims, measures)
        cap = DEFAULT_GROUP_CAP
        query_limit = data.limit if data.limit is not None else cap + 1

        fill = None
        if data.fill_gaps and dims and dims[0].is_bucket:
            start, end = filters.date_bounds(domain, dims[0].field, dims[0].type, tz)
            direction = (data.order or {}).get("dir", "asc") if data.order else "asc"
            fill = FillSpec(dims[0].granularity, start, end, direction)

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
            fill=fill,
            tz=tz,
            week_start=week_start,
        )

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
        if dims and measures:
            return "%s desc" % measures[0].key
        return None
