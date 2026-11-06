"""Thin Odoo adapter: wires the pure ``lib`` pieces to the caller's environment.

The methods are private on purpose (``_run_spec`` ...): they are the building
blocks. The public RPC surface is ``levelix.board.lx_*`` (``board_rpc.py``), which
checks the board and the arguments first and then calls these.
"""
import json
import logging
from collections import namedtuple
from dataclasses import replace
from datetime import datetime

from odoo import api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import get_lang

from ..lib import board_filters
from ..lib import drill as drill_lib
from ..lib import filters as date_lib
from ..lib import runner as runner_lib
from ..lib.errors import BoardError, BoardWarning
from ..lib.explain import ExplainBuilder
from ..lib.frame import OTHERS_REF, FrameBuilder
from ..lib.i18n import t
from ..lib.planner import Planner
from ..lib.spec import MAX_SPEC_BYTES, Spec
from ..lib.validator import Validator
from .env_catalog import EnvCatalog

_logger = logging.getLogger(__name__)
# what the dashboard filters add to every widget: conditions per model, the clicked group of a cross-filter, the money fields to
# read instead (``swaps``) and the chosen basis ("untaxed" / "taxed", or None without an Amounts filter)
Extras = namedtuple("Extras", "leaves crossing swaps basis filters")
_SHAPE_ERRORS = (TypeError, AttributeError, KeyError, IndexError, ValueError)  # what a wrongly typed JSON value raises


