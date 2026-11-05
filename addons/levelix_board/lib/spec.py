"""The spec: the one format the AI produces and the server stores and runs.

This module only knows structure (types, required keys, unknown keys). Whether a
model or field exists, or whether a measure may be summed, is the validator's job.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional

from .errors import BoardError

SPEC_VERSION = 1
MAX_WIDGETS = 30
MAX_SPEC_BYTES = 256 * 1024

GRANULARITIES = ("day", "week", "month", "quarter", "year")
DATE_PARTS = (
    "year_number", "quarter_number", "month_number", "iso_week_number", "day_of_year",
    "day_of_month", "day_of_week", "hour_number", "minute_number", "second_number",
)
AGGREGATES = ("sum", "avg", "min", "max", "count_distinct", "count")
MEASURE_FORMATS = ("number", "currency", "percent")

# widget type -> (min dimensions, max dimensions, min measures, max measures)
SHAPES = {
    "kpi": (0, 1, 1, 3),
    "line": (1, 2, 1, 3),
    "area": (1, 2, 1, 3),
    "bar": (1, 2, 1, 3),
    "pie": (1, 1, 1, 1),
    "table": (1, 2, 1, 4),
    "heatmap": (2, 2, 1, 1),
    "funnel": (1, 1, 1, 1),
    "treemap": (1, 2, 1, 1),
    "gauge": (0, 0, 1, 1),
    "waterfall": (1, 1, 1, 1),
    "scatter": (1, 1, 2, 2),
    "combo": (1, 1, 2, 2),
}
TIME_AXIS_TYPES = ("kpi", "line", "area")  # first dimension (if any) must be a date axis
WIDGET_TYPES = tuple(SHAPES)

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def _bad(path, message, code="BAD_SPEC"):
    raise BoardError(code, path, message)


def _only_keys(raw: dict, allowed: tuple, path: str):
    unknown = sorted(set(raw) - set(allowed))
    if unknown:
        _bad(path, "Unknown key(s) %s. Allowed: %s." % (", ".join(unknown), ", ".join(allowed)), "UNKNOWN_KEY")


def _expect(value, types, path, what):
    if isinstance(value, bool) and bool not in (types if isinstance(types, tuple) else (types,)):
        _bad(path, "%s must not be a boolean." % what)
    if not isinstance(value, types):
        name = types.__name__ if isinstance(types, type) else "/".join(t.__name__ for t in types)
        _bad(path, "%s must be of type %s." % (what, name))
    return value


@dataclass(frozen=True)
class Dimension:
    field: str
    granularity: Optional[str] = None

    @property
    def key(self) -> str:
        return "%s:%s" % (self.field, self.granularity) if self.granularity else self.field

    @classmethod
    def from_raw(cls, raw, path: str) -> "Dimension":
        if isinstance(raw, str):
            name, _, gran = raw.partition(":")
            return cls(name, gran or None)
        _expect(raw, dict, path, "A dimension")
        _only_keys(raw, ("field", "granularity"), path)
        if not isinstance(raw.get("field"), str) or not raw["field"]:
            _bad(path, "A dimension needs a 'field'.")
        gran = raw.get("granularity")
        if gran is not None:
            _expect(gran, str, path + ".granularity", "'granularity'")
        return cls(raw["field"], gran)

    def to_raw(self) -> dict:
        raw = {"field": self.field}
        if self.granularity:
            raw["granularity"] = self.granularity
        return raw


@dataclass(frozen=True)
class Measure:
    id: str
    field: Optional[str] = None
    agg: Optional[str] = None
    label: Optional[str] = None
    format: Optional[str] = None
    calc: Optional[str] = None

    @property
    def is_count(self) -> bool:
        return self.calc is None and (self.field == "__count" or (self.field is None and self.agg == "count"))

    @classmethod
    def from_raw(cls, raw, path: str) -> "Measure":
        _expect(raw, dict, path, "A measure")
        _only_keys(raw, ("id", "field", "agg", "label", "format", "calc"), path)
        for key in ("id", "field", "agg", "label", "format", "calc"):
            if raw.get(key) is not None:
                _expect(raw[key], str, "%s.%s" % (path, key), "'%s'" % key)
        if not raw.get("id") or not _ID_RE.match(raw["id"]):
            _bad(path, "A measure needs an 'id' like 'm1' (lowercase letters, digits, underscore).")
        measure = cls(raw["id"], raw.get("field"), raw.get("agg"), raw.get("label"), raw.get("format"), raw.get("calc"))
        if not (measure.field or measure.calc or measure.agg == "count"):
            _bad(path, "A measure needs a 'field' (or agg 'count', or a 'calc').")
        return measure

    def to_raw(self) -> dict:
        raw = {"id": self.id}
        for key in ("field", "agg", "label", "format", "calc"):
            if getattr(self, key) is not None:
                raw[key] = getattr(self, key)
        return raw


@dataclass(frozen=True)
class Data:
    source: str
    measures: tuple
    domain: tuple = ()
    dimensions: tuple = ()
    order: Optional[dict] = None
    limit: Optional[int] = None
    others: bool = False
    having: tuple = ()
    fill_gaps: bool = False
    compare: Optional[str] = None

    _KEYS = (
        "source", "domain", "dimensions", "measures", "order", "limit", "others",
        "having", "fill_gaps", "compare",
    )

    @classmethod
    def from_raw(cls, raw, path: str) -> "Data":
        _expect(raw, dict, path, "'data'")
        _only_keys(raw, cls._KEYS, path)
        source = _expect(raw.get("source"), str, path + ".source", "'source'")
        domain = _expect(raw.get("domain", []), list, path + ".domain", "'domain'")
        dims = _expect(raw.get("dimensions", []), list, path + ".dimensions", "'dimensions'")
        measures = _expect(raw.get("measures"), list, path + ".measures", "'measures'")
        order = raw.get("order")
        if order is not None:
            _expect(order, dict, path + ".order", "'order'")
            _only_keys(order, ("by", "dir"), path + ".order")
        limit = raw.get("limit")
        if limit is not None:
            _expect(limit, int, path + ".limit", "'limit'")
        having = _expect(raw.get("having", []), list, path + ".having", "'having'")
        compare = raw.get("compare")
        if compare is not None:
            _expect(compare, str, path + ".compare", "'compare'")
        return cls(
            source=source,
            measures=tuple(Measure.from_raw(m, "%s.measures[%d]" % (path, i)) for i, m in enumerate(measures)),
            domain=tuple(domain),
            dimensions=tuple(Dimension.from_raw(d, "%s.dimensions[%d]" % (path, i)) for i, d in enumerate(dims)),
            order=order,
            limit=limit,
            others=_expect(raw.get("others", False), bool, path + ".others", "'others'"),
            having=tuple(having),
            fill_gaps=_expect(raw.get("fill_gaps", False), bool, path + ".fill_gaps", "'fill_gaps'"),
            compare=compare,
        )

    def to_raw(self) -> dict:
        raw = {"source": self.source}
        if self.domain:
            raw["domain"] = list(self.domain)
        if self.dimensions:
            raw["dimensions"] = [d.to_raw() for d in self.dimensions]
        raw["measures"] = [m.to_raw() for m in self.measures]
        if self.order is not None:
            raw["order"] = dict(self.order)
        if self.limit is not None:
            raw["limit"] = self.limit
        if self.others:
            raw["others"] = True
        if self.having:
            raw["having"] = list(self.having)
        if self.fill_gaps:
            raw["fill_gaps"] = True
        if self.compare is not None:
            raw["compare"] = self.compare
        return raw


@dataclass(frozen=True)
class Widget:
    id: str
    type: str
    data: Data
    title: str = ""
    grid: Optional[dict] = None
    view: dict = field(default_factory=dict)
    interact: dict = field(default_factory=dict)

    _KEYS = ("id", "type", "title", "grid", "data", "view", "interact")

    @classmethod
    def from_raw(cls, raw, path: str) -> "Widget":
        _expect(raw, dict, path, "A widget")
        _only_keys(raw, cls._KEYS, path)
        wid = raw.get("id")
        if not isinstance(wid, str) or not _ID_RE.match(wid):
            _bad(path, "A widget needs an 'id' like 'w1' (lowercase letters, digits, underscore).")
        wtype = _expect(raw.get("type"), str, path + ".type", "'type'")
        if "data" not in raw:
            _bad(path, "A widget needs a 'data' block.")
        grid = raw.get("grid")
        if grid is not None:
            _expect(grid, dict, path + ".grid", "'grid'")
        return cls(
            id=wid,
            type=wtype,
            data=Data.from_raw(raw["data"], path + ".data"),
            title=_expect(raw.get("title", ""), str, path + ".title", "'title'"),
            grid=grid,
            view=_expect(raw.get("view", {}), dict, path + ".view", "'view'"),
            interact=_expect(raw.get("interact", {}), dict, path + ".interact", "'interact'"),
        )

    def to_raw(self) -> dict:
        raw = {"id": self.id, "type": self.type}
        if self.title:
            raw["title"] = self.title
        if self.grid is not None:
            raw["grid"] = dict(self.grid)
        raw["data"] = self.data.to_raw()
        if self.view:
            raw["view"] = dict(self.view)
        if self.interact:
            raw["interact"] = dict(self.interact)
        return raw


@dataclass(frozen=True)
class Spec:
    widgets: tuple
    title: str = ""
    v: int = SPEC_VERSION
    assumptions: tuple = ()
    filters: tuple = ()
    uncertain: tuple = ()

    _KEYS = ("v", "title", "assumptions", "filters", "widgets", "uncertain")

    @classmethod
    def from_raw(cls, raw) -> "Spec":
        raw = migrate(raw)
        _only_keys(raw, cls._KEYS, "")
        widgets = _expect(raw.get("widgets"), list, "widgets", "'widgets'")
        return cls(
            widgets=tuple(Widget.from_raw(w, "widgets[%d]" % i) for i, w in enumerate(widgets)),
            title=_expect(raw.get("title", ""), str, "title", "'title'"),
            v=raw["v"],
            assumptions=tuple(_expect(raw.get("assumptions", []), list, "assumptions", "'assumptions'")),
            filters=tuple(_expect(raw.get("filters", []), list, "filters", "'filters'")),
            uncertain=tuple(_expect(raw.get("uncertain", []), list, "uncertain", "'uncertain'")),
        )

    def to_raw(self) -> dict:
        raw = {"v": self.v}
        if self.title:
            raw["title"] = self.title
        if self.assumptions:
            raw["assumptions"] = list(self.assumptions)
        if self.filters:
            raw["filters"] = list(self.filters)
        raw["widgets"] = [w.to_raw() for w in self.widgets]
        if self.uncertain:
            raw["uncertain"] = list(self.uncertain)
        return raw

    def widget(self, widget_id: str) -> Optional[Widget]:
        return next((w for w in self.widgets if w.id == widget_id), None)

    def size_bytes(self) -> int:
        return len(json.dumps(self.to_raw(), ensure_ascii=False).encode("utf-8"))


# Each entry upgrades a spec of version N to N+1. Empty while only v1 exists.
MIGRATIONS: dict = {}


def migrate(raw) -> dict:
    """Bring a stored spec up to ``SPEC_VERSION``; never mutates the input."""
    _expect(raw, dict, "", "A spec")
    version = raw.get("v")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        _bad("v", "The spec needs an integer version 'v' (>= 1).")
    if version > SPEC_VERSION:
        _bad("v", "Spec version %d is newer than this server understands (%d)." % (version, SPEC_VERSION),
             "UNSUPPORTED_VERSION")
    while version < SPEC_VERSION:
        raw = MIGRATIONS[version](raw)
        version = raw["v"]
    return raw
