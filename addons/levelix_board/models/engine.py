"""Thin Odoo adapter: wires the pure ``lib`` pieces to the caller's environment.

The methods are private on purpose (``_run_spec`` ...): they are the building
blocks. The public RPC surface is ``levelix.board.lx_*`` (``board_rpc.py``), which
checks the board and the arguments first and then calls these.
"""
import json
import logging
from dataclasses import replace
from datetime import datetime

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.tools import get_lang

from ..lib import drill as drill_lib
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


class LevelixBoardEngine(models.AbstractModel):
    _name = "levelix.board.engine"
    _description = "Levelix Board query engine"

    # -- validating -------------------------------------------------------------

    @api.model
    def _validate_spec(self, raw) -> dict:
        """Structure and semantics of a whole spec. Never raises for a bad spec."""
        try:
            spec = Spec.from_raw(raw)
        except BoardError as error:
            return {"ok": False, "errors": [error.to_dict()], "warnings": []}
        return Validator(EnvCatalog(self.env)).validate_spec(spec).to_dict()

    @api.model
    def _normalise_spec(self, raw):
        """``(clean_spec, warnings)`` or raise ``BoardError`` / ``SpecInvalid``: what saving a spec needs."""
        if len(json.dumps(raw, ensure_ascii=False, default=str).encode("utf-8")) > MAX_SPEC_BYTES * 2:
            raise BoardError("SPEC_TOO_LARGE", "", t("The spec is larger than %d KB.") % (MAX_SPEC_BYTES // 1024))
        spec = Spec.from_raw(raw)
        result = Validator(EnvCatalog(self.env)).validate_spec(spec)
        result.raise_if_invalid()
        return spec.to_raw(), [w.to_dict() for w in result.warnings]

    # -- running -------------------------------------------------------------------

    @api.model
    def _run_spec(self, raw, widget_ids=None, explain=False) -> dict:
        """Run a spec (or some of its widgets). One widget failing does not affect the others.

        Returns ``{"widgets": {id: {"frame": {...}, "explain": [...]} | {"error": {...}}}}``.
        ``widget_ids`` must name widgets of the spec.
        """
        spec = Spec.from_raw(raw)  # a structurally broken spec is a caller error
        if widget_ids is not None:
            unknown = [w for w in widget_ids if spec.widget(w) is None]
            if unknown:
                raise BoardError("UNKNOWN_WIDGET", "widget_ids", t("The dashboard has no widget '%s'.") % unknown[0])
        catalog = EnvCatalog(self.env)
        out = {}
        for index, widget in enumerate(spec.widgets):
            if widget_ids is not None and widget.id not in widget_ids:
                continue
            out[widget.id] = self._run_widget(widget, catalog, "widgets[%d]" % index, explain)
        return {"widgets": out}

    def _plan(self, widget, catalog):
        model = catalog.model(widget.data.source)
        tz = self.env.context.get("tz") or self.env.user.tz or "UTC"
        week_start = int(get_lang(self.env).week_start)
        return model, Planner(catalog).plan(widget, model, tz, datetime.utcnow(), week_start)

    def _run_widget(self, widget, catalog, path="widget", explain=False) -> dict:
        try:
            checked = Validator(catalog).validate_widget(widget, path)
            if checked.errors:
                return {"error": checked.errors[0].to_dict(), "errors": [e.to_dict() for e in checked.errors]}
            model, plan = self._plan(widget, catalog)
            runner = runner_lib.Runner(self.env)
            raw = runner.run(plan)
            currency, extra = self._currency_meta(plan, model, runner)
            warnings = list(checked.warnings) + extra
            frame = FrameBuilder().build(plan, raw.groups, raw.total, currency, warnings)
            result = {"frame": frame.to_dict()}
            if explain:
                result["explain"] = ExplainBuilder(self._resolve_names).build(widget, model, plan, currency, warnings)
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
    def _drill_spec(self, raw, widget_id, group_ref) -> dict:
        """The records behind one clicked group of one widget, read with the caller's rights."""
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

        _model, plan = self._plan(widget, catalog)
        runner = runner_lib.Runner(self.env)
        groups = runner.run(replace(plan, others=False, fill=None)).groups
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
