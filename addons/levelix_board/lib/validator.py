"""Semantic checks of a spec against the real models and fields.

Errors block execution; warnings are shown to the user. Every message is a plain
sentence that names the problem and, where possible, the way out, because the AI
self-repair loop feeds these messages straight back to the model.
"""
import difflib

from . import domain as domain_lib
from . import drill as drill_lib
from . import filters
from .catalog import NUMERIC_TYPES, TEMPORAL_TYPES, Catalog, ModelInfo
from .errors import BoardError, BoardWarning, ValidationResult
from .i18n import t
from .spec import (
    AGGREGATES, DATE_PARTS, GRANULARITIES, MAX_SPEC_BYTES, MAX_WIDGETS, MEASURE_FORMATS,
    SHAPES, TIME_AXIS_TYPES, Data, Spec, Widget,
)

MAX_DIMENSIONS = 2
MAX_MEASURES = 4
MAX_LIMIT = 500
DOMAIN_OPERATORS = (
    "=", "!=", "<", "<=", ">", ">=", "in", "not in", "like", "not like", "ilike", "not ilike",
    "=like", "=ilike", "child_of", "parent_of",
)
HAVING_OPERATORS = ("=", "!=", "<", "<=", ">", ">=")
LIST_OPERATORS = ("in", "not in")
PATTERN_OPERATORS = ("like", "not like", "ilike", "not ilike", "=like", "=ilike")
SCALAR_TYPES = (str, int, float, bool, type(None))
ADDITIVE_AGGREGATES = ("sum", "count")
HOUR_PARTS = ("hour_number", "minute_number", "second_number")
LOG_DATES = ("create_date", "write_date")


def allowed_aggregates(field) -> tuple:
    """Aggregates that make sense for a field.

    A field is summable only if Odoo declares ``sum`` as its aggregator (prices,
    percentages and ratios declare ``avg`` and must not be added up).
    """
    allowed = []
    if field.aggregator == "sum":
        allowed += ["sum", "avg", "min", "max"]
    elif field.aggregator == "avg":
        allowed += ["avg", "min", "max"]
    elif field.type in NUMERIC_TYPES or field.type in TEMPORAL_TYPES:
        allowed += ["min", "max"]
    if field.type != "boolean" and field.type not in ("binary", "html"):
        allowed.append("count_distinct")
    return tuple(allowed)


