"""The tools that turn a question into a dashboard draft. The model only writes a spec (a JSON text); the server
validates it, runs every widget with the user's own rights and keeps a draft that belongs to the user.
Nothing here changes business data."""
import json
import logging

from odoo import api, models
from odoo.exceptions import UserError

from odoo.addons.levelix_board.lib import patch as patch_lib
from odoo.addons.levelix_board.lib.errors import BoardError, SpecInvalid

from ..lib import drill_defaults, json_help

_logger = logging.getLogger(__name__)

PREVIEW_ROWS = 10
MAX_REPAIRS = 3  # the first try is free; then at most three repairs
MAX_JSON_CHARS = 60000
DEFAULT_MAX_WIDGETS = 8
MAX_REPORTED_ERRORS = 12

_STRING = {"type": "string"}
GET_HINTS = {
    "name": "get_hints",
    "description": "Look up which reporting model fits the user's question and the conventions of its data (which status means 'confirmed', "
                   "the date field, the measures, how to open the records behind a chart). Call this first, with the user's own words.",
    "parameters": {"type": "object", "properties": {"query": _STRING}, "required": ["query"]},
}
PREVIEW_WIDGET = {
    "name": "preview_widget",
    "description": "Try one widget's query without saving anything. 'widget' is the widget as JSON text: {\"id\":\"w1\",\"type\":\"bar\",\"data\":{...}}. "
                   "Returns the shape of the result, warnings, or the errors to fix.",
    "parameters": {"type": "object", "properties": {"widget": {"type": "string", "description": "The widget as JSON text."}}, "required": ["widget"]},
}
BUILD_DASHBOARD = {
    "name": "build_dashboard",
    "description": "Create the dashboard draft from the complete spec (JSON text). The server checks the spec and runs every widget. "
                   "If it returns errors, fix those paths and call it again with the corrected complete spec.",
    "parameters": {"type": "object", "properties": {"spec": {"type": "string", "description": "The complete dashboard spec as JSON text."}}, "required": ["spec"]},
}
UPDATE_DASHBOARD = {
    "name": "update_dashboard",
    "description": "Change an existing dashboard with a small patch instead of rebuilding it: widget ids and positions stay. 'patch' is a JSON text "
                   "list of {op: add|replace|remove, path, value}, paths under /widgets/<index>/..., /filters, /title, /assumptions "
                   "(for example [{\"op\":\"replace\",\"path\":\"/widgets/1/type\",\"value\":\"column\"}]). "
                   "'board_id' is the dashboard (given in the context line as open dashboard or mentioned); leave it out for this chat's draft. "
                   "The server checks the result and runs every widget; if it returns errors, fix those paths and call it again.",
    "parameters": {"type": "object", "properties": {"patch": {"type": "string", "description": "The patch as JSON text."},
                                                      "board_id": {"type": "integer"}}, "required": ["patch"]},
}