class LevelixBoardEngine(models.AbstractModel):
    _name = "levelix.board.engine"
    _description = "Levelix Board query engine"

    # -- validating -------------------------------------------------------------

    @api.model
    def _validate_spec(self, raw) -> dict:
        """Structure and semantics of a whole spec. Never raises for a bad spec."""
        try:
            spec = Spec.from_raw(raw)
            return Validator(EnvCatalog(self.env)).validate_spec(spec).to_dict()
        except BoardError as error:
            return {"ok": False, "errors": [error.to_dict()], "warnings": []}
        except _SHAPE_ERRORS:
            return {"ok": False, "errors": [self._odd_shape().to_dict()], "warnings": []}

    @api.model
    def _normalise_spec(self, raw):
        """``(clean_spec, warnings)`` or raise ``BoardError`` / ``SpecInvalid``: what saving a spec needs."""
        if len(json.dumps(raw, ensure_ascii=False, default=str).encode("utf-8")) > MAX_SPEC_BYTES * 2:
            raise BoardError("SPEC_TOO_LARGE", "", t("The spec is larger than %d KB.") % (MAX_SPEC_BYTES // 1024))
        try:
            spec = Spec.from_raw(raw)
            result = Validator(EnvCatalog(self.env)).validate_spec(spec)
        except _SHAPE_ERRORS as error:
            raise self._odd_shape() from error
        result.raise_if_invalid()
        return spec.to_raw(), [w.to_dict() for w in result.warnings]

    @api.model
    def _still_fits(self, raw) -> bool:
        """Is this spec (with one option left in it) still valid? Used to keep only options that still apply."""
        try:
            self._normalise_spec(raw)
        except (BoardError, UserError):
            return False
        return True

    @staticmethod
    def _odd_shape() -> BoardError:
        """Safety net for a value of an unexpected type that no specific check caught: a clear error, never a server error."""
        _logger.exception("The spec has an unexpected shape")
        return BoardError("BAD_SPEC", "", t("The spec has an unexpected shape and could not be checked. Compare it with the format description."))

    # -- running -------------------------------------------------------------------

    @api.model
    def _run_spec(self, raw, widget_ids=None, explain=False, filter_values=None, cross=None) -> dict:
        """Run a spec (or some of its widgets). One widget failing does not affect the others.

        Returns ``{"widgets": {id: {"frame": {...}, "explain": [...]} | {"error": {...}}}}``.
        ``widget_ids`` must name widgets of the spec. ``filter_values`` are the reader's choices for the dashboard filters;
        ``cross`` is ``{"widget_id", "group_ref"}``: the clicked group of a cross-filtering widget.
        """
        spec = Spec.from_raw(raw)  # a structurally broken spec is a caller error
        if widget_ids is not None:
            unknown = [w for w in widget_ids if spec.widget(w) is None]
            if unknown:
                raise BoardError("UNKNOWN_WIDGET", "widget_ids", t("The dashboard has no widget '%s'.") % unknown[0])
        catalog = EnvCatalog(self.env)
        extras = self._extras(spec, catalog, filter_values, cross)
        out = {}
        for index, widget in enumerate(spec.widgets):
            if widget_ids is not None and widget.id not in widget_ids:
                continue
            extra, crossed = self._extra_for(widget, extras)
            shown, note = self._variant(widget, extras)
            out[widget.id] = self._run_widget(shown, catalog, "widgets[%d]" % index, explain, extra, crossed, spec.filters, note)
        return {"widgets": out}

    def _plan(self, widget, catalog, extra=(), cross=False):
        model = catalog.model(widget.data.source)
        tz = self.env.context.get("tz") or self.env.user.tz or "UTC"
        week_start = int(get_lang(self.env).week_start)
        return model, Planner(catalog).plan(widget, model, tz, datetime.utcnow(), week_start, extra, cross)

    # -- dashboard filters and cross-filtering ----------------------------------------------

    def _today_and_week(self):
        tz = self.env.context.get("tz") or self.env.user.tz or "UTC"
        return date_lib.today_in(tz, datetime.utcnow()), int(get_lang(self.env).week_start)

    @api.model
    def _extras(self, spec, catalog, filter_values, cross):
        """What the dashboard filters and a cross-filter add to every widget: an ``Extras``."""
        leaves, swaps, basis = {}, {}, None
        if spec.filters or filter_values:
            today, week_start = self._today_and_week()
            leaves, parsed = board_filters.resolve(
                list(spec.filters), filter_values, catalog, today, week_start, self.env.user.company_ids.ids)
            swaps = board_filters.swaps(list(spec.filters), parsed)
            basis = next((v[1] for v in parsed.values() if v and v[0] == "basis"), None)
        extras = Extras(leaves, None, swaps, basis, list(spec.filters))
        return extras._replace(crossing=self._cross(spec, catalog, cross, extras))

    @staticmethod
    def _variant(widget, extras):
        """``(the widget reading the money fields the reader chose, a plain note for "how it was calculated" or None)``."""
        swapped = board_filters.swap_measures(widget, extras.swaps.get(widget.data.source) or {})
        follows = extras.basis and board_filters.follows_basis(widget, extras.filters)
        return swapped, (t("Amounts: %s.") % t(board_filters.BASIS_LABELS[extras.basis]).lower() if follows else None)

    @staticmethod
    def _extra_for(widget, extras):
        """``(conditions to add, True when a cross-filter applies)`` for one widget. The clicked widget itself is not filtered."""
        crossing = extras.crossing
        extra = list(extras.leaves.get(widget.data.source, []))
        crossed = bool(crossing) and widget.id != crossing["widget_id"] and widget.data.source == crossing["model"]
        if crossed:
            extra += crossing["leaves"]
        return extra, crossed

    def _cross(self, spec, catalog, cross, extras):
        """The conditions a clicked group stands for, found again on the server (the browser only names the group)."""
        if not cross:
            return None
        if (not isinstance(cross, dict) or set(cross) - {"widget_id", "group_ref"} or not isinstance(cross.get("widget_id"), str)
                or not isinstance(cross.get("group_ref"), (list, tuple)) or len(cross["group_ref"]) > 4):
            raise BoardError("BAD_ARGUMENT", "cross", t("'cross' names a widget and the group that was clicked."))
        widget = spec.widget(cross["widget_id"])
        if widget is None:
            raise BoardError("UNKNOWN_WIDGET", "cross.widget_id", t("The dashboard has no widget '%s'.") % cross["widget_id"])
        if ((widget.interact or {}).get("on_click") or {}).get("action") != "cross_filter":
            raise BoardError("CROSS_NOT_CONFIGURED", "cross.widget_id", t("Clicking this widget does not filter the others."))
        group_ref = list(cross["group_ref"])
        if OTHERS_REF in group_ref:
            raise BoardError("DRILL_OTHERS", "cross.group_ref", t("The 'Others' group is a sum of many groups and cannot filter the others."))
        checked = Validator(catalog).validate_widget(widget, "widget")
        if checked.errors:
            raise checked.errors[0]
        widget, _note = self._variant(widget, extras)  # the group is found among the same numbers the reader sees
        _model, plan = self._plan(widget, catalog, extras.leaves.get(widget.data.source, []))
        groups = runner_lib.Runner(self.env).run(replace(plan, others=False, totals=False, fill=None, compare=None, auto_others=False)).groups
        try:
            group = drill_lib.find_group(groups, plan.dims, group_ref, FrameBuilder.dim_ref)
        except BoardError as error:
            raise BoardError("CROSS_EMPTY", "cross.group_ref", t("There is nothing behind this point to filter the others by.")) from error
        found = [list(item) if isinstance(item, (list, tuple)) else item for item in (group.get("__extra_domain") or [])]
        return {"widget_id": widget.id, "model": widget.data.source, "leaves": found}

    @api.model
    def _filter_options(self, spec, filter_id, query=""):
        """``[{"value", "label"}]`` a reader may choose from for one filter of a dashboard, with the reader's own rights."""
        item = next((f for f in spec.filters if f.get("id") == filter_id), None)
        if item is None or item.get("type") == "date_range":
            raise BoardError("BAD_FILTER", "filter_id", t("This dashboard has no choice filter '%s'.") % filter_id)
        if item["type"] == "company":
            return [{"value": c.id, "label": c.name} for c in self.env.user.company_ids if query.lower() in c.name.lower()]
        model_name, field_name = next(iter(item["applies_to"].items()))
        field = EnvCatalog(self.env).model(model_name).field(field_name)
        if field.type == "selection":
            return [{"value": key, "label": label} for key, label in field.selection if query.lower() in str(label).lower()]
        found = self.env[field.relation].name_search(query, limit=board_filters.MAX_CHOICES)
        return [{"value": record_id, "label": name} for record_id, name in found]

    def _run_widget(self, widget, catalog, path="widget", explain=False, extra=(), crossed=False, filters=(), note=None) -> dict:
        try:
            checked = Validator(catalog).validate_widget(widget, path, filters)
            if checked.errors:
                return {"error": checked.errors[0].to_dict(), "errors": [e.to_dict() for e in checked.errors]}
            model, plan = self._plan(widget, catalog, extra, crossed)
            runner = runner_lib.Runner(self.env)
            raw = runner.run(plan)
            currency, more = self._currency_meta(plan, model, runner)
            warnings = list(checked.warnings) + more
            if plan.compare_skipped and not any(w.code == "COMPARE_NO_PERIOD" for w in warnings):  # the validator may have said so already
                warnings.append(BoardWarning("COMPARE_UNAVAILABLE", path + ".data.compare", plan.compare_skipped))
            frame = FrameBuilder().build(plan, raw.groups, raw.total, currency, warnings, raw.compare_groups)
            result = {"frame": frame.to_dict()}
            if explain:
                result["explain"] = ExplainBuilder(self._resolve_names).build(widget, model, plan, currency, warnings, note)
            return result
        except BoardError as error:
            return {"error": error.to_dict()}
        except Exception:  # noqa: BLE001 - deliberate boundary: a bug in one widget must not take the whole page down
            _logger.exception("Widget %s could not be computed", widget.id)
            return {"error": BoardError(
                "INTERNAL", path, t("This widget could not be computed because of an internal error. The details are in the server log.")).to_dict()}

    def _currency_meta(self, plan, model, runner):
        """Currency to show next to money, plus a warning when currencies were mixed."""
        if not any(m.type == "monetary" for m in plan.measures):
            return None, []
        company_currency = self.env.company.currency_id
        shown = company_currency
        if not model.is_report and "currency_id" in model.fields:
            ids = runner.currency_ids(plan)
            if len(ids) > 1:
                return {"mixed": True}, [BoardWarning(
                    "MIXED_CURRENCY", "data",
                    t("The amounts are in different currencies and were added without conversion, so the total is not reliable."))]
            if len(ids) == 1:
                shown = self.env["res.currency"].browse(ids[0])
        return {"symbol": shown.symbol, "position": shown.position}, []

    def _resolve_names(self, model_name, ids):
        """Names for ids shown in the explanation; an id the reader may not see stays a bare number."""
        try:
            return [r.display_name for r in self.env[model_name].browse(ids).exists()]
        except AccessError:
            return ["#%s" % i for i in ids]

    # -- drill-down ------------------------------------------------------------------

    @api.model
    def _drill_spec(self, raw, widget_id, group_ref, filter_values=None, cross=None) -> dict:
        """The records behind one clicked group of one widget, read with the caller's rights (and the same filters the chart had)."""
        spec = Spec.from_raw(raw)
        widget = spec.widget(widget_id)
        if widget is None:
            raise BoardError("UNKNOWN_WIDGET", "widget_id", t("The dashboard has no widget '%s'.") % widget_id)
        catalog = EnvCatalog(self.env)
        checked = Validator(catalog).validate_widget(widget, "widget")
        if checked.errors:
            raise checked.errors[0]
        config = drill_lib.parse(widget.interact)
        if config is None:
            raise BoardError("DRILL_NOT_CONFIGURED", "widget_id", t("Clicking this widget does not open records."))
        if isinstance(group_ref, (list, tuple)) and OTHERS_REF in group_ref:
            raise BoardError("DRILL_OTHERS", "group_ref", t("The 'Others' group is a sum of many groups and cannot be opened."))

        extras = self._extras(spec, catalog, filter_values, cross)
        extra, crossed = self._extra_for(widget, extras)
        widget, _note = self._variant(widget, extras)
        _model, plan = self._plan(widget, catalog, extra, crossed)
        runner = runner_lib.Runner(self.env)
        groups = runner.run(replace(plan, others=False, totals=False, fill=None, compare=None, auto_others=False)).groups
        target = catalog.model(config.model)
        try:
            group = drill_lib.find_group(groups, plan.dims, group_ref, FrameBuilder.dim_ref)
        except BoardError:
            # an empty day that gap filling added is a real point on the chart, with no records behind it
            if plan.fill is not None and group_ref in FrameBuilder().build(plan, groups).meta["group_refs"]:
                return drill_lib.empty_result(config, target)
            raise
        domain = drill_lib.translate_domain(list(plan.domain) + list(group.get("__extra_domain") or []), config.map, target)
        records, total = runner.fetch(config.model, domain, list(config.columns), drill_lib.MAX_DRILL_ROWS, plan.tz)
        infos = [target.field(c) for c in config.columns]
        return {
            "model": config.model,
            "open_as": config.open_as,
            "columns": drill_lib.columns_meta(config, target),
            "rows": [[drill_lib.format_cell(info, rec[info.name], plan.tz) for info in infos] for rec in records],
            "ids": [rec["id"] for rec in records],
            "total": total,
            "truncated": total > len(records),
            "action": {
                "type": "ir.actions.act_window", "name": target.label, "res_model": config.model,
                "views": [[False, "list"], [False, "form"]], "domain": domain, "target": "current",
            },
        }
