"""Thin Odoo adapter: wires the pure ``lib`` pieces to the caller's environment.

The methods are private on purpose (``_run_spec`` ...): they are the building
blocks; the public RPC surface (``lx_*``) arrives with the dashboard model and
checks rights per call.
"""
from datetime import datetime

from odoo import api, models
from odoo.tools import get_lang

from ..lib import runner as runner_lib
from ..lib.errors import BoardError, BoardWarning
from ..lib.explain import ExplainBuilder
from ..lib.frame import FrameBuilder
from ..lib.i18n import t
from ..lib.planner import Planner
from ..lib.spec import Spec
from ..lib.validator import Validator
from .env_catalog import EnvCatalog


class LevelixBoardEngine(models.AbstractModel):
    _name = "levelix.board.engine"
    _description = "Levelix Board query engine"

    # -- public building blocks (private names, see module docstring) --------

    @api.model
    def _validate_spec(self, raw) -> dict:
        """Structure and semantics of a whole spec. Never raises for a bad spec."""
        try:
            spec = Spec.from_raw(raw)
        except BoardError as error:
            return {"ok": False, "errors": [error.to_dict()], "warnings": []}
        return Validator(EnvCatalog(self.env)).validate_spec(spec).to_dict()

    @api.model
    def _run_spec(self, raw, widget_ids=None, explain=False) -> dict:
        """Run a spec (or some of its widgets). One widget failing does not affect the others.

        Returns ``{"widgets": {id: {"frame": {...}, "explain": [...]} | {"error": {...}}}}``.
        """
        spec = Spec.from_raw(raw)  # a structurally broken spec is a caller error
        catalog = EnvCatalog(self.env)
        out = {}
        for index, widget in enumerate(spec.widgets):
            if widget_ids is not None and widget.id not in widget_ids:
                continue
            out[widget.id] = self._run_widget(widget, catalog, "widgets[%d]" % index, explain)
        return {"widgets": out}

    # -- one widget ------------------------------------------------------------

    def _run_widget(self, widget, catalog, path="widget", explain=False) -> dict:
        try:
            checked = Validator(catalog).validate_widget(widget, path)
            if checked.errors:
                return {"error": checked.errors[0].to_dict(), "errors": [e.to_dict() for e in checked.errors]}
            model = catalog.model(widget.data.source)
            tz = self.env.context.get("tz") or self.env.user.tz or "UTC"
            week_start = int(get_lang(self.env).week_start)
            plan = Planner(catalog).plan(widget, model, tz, datetime.utcnow(), week_start)
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
        records = self.env[model_name].browse(ids).exists()
        return [r.display_name for r in records]