def _is_number(value) -> bool:
    """A number, or text that reads as one ("5"); true/false are not numbers here."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _suggest(name: str, candidates) -> str:
    close = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return " Did you mean '%s'?" % close[0] if close else ""


class Validator:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    # -- entry points -------------------------------------------------------

    def validate_spec(self, spec: Spec) -> ValidationResult:
        result = ValidationResult([], [])
        if len(spec.widgets) > MAX_WIDGETS:
            result.errors.append(BoardError("SPEC_TOO_LARGE", "widgets", "At most %d widgets are allowed." % MAX_WIDGETS))
        if spec.size_bytes() > MAX_SPEC_BYTES:
            result.errors.append(BoardError("SPEC_TOO_LARGE", "", "The spec is larger than %d KB." % (MAX_SPEC_BYTES // 1024)))
        seen = set()
        for index, widget in enumerate(spec.widgets):
            path = "widgets[%d]" % index
            if widget.id in seen:
                result.errors.append(BoardError("DUPLICATE_ID", path + ".id", "Widget id '%s' is used twice." % widget.id))
            seen.add(widget.id)
            sub = self.validate_widget(widget, path)
            result.errors += sub.errors
            result.warnings += sub.warnings
        return result

    def validate_widget(self, widget: Widget, path: str = "widget") -> ValidationResult:
        result = ValidationResult([], [])
        err = lambda code, sub, message: result.errors.append(BoardError(code, "%s%s" % (path, sub), message))  # noqa: E731
        data = widget.data
        dpath = ".data"

        if widget.type not in SHAPES:
            err("UNKNOWN_TYPE", ".type", "Unknown widget type '%s'. Allowed: %s." % (widget.type, ", ".join(SHAPES)))
        model = self.catalog.model(data.source)
        if model is None:
            err("UNKNOWN_MODEL", dpath + ".source", "Model '%s' does not exist." % data.source)
            return result
        if not model.accessible:
            err("NO_ACCESS", dpath + ".source", "You are not allowed to read '%s'." % model.label)
            return result

        self._check_domain(data, model, path, result)
        dim_fields = self._check_dimensions(data, model, path, result)
        measure_ids = self._check_measures(data, model, path, result)
        self._check_order(data, model, measure_ids, path, result)
        self._check_limit_others(data, model, path, result)
        self._check_having(data, measure_ids, path, result)
        if widget.type in SHAPES:
            self._check_shape(widget, dim_fields, path, result)
        if data.compare is not None:
            err("UNSUPPORTED", dpath + ".compare", "'compare' is not available yet.")
        result.errors += drill_lib.check(widget, model, self.catalog, path)
        if not result.errors:
            self._warnings(data, model, path, result)
        return result

    # -- parts --------------------------------------------------------------

    def _check_domain(self, data: Data, model: ModelInfo, path: str, result: ValidationResult):
        dpath = path + ".data.domain"
        try:
            nodes = domain_lib.parse(data.domain, dpath)
        except BoardError as error:
            result.errors.append(error)
            return
        for leaf in domain_lib.leaves(nodes):
            name, op, value = leaf
            base = name.split(".")[0]
            field = model.field(base)
            if field is None:
                result.errors.append(BoardError(
                    "UNKNOWN_FIELD", dpath, "Model '%s' has no field '%s'.%s" % (model.name, base, _suggest(base, model.fields))))
                continue
            if op not in DOMAIN_OPERATORS:
                result.errors.append(BoardError("BAD_OPERATOR", dpath, "Operator '%s' is not allowed in a domain." % op))
                continue
            if "." not in name and not field.is_temporal:
                self._check_value(field, op, value, dpath, result)
            if "." not in name and field.is_temporal:
                for element in (value if isinstance(value, (list, tuple)) else [value]):
                    try:
                        filters.check_date_value(element)
                    except ValueError as error:
                        result.errors.append(BoardError(
                            "BAD_DATE", dpath, "Cannot read the date %r on '%s': %s." % (element, field.label, error)))

    def _check_value(self, field, op, value, dpath: str, result: ValidationResult):
        """What a condition compares with must make sense for the field, or the answer is a silent "0 rows"."""
        err = lambda code, message: result.errors.append(BoardError(code, dpath, message))  # noqa: E731
        if op in ("child_of", "parent_of"):
            return
        if op in LIST_OPERATORS:
            if not isinstance(value, (list, tuple)):
                err("BAD_VALUE", "'%s' %s needs a list of values, for example [\"a\", \"b\"]." % (field.label, op))
                return
            items = list(value)
        elif isinstance(value, (list, tuple)):
            err("BAD_VALUE", "'%s' %s compares with one value, not a list. Use 'in' for several." % (field.label, op))
            return
        else:
            items = [value]
        if not all(isinstance(item, SCALAR_TYPES) for item in items):
            err("BAD_VALUE", "Values compared with '%s' must be text, numbers, true/false or null." % field.label)
            return
        if op in PATTERN_OPERATORS:
            return
        empty = (False, None)
        if field.type == "selection" and field.selection:
            allowed = [key for key, _label in field.selection]
            for item in items:
                if item not in empty and item not in allowed:
                    options = ", ".join("%s (%s)" % pair for pair in field.selection[:12])
                    err("UNKNOWN_VALUE", "'%s' is not a value of '%s'. Use one of: %s." % (item, field.label, options))
                    return
        elif field.is_numeric:
            for item in items:
                if item not in empty and not _is_number(item):
                    err("BAD_VALUE", "'%s' is a number field; %r is not a number." % (field.label, item))
                    return
        elif field.type == "boolean":
            for item in items:
                if item is not None and item not in (True, False, 0, 1):
                    err("BAD_VALUE", "'%s' is a yes/no field; compare it with true or false, not %r." % (field.label, item))
                    return

    def _split_dimension(self, dim, model, path, result):
        """Return the FieldInfo that decides the dimension's type, or ``None`` after reporting."""
        err = lambda code, message: result.errors.append(BoardError(code, path, message))  # noqa: E731
        base, _, sub = dim.field.partition(".")
        field = model.field(base)
        if field is None:
            err("UNKNOWN_FIELD", "Model '%s' has no field '%s'.%s" % (model.name, base, _suggest(base, model.fields)))
            return None
        if not field.store:
            err("LEVEL_MISMATCH", "'%s' is a computed field and cannot be a grouping axis." % field.label)
            return None
        if sub:
            if field.type != "many2one":
                err("LEVEL_MISMATCH", "'%s' is not a link to another record, so '%s' cannot be followed." % (field.label, sub))
                return None
            if "." in sub:
                err("LEVEL_MISMATCH", "A grouping axis may follow only one link ('%s')." % dim.field)
                return None
            comodel = self.catalog.model(field.relation)
            target = comodel.field(sub) if comodel else None
            if target is None or not target.store:
                err("UNKNOWN_FIELD", "'%s' has no stored field '%s'." % (field.label, sub))
                return None
            field = target
        if not field.groupable:
            err("NOT_GROUPABLE", "'%s' cannot be used as a grouping axis." % field.label)
            return None
        return field

    def _check_dimensions(self, data: Data, model: ModelInfo, path: str, result: ValidationResult) -> list:
        fields = []
        if len(data.dimensions) > MAX_DIMENSIONS:
            result.errors.append(BoardError("BAD_SHAPE", path + ".data.dimensions", "At most %d dimensions are allowed." % MAX_DIMENSIONS))
        for index, dim in enumerate(data.dimensions):
            dpath = "%s.data.dimensions[%d]" % (path, index)
            field = self._split_dimension(dim, model, dpath, result)
            fields.append(field)
            if field is None:
                continue
            gran = dim.granularity
            if gran is not None:
                if not field.is_temporal:
                    result.errors.append(BoardError(
                        "BAD_GRANULARITY", dpath, "'%s' is not a date, so it cannot be grouped by '%s'." % (field.label, gran)))
                elif gran not in GRANULARITIES + DATE_PARTS:
                    result.errors.append(BoardError(
                        "BAD_GRANULARITY", dpath, "Unknown granularity '%s'. Allowed: %s." % (gran, ", ".join(GRANULARITIES + DATE_PARTS))))
                elif gran in HOUR_PARTS and field.type != "datetime":
                    result.errors.append(BoardError("BAD_GRANULARITY", dpath, "'%s' has no time of day." % field.label))
        return fields

    def _check_measures(self, data: Data, model: ModelInfo, path: str, result: ValidationResult) -> set:
        ids = set()
        if len(data.measures) > MAX_MEASURES:
            result.errors.append(BoardError("BAD_SHAPE", path + ".data.measures", "At most %d measures are allowed." % MAX_MEASURES))
        for index, measure in enumerate(data.measures):
            mpath = "%s.data.measures[%d]" % (path, index)
            err = lambda code, message, mpath=mpath: result.errors.append(BoardError(code, mpath, message))  # noqa: E731
            if measure.id in ids:
                err("DUPLICATE_ID", "Measure id '%s' is used twice." % measure.id)
            ids.add(measure.id)
            if measure.format is not None and measure.format not in MEASURE_FORMATS:
                err("BAD_FORMAT", "Unknown format '%s'. Allowed: %s." % (measure.format, ", ".join(MEASURE_FORMATS)))
            if measure.agg is not None and measure.agg not in AGGREGATES:
                err("NOT_AGGREGATABLE", "Unknown aggregate '%s'. Allowed: %s." % (measure.agg, ", ".join(AGGREGATES)))
                continue
            if measure.calc is not None:
                err("UNSUPPORTED", "Calculated measures are not available yet.")
                continue
            if measure.is_count:
                continue
            field = model.field(measure.field.split(".")[0])
            if "." in measure.field:
                err("LEVEL_MISMATCH", "A measure must be a field of '%s' itself, not '%s' (that would count some rows several times)." % (model.label, measure.field))
                continue
            if field is None:
                err("UNKNOWN_FIELD", "Model '%s' has no field '%s'.%s" % (model.name, measure.field, _suggest(measure.field, model.fields)))
                continue
            if not field.store:
                err("LEVEL_MISMATCH", "'%s' is a computed field; it cannot be summed from the database." % field.label)
                continue
            allowed = allowed_aggregates(field)
            agg = measure.agg or field.aggregator
            if agg not in allowed:
                what = "summed" if agg in (None, "sum") else "used with '%s'" % agg
                tail = " Allowed: %s." % ", ".join(allowed) if allowed else " It can only be used in a count."
                err("NOT_AGGREGATABLE", "Field '%s' cannot be %s.%s" % (field.name, what, tail))
        return ids

    def _check_order(self, data, model, measure_ids, path, result):
        if data.order is None:
            return
        opath = path + ".data.order"
        by, direction = data.order.get("by"), data.order.get("dir", "asc")
        if not isinstance(by, str):
            result.errors.append(BoardError("BAD_ORDER", opath, "'by' must be a measure id or a dimension name (text)."))
            return
        if direction not in ("asc", "desc"):
            result.errors.append(BoardError("BAD_ORDER", opath, "'dir' must be 'asc' or 'desc'."))
        dim_names = {d.field for d in data.dimensions} | {d.key for d in data.dimensions}
        if by not in measure_ids and by not in dim_names:
            options = sorted(measure_ids | {d.field for d in data.dimensions})
            result.errors.append(BoardError("BAD_ORDER", opath, "Cannot order by '%s'. Use a measure id or a dimension: %s." % (by, ", ".join(options) or "-")))

    def _check_limit_others(self, data: Data, model, path, result):
        lpath = path + ".data"
        if data.limit is not None and not 1 <= data.limit <= MAX_LIMIT:
            result.errors.append(BoardError("BAD_LIMIT", lpath + ".limit", "'limit' must be between 1 and %d." % MAX_LIMIT))
        if not data.others:
            return
        if data.limit is None:
            result.errors.append(BoardError("BAD_SHAPE", lpath + ".others", "'others' needs a 'limit' (the rest is grouped as 'Others')."))
        if len(data.dimensions) != 1:
            result.errors.append(BoardError("BAD_SHAPE", lpath + ".others", "'others' works with exactly one dimension."))
        if data.having:
            result.errors.append(BoardError("BAD_SHAPE", lpath + ".others", "'others' cannot be combined with 'having'."))
        for index, measure in enumerate(data.measures):
            if measure.calc is None and not measure.is_count:
                field = model.field((measure.field or "").split(".")[0])
                agg = measure.agg or (field.aggregator if field else None)
                if agg not in ADDITIVE_AGGREGATES:
                    result.errors.append(BoardError(
                        "NON_ADDITIVE_OTHERS", "%s.measures[%d]" % (lpath, index),
                        "'Others' is only correct for sums and counts; '%s' of '%s' cannot be added up." % (agg, measure.field)))

    def _check_having(self, data: Data, measure_ids, path, result):
        for index, item in enumerate(data.having):
            hpath = "%s.data.having[%d]" % (path, index)
            if not (isinstance(item, (list, tuple)) and len(item) == 3):
                result.errors.append(BoardError("BAD_HAVING", hpath, "A 'having' condition looks like [measure_id, operator, number]."))
                continue
            mid, op, value = item
            if not isinstance(mid, str) or not isinstance(op, str):
                result.errors.append(BoardError("BAD_HAVING", hpath, "A 'having' condition looks like [measure_id, operator, number]."))
                continue
            if mid not in measure_ids:
                result.errors.append(BoardError("UNKNOWN_MEASURE", hpath, "No measure with id '%s'." % mid))
            if op not in HAVING_OPERATORS:
                result.errors.append(BoardError("BAD_HAVING", hpath, "Operator '%s' is not allowed here." % op))
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                result.errors.append(BoardError("BAD_HAVING", hpath, "The compared value must be a number."))

    def _check_shape(self, widget: Widget, dim_fields: list, path: str, result: ValidationResult):
        data = widget.data
        min_d, max_d, min_m, max_m = SHAPES[widget.type]
        spath = path + ".data"
        n_dims, n_meas = len(data.dimensions), len(data.measures)
        if not min_d <= n_dims <= max_d:
            result.errors.append(BoardError("BAD_SHAPE", spath + ".dimensions", "A '%s' widget needs %s dimension(s), got %d." % (widget.type, _range(min_d, max_d), n_dims)))
        if not min_m <= n_meas <= max_m:
            result.errors.append(BoardError("BAD_SHAPE", spath + ".measures", "A '%s' widget needs %s measure(s), got %d." % (widget.type, _range(min_m, max_m), n_meas)))
        if widget.type in TIME_AXIS_TYPES and dim_fields and dim_fields[0] is not None and not dim_fields[0].is_temporal:
            result.errors.append(BoardError("BAD_SHAPE", spath + ".dimensions[0]", "A '%s' widget needs a date as its first dimension." % widget.type))
        if widget.type == "pie" and data.limit is not None and data.limit > 8:
            result.errors.append(BoardError("BAD_SHAPE", spath + ".limit", "A pie chart shows at most 8 slices."))
        if widget.type == "gauge":
            target = widget.view.get("target")
            if isinstance(target, bool) or not isinstance(target, (int, float)):
                result.errors.append(BoardError("BAD_SHAPE", path + ".view.target", "A gauge needs a numeric 'view.target'."))
        if data.fill_gaps:
            first = dim_fields[0] if dim_fields else None
            dim = data.dimensions[0] if data.dimensions else None
            if first is None or not first.is_temporal or dim.granularity not in GRANULARITIES:
                result.errors.append(BoardError("BAD_SHAPE", spath + ".fill_gaps", "'fill_gaps' needs a date axis grouped by day, week, month, quarter or year."))
            elif data.order and data.order.get("by") not in (dim.field, dim.key):
                result.errors.append(BoardError("BAD_SHAPE", spath + ".fill_gaps", "'fill_gaps' needs the rows ordered by the date axis."))

    def _warnings(self, data: Data, model: ModelInfo, path: str, result: ValidationResult):
        wpath = path + ".data"
        nodes = domain_lib.parse(data.domain)
        used = {leaf[0].split(".")[0] for leaf in domain_lib.leaves(nodes)}
        state = model.field("state")
        if state is not None and state.type == "selection" and "state" not in used:
            result.warnings.append(BoardWarning(
                "STATE_FILTER_MISSING", wpath + ".domain",
                t("There is no filter on '%s', so every status is counted (for example cancelled records).") % state.label))
        log_used = [d.field for d in data.dimensions if d.field in LOG_DATES] + [n for n in used if n in LOG_DATES]
        other_dates = [f for f in model.fields.values() if f.is_temporal and f.store and f.name not in LOG_DATES]
        if log_used and other_dates:
            result.warnings.append(BoardWarning(
                "SUSPICIOUS_DATE", wpath,
                t("The date used is when the record was created in the system, not a business date. '%s' may be what you mean.") % other_dates[0].label))


def _range(low: int, high: int) -> str:
    return str(low) if low == high else "%d to %d" % (low, high)
