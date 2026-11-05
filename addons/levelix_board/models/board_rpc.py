"""Public RPC surface of a dashboard (``lx_*``), called by the browser.

Every method checks its arguments, finds the board with the caller's own rights
(a board the caller may not see is reported as missing) and never uses ``sudo``.
The heavy lifting is in ``levelix.board.engine``.
"""
from odoo import api, models
from odoo.exceptions import AccessError

from ..lib.errors import BoardError
from ..lib.i18n import t
from ..lib.spec import MAX_WIDGETS

LIST_LIMIT = 500
MAX_NOTE = 500


def _bad_argument(name, message):
    return BoardError("BAD_ARGUMENT", name, message)


def _check_widget_ids(widget_ids):
    if widget_ids is None:
        return None
    if not isinstance(widget_ids, (list, tuple)) or len(widget_ids) > MAX_WIDGETS or not all(isinstance(w, str) for w in widget_ids):
        raise _bad_argument("widget_ids", t("'widget_ids' must be a list of up to %d widget ids.") % MAX_WIDGETS)
    return list(widget_ids)


def _check_no_filters(filter_values):
    if filter_values:  # dashboard filters arrive in a later phase; refuse rather than ignore silently
        raise BoardError("UNSUPPORTED", "filter_values", t("Dashboard filters are not available yet."))


class LevelixBoardRpc(models.Model):
    _inherit = "levelix.board"

    @api.model
    def _lx_board(self, board_id, mode="read"):
        if isinstance(board_id, bool) or not isinstance(board_id, int) or board_id < 1:
            raise _bad_argument("board_id", t("'board_id' must be a dashboard id."))
        board = self.browse(board_id).exists()
        try:
            board.check_access("read")
        except AccessError:
            board = self.browse()
        if not board or not board.active:
            raise BoardError("NOT_FOUND", "board_id", t("This dashboard does not exist or you cannot see it."))
        if mode == "write" and not board.has_access("write"):
            raise BoardError("NO_ACCESS", "board_id", t("You are not allowed to change this dashboard."))
        return board

    def _lx_card(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "share_mode": self.share_mode,
            "version": self.version,
            "owner": self.user_id.name,
            "is_owner": self.user_id == self.env.user,
            "can_edit": self.has_access("write"),
            "widgets": len((self.spec or {}).get("widgets", [])),
            "updated": self.write_date.isoformat(sep=" ") if self.write_date else None,
        }

    # -- reading ----------------------------------------------------------------------

    @api.model
    def lx_list(self):
        """Cards of the dashboards the caller may open."""
        return [board._lx_card() for board in self.search([], limit=LIST_LIMIT)]

    @api.model
    def lx_load(self, board_id):
        """Description and spec of a dashboard (no data)."""
        board = self._lx_board(board_id)
        return dict(
            board._lx_card(),
            spec=board.spec,
            group_names=board.group_ids.mapped("display_name"),
            own_rights=board.user_id != self.env.user,  # the numbers follow the viewer's rights, not the owner's
        )

    @api.model
    def lx_run(self, board_id, widget_ids=None, filter_values=None, explain=False):
        """Frames of some (or all) widgets, computed with the caller's rights."""
        board = self._lx_board(board_id)
        ids = _check_widget_ids(widget_ids)
        _check_no_filters(filter_values)
        out = self.env["levelix.board.engine"]._run_spec(board.spec, ids, bool(explain))
        out["version"] = board.version
        return out

    @api.model
    def lx_explain(self, board_id, widget_ids=None):
        """The "what did I do" lines of some (or all) widgets."""
        out = self.lx_run(board_id, widget_ids, None, True)["widgets"]
        return {wid: ({"explain": res["explain"]} if "explain" in res else {"error": res["error"]}) for wid, res in out.items()}

    @api.model
    def lx_drill(self, board_id, widget_id, group_ref, filter_values=None):
        """The records behind one clicked group. The browser names the group; the server builds the domain."""
        board = self._lx_board(board_id)
        if not isinstance(widget_id, str) or not widget_id:
            raise _bad_argument("widget_id", t("'widget_id' must be a widget id."))
        _check_no_filters(filter_values)
        return self.env["levelix.board.engine"]._drill_spec(board.spec, widget_id, group_ref)

    # -- writing --------------------------------------------------------------------------

    @api.model
    def lx_save(self, board_id, spec, note=None):
        """Validate the spec as the caller and store it as a new version."""
        board = self._lx_board(board_id, "write")
        if not isinstance(spec, dict):
            raise _bad_argument("spec", t("'spec' must be an object."))
        if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE):
            raise _bad_argument("note", t("'note' must be text of up to %d characters.") % MAX_NOTE)
        clean, warnings = self.env["levelix.board.engine"]._normalise_spec(spec)
        before = board.version
        board.with_context(lx_note=note, lx_origin="manual").write({"spec": clean})
        return {"version": board.version, "changed": board.version != before, "warnings": warnings}