class LevelixAiTools(models.AbstractModel):
    _inherit = "levelix.ai.tools"

    @api.model
    def _tool_defs(self):
        return super()._tool_defs() + [GET_HINTS, PREVIEW_WIDGET, BUILD_DASHBOARD, UPDATE_DASHBOARD]

    # -- helpers -----------------------------------------------------------------------------------------------

    @api.model
    def _json_object(self, value, what):
        """The model sends specs as JSON text (every vendor accepts that); an object is fine too."""
        if isinstance(value, str):
            if len(value) > MAX_JSON_CHARS:
                raise UserError(self.env._("The %s is too long.", what))
            try:
                value = json.loads(value)
            except ValueError as error:
                repaired = json_help.repair(value)
                if not repaired:
                    raise UserError(self.env._("The %(what)s is not valid JSON: %(error)s", what=what, error=json_help.explain(value, error))) from error
                _logger.info("Levelix AI: closed %d missing bracket(s) in the model's %s", repaired[1], what)
                value = repaired[0]
        if not isinstance(value, dict):
            raise UserError(self.env._("The %s must be a JSON object.", what))
        return value

    @staticmethod
    def _problem(error):
        return error.to_dict() if isinstance(error, BoardError) else {"path": "", "code": "BAD_SPEC", "message": str(error)}

    # -- get_hints ----------------------------------------------------------------------------------------------------

    def _tool_get_hints(self, args, message):
        found = self.env["levelix.ai.hint"]._matching(str(args.get("query") or ""))
        note = "" if found else "No hint matched. Use find_models and describe_model to look for the data."
        return {"hints": found, "note": note}, {"count": len(found)}

    @api.model
    def _to_ai_get_hints(self, result):
        return result  # conventions of the data, no data

    # -- preview_widget --------------------------------------------------------------------------------------------------

    def _tool_preview_widget(self, args, message):
        widget = drill_defaults.expand_widget(self._json_object(args.get("widget"), "widget"))
        widget.setdefault("id", "w1")
        engine = self.env["levelix.board.engine"]
        try:
            out = engine._run_spec({"v": 1, "widgets": [widget]})["widgets"][widget["id"]]
        except (BoardError, UserError) as error:
            return {"ok": False, "errors": [self._problem(error)]}, {"error": str(error)[:200]}
        if "frame" not in out:
            return {"ok": False, "errors": out.get("errors") or [out["error"]]}, {"error": (out["error"] or {}).get("message", "")[:200]}
        frame = out["frame"]
        labels = [c["label"] for c in frame["columns"]]
        return {
            "ok": True,
            "shape": "%d row%s, %d column%s (%s)" % (len(frame["rows"]), "" if len(frame["rows"]) == 1 else "s", len(labels), "" if len(labels) == 1 else "s", ", ".join(labels)),
            "rows": len(frame["rows"]),
            "columns": labels,
            "warnings": [w["text"] for w in frame["meta"]["warnings"]],
            "sample": frame["rows"][:PREVIEW_ROWS],
        }, {"model": (widget.get("data") or {}).get("source") if isinstance(widget.get("data"), dict) else False, "count": len(frame["rows"])}

    @api.model
    def _to_ai_preview_widget(self, result):
        if self.env["levelix.ai.engine"]._privacy() == "schema":
            return {k: v for k, v in result.items() if k != "sample"}  # the shape only; never a value
        return result

    # -- build_dashboard ----------------------------------------------------------------------------------------------------

    def _tool_build_dashboard(self, args, message):
        failed = self.env["levelix.ai.tool.call"].sudo().search_count(
            [("message_id", "=", message.id), ("name", "=", "build_dashboard"), ("is_error", "=", True)])
        if failed > MAX_REPAIRS:
            return {
                "ok": False, "give_up": True, "errors": [],
                "note": "The attempts are used up. Stop. Tell the user plainly that the dashboard could not be built and why, in simple words.",
            }, {"error": "gave up after %d failed attempts" % failed}
        checked = self._check_spec(drill_defaults.expand_spec(self._json_object(args.get("spec"), "spec")))
        if isinstance(checked, list):  # problems to fix
            left = max(0, MAX_REPAIRS - failed)
            result = {"ok": False, "errors": checked[:MAX_REPORTED_ERRORS], "repairs_left": left}
            if not left:  # this was the last allowed attempt: say so now, so the model can answer within its step budget
                result.update({"give_up": True, "note": "No repairs are left. Stop. Tell the user plainly that the dashboard could not be built and why, in simple words."})
            return result, {"error": "; ".join("%s: %s" % (p["path"] or "-", p["message"]) for p in checked[:3])}
        spec, ran, warnings = checked
        draft = self._keep_draft(message, spec)
        blocks = self._draft_blocks(draft, spec, ran, warnings)
        return {
            "ok": True, "board_id": draft.id, "widgets": len(spec["widgets"]),
            "warnings": [w["text"] for w in blocks[0]["warnings"]],
            "note": "The draft is on the user's screen with Keep and Change buttons. Reply in one or two sentences: what it shows and anything "
                    "the user should know. Do not list numbers.",
        }, {"model": "levelix.board", "count": len(spec["widgets"]), "blocks": blocks}

    @api.model
    def _to_ai_build_dashboard(self, result):
        return result  # ids, counts and warning texts; no data

    # -- update_dashboard ---------------------------------------------------------------------------------------------------

    def _tool_update_dashboard(self, args, message):
        failed = self.env["levelix.ai.tool.call"].sudo().search_count(
            [("message_id", "=", message.id), ("name", "=", "update_dashboard"), ("is_error", "=", True)])
        if failed > MAX_REPAIRS:
            return {"ok": False, "give_up": True, "errors": [], "note": "The attempts are used up. Stop. Tell the user plainly that the change could not be made and why."}, \
                {"error": "gave up after %d failed attempts" % failed}
        board = self._update_target(args.get("board_id"), message)
        patch = self._json_list(args.get("patch"), "patch")
        try:
            changed = patch_lib.apply_patch(board.spec, [self._expand_step(step) for step in patch])
        except BoardError as error:
            return self._update_failed([self._problem(error)], failed)
        checked = self._check_spec(changed)
        if isinstance(checked, list):
            return self._update_failed(checked, failed)
        spec, ran, warnings = checked
        values = {"spec": spec}
        if spec.get("title") and spec.get("title") != (board.spec or {}).get("title"):
            values["name"] = spec["title"][:80]
        board.with_context(lx_origin="ai", lx_note=self.env._("Changed from the chat")).write(values)
        blocks = self._draft_blocks(board, spec, ran, warnings)
        return {
            "ok": True, "board_id": board.id, "widgets": len(spec["widgets"]), "version": board.version,
            "warnings": [w["text"] for w in blocks[0]["warnings"]],
            "note": "The change is made and the dashboard is on the user's screen. Reply in one sentence: what you changed. Do not list numbers.",
        }, {"model": "levelix.board", "count": len(spec["widgets"]), "blocks": blocks}

    @api.model
    def _to_ai_update_dashboard(self, result):
        return result  # ids, counts and warning texts; no data

    def _update_failed(self, problems, failed):
        left = max(0, MAX_REPAIRS - failed)
        result = {"ok": False, "errors": problems[:MAX_REPORTED_ERRORS], "repairs_left": left}
        if not left:
            result.update({"give_up": True, "note": "No repairs are left. Stop. Tell the user plainly that the change could not be made and why."})
        return result, {"error": "; ".join("%s: %s" % (p["path"] or "-", p["message"]) for p in problems[:3])}

    def _update_target(self, board_id, message):
        """The dashboard to change: the one named (the caller must be allowed to change it), else this chat's own draft."""
        Board = self.env["levelix.board"]
        if board_id not in (None, "", False):
            try:
                return Board._lx_board(int(board_id), "write")
            except (BoardError, ValueError, TypeError) as error:
                raise UserError(str(error)) from error
        draft = Board.search([("source_conversation_id", "=", message.conversation_id.id), ("state", "=", "draft"), ("user_id", "=", self.env.uid)], limit=1)
        if not draft:
            raise UserError(self.env._("There is no dashboard to change here. Name one (board_id) or build one first."))
        return draft

    def _json_list(self, value, what):
        if isinstance(value, str):
            if len(value) > MAX_JSON_CHARS:
                raise UserError(self.env._("The %s is too long.", what))
            try:
                value = json.loads(value)
            except ValueError as error:
                repaired = json_help.repair(value)
                if not repaired:
                    raise UserError(self.env._("The %(what)s is not valid JSON: %(error)s", what=what, error=json_help.explain(value, error))) from error
                value = repaired[0]
        if not isinstance(value, list):
            raise UserError(self.env._("The %s must be a JSON list.", what))
        return value

    @staticmethod
    def _expand_step(step):
        """A widget added or replaced as a whole gets the same drill shorthand as in build_dashboard."""
        if isinstance(step, dict) and isinstance(step.get("value"), dict) and "type" in step["value"]:
            return dict(step, value=drill_defaults.expand_widget(step["value"]))
        return step

    def _check_spec(self, raw):
        """``(clean spec, results per widget, warnings)`` when the spec is good and every widget runs; else the list of problems."""
        engine = self.env["levelix.board.engine"]
        try:
            clean, warnings = engine._normalise_spec(raw)
        except SpecInvalid as error:
            return [self._problem(e) for e in error.errors]
        except BoardError as error:
            return [self._problem(error)]
        limit = int(self.env["levelix.ai.engine"]._param("max_widgets", str(DEFAULT_MAX_WIDGETS)) or DEFAULT_MAX_WIDGETS)
        if len(clean["widgets"]) > limit:
            return [{"path": "widgets", "code": "TOO_MANY_WIDGETS", "message": "A dashboard has at most %d widgets here; drop the least important." % limit}]
        if not clean["widgets"]:
            return [{"path": "widgets", "code": "BAD_SHAPE", "message": "A dashboard needs at least one widget."}]
        ran = engine._run_spec(clean, explain=True)["widgets"]  # every widget must really run, with the user's rights
        problems = []
        for widget in clean["widgets"]:
            outcome = ran[widget["id"]]
            if "error" in outcome:
                problems += outcome.get("errors") or [outcome["error"]]
        if problems:
            return problems
        for widget in clean["widgets"]:
            warnings += [dict(w, widget=widget.get("title") or widget["id"]) for w in ran[widget["id"]]["frame"]["meta"]["warnings"]]
        return clean, ran, warnings

    def _keep_draft(self, message, spec):
        """One draft per conversation: asking for a change rebuilds it; once kept, the next question makes a new one."""
        Board = self.env["levelix.board"].with_context(lx_origin="ai", lx_note=self.env._("Built from the chat"))
        conversation = message.conversation_id
        name = (spec.get("title") or (spec["widgets"][0].get("title") if spec["widgets"] else "") or self.env._("AI dashboard"))[:80]
        draft = Board.search([("source_conversation_id", "=", conversation.id), ("state", "=", "draft"), ("user_id", "=", self.env.uid)], limit=1)
        if draft:
            draft.write({"name": name, "spec": spec})
            return draft
        return Board.create({"name": name, "spec": spec, "state": "draft", "source_conversation_id": conversation.id})

    def _draft_blocks(self, draft, spec, ran, warnings):
        seen, shown = set(), []
        for warning in warnings:
            key = (warning.get("code"), warning.get("text"))
            if key not in seen:
                seen.add(key)
                shown.append({"code": warning.get("code"), "text": warning.get("text"), "widget": warning.get("widget") or ""})
        return [
            {
                "type": "board_draft", "board_id": draft.id, "title": draft.name,
                "assumptions": spec.get("assumptions") or [],
                "uncertain": [{"index": i, "text": u["text"]} for i, u in enumerate(spec.get("uncertain") or [])],
                "warnings": shown,
                "widgets": [{"id": w["id"], "title": w.get("title") or w["id"], "type": w["type"]} for w in spec["widgets"]],
            },
            {
                "type": "board_explain",
                "widgets": [{"id": w["id"], "title": w.get("title") or w["id"], "lines": ran[w["id"]].get("explain") or []} for w in spec["widgets"]],
            },
        ]
