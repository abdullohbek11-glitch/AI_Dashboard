"""Public RPC surface of a dashboard (``lx_*``), called by the browser.

Every method checks its arguments, finds the board with the caller's own rights
(a board the caller may not see is reported as missing) and never uses ``sudo``.
The heavy lifting is in ``levelix.board.engine``.
"""
from odoo import api, models
from odoo.exceptions import AccessError

from ..lib import versions as versions_lib
from ..lib.errors import BoardError
from ..lib.patch import MAX_OPS, apply_patch
from ..lib.i18n import t
from ..lib.spec import MAX_WIDGETS, SHAPES, Spec, Widget
from ..lib.validator import allowed_aggregates
from .env_catalog import EnvCatalog

LIST_LIMIT = 500
MAX_FILTER_VALUES = 20
HISTORY_LIMIT = 200
MAX_SHARE_GROUPS = 20
GRID_COLUMNS = 24
GRID_MAX_ROWS = 400
MAX_NAME = 80
MAX_NOTE = 500


def _bad_argument(name, message):
    return BoardError("BAD_ARGUMENT", name, message)


def _check_base(board, base_version):
    """Optimistic locking: a save that was made from an older version than the stored one would overwrite someone else's change."""
    if base_version is None:
        return
    if isinstance(base_version, bool) or not isinstance(base_version, int):
        raise _bad_argument("base_version", t("'base_version' must be the version number the editor started from."))
    if base_version != board.version:
        raise BoardError(
            "STALE_VERSION", "base_version",
            t("This dashboard was changed since you opened it (it is now version %(now)d, you have version %(yours)d). Reload it, then make your change again.")
            % {"now": board.version, "yours": base_version})


def _check_layout(layout, board_widgets):
    """``{widget id: {x, y, w, h}}`` for widgets that exist, inside the 24-column grid."""
    if not isinstance(layout, dict) or not layout or len(layout) > MAX_WIDGETS:
        raise _bad_argument("layout", t("'layout' maps widget ids to {x, y, w, h}."))
    known = {w.get("id") for w in board_widgets}
    out = {}
    for wid, cell in layout.items():
        if wid not in known:
            raise BoardError("UNKNOWN_WIDGET", "layout", t("The dashboard has no widget '%s'.") % wid)
        if not isinstance(cell, dict) or set(cell) != {"x", "y", "w", "h"} or not all(
                isinstance(v, int) and not isinstance(v, bool) for v in cell.values()):
            raise _bad_argument("layout", t("A place is {x, y, w, h}, whole numbers."))
        if not (0 <= cell["x"] < GRID_COLUMNS and 1 <= cell["w"] <= GRID_COLUMNS and cell["x"] + cell["w"] <= GRID_COLUMNS
                and 0 <= cell["y"] <= GRID_MAX_ROWS and 1 <= cell["h"] <= 60):
            raise _bad_argument("layout", t("A widget must fit the %d columns of the page.") % GRID_COLUMNS)
        out[wid] = dict(cell)
    return out


def _check_widget_ids(widget_ids):
    if widget_ids is None:
        return None
    if not isinstance(widget_ids, (list, tuple)) or len(widget_ids) > MAX_WIDGETS or not all(isinstance(w, str) for w in widget_ids):
        raise _bad_argument("widget_ids", t("'widget_ids' must be a list of up to %d widget ids.") % MAX_WIDGETS)
    return list(widget_ids)


def _check_filter_inputs(filter_values, cross):
    """Shape of what the browser sends along: the reader's filter choices and an optional cross-filter."""
    if filter_values is not None and (not isinstance(filter_values, dict) or len(filter_values) > MAX_FILTER_VALUES):
        raise _bad_argument("filter_values", t("'filter_values' maps a filter id to the chosen value."))
    if cross is not None and not isinstance(cross, dict):
        raise _bad_argument("cross", t("'cross' names a widget and the group that was clicked."))


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
            group_ids=board.group_ids.ids,
            own_rights=board.user_id != self.env.user,  # the numbers follow the viewer's rights, not the owner's
        )

    @api.model
    def lx_run(self, board_id, widget_ids=None, filter_values=None, explain=False, cross=None):
        """Frames of some (or all) widgets, computed with the caller's rights and the reader's filter choices."""
        board = self._lx_board(board_id)
        ids = _check_widget_ids(widget_ids)
        _check_filter_inputs(filter_values, cross)
        out = self.env["levelix.board.engine"]._run_spec(board.spec, ids, bool(explain), filter_values, cross)
        out["version"] = board.version
        return out

    @api.model
    def lx_explain(self, board_id, widget_ids=None, filter_values=None, cross=None):
        """The "what did I do" lines of some (or all) widgets."""
        out = self.lx_run(board_id, widget_ids, filter_values, True, cross)["widgets"]
        return {wid: ({"explain": res["explain"]} if "explain" in res else {"error": res["error"]}) for wid, res in out.items()}

    @api.model
    def lx_drill(self, board_id, widget_id, group_ref, filter_values=None, cross=None):
        """The records behind one clicked group. The browser names the group; the server builds the domain."""
        board = self._lx_board(board_id)
        if not isinstance(widget_id, str) or not widget_id:
            raise _bad_argument("widget_id", t("'widget_id' must be a widget id."))
        _check_filter_inputs(filter_values, cross)
        return self.env["levelix.board.engine"]._drill_spec(board.spec, widget_id, group_ref, filter_values, cross)

    @api.model
    def lx_filter_options(self, board_id, filter_id, query=""):
        """What a reader may choose from for one choice filter (the records or values they are allowed to see)."""
        board = self._lx_board(board_id)
        if not isinstance(filter_id, str) or not isinstance(query, str) or len(query) > 60:
            raise _bad_argument("filter_id", t("'filter_id' must be a filter id and 'query' short text."))
        spec = Spec.from_raw(board.spec)
        return self.env["levelix.board.engine"]._filter_options(spec, filter_id, query)

    # -- writing --------------------------------------------------------------------------

    def _lx_check_note(self, note):
        if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE):
            raise _bad_argument("note", t("'note' must be text of up to %d characters.") % MAX_NOTE)

    def _lx_store(self, board, spec, note):
        """Validate the spec as the caller and store it as a new version (nothing happens if it did not change)."""
        clean, warnings = self.env["levelix.board.engine"]._normalise_spec(spec)
        before = board.version
        board.with_context(lx_note=note, lx_origin="manual").write({"spec": clean})
        return {"version": board.version, "changed": board.version != before, "warnings": warnings}

    @api.model
    def lx_save(self, board_id, spec, note=None, base_version=None):
        """Validate the spec as the caller and store it as a new version. ``base_version``: the version the editor started
        from; a newer stored version means someone else saved meanwhile, and nothing is overwritten."""
        board = self._lx_board(board_id, "write")
        if not isinstance(spec, dict):
            raise _bad_argument("spec", t("'spec' must be an object."))
        self._lx_check_note(note)
        _check_base(board, base_version)
        return self._lx_store(board, spec, note)

    @api.model
    def lx_apply_patch(self, board_id, patch, note=None, base_version=None):
        """Change the spec with a small patch (add / replace / remove). The whole spec is checked again afterwards."""
        board = self._lx_board(board_id, "write")
        if not isinstance(patch, list) or len(patch) > MAX_OPS:
            raise _bad_argument("patch", t("'patch' must be a list of up to %d operations.") % MAX_OPS)
        self._lx_check_note(note)
        _check_base(board, base_version)
        return self._lx_store(board, apply_patch(board.spec, patch), note or t("Changed by a patch"))

    @api.model
    def lx_save_layout(self, board_id, layout, base_version=None):
        """Where the widgets sit and how big they are: only the ``grid`` of existing widgets changes, nothing else."""
        board = self._lx_board(board_id, "write")
        cells = _check_layout(layout, (board.spec or {}).get("widgets", []))
        _check_base(board, base_version)
        spec = dict(board.spec, widgets=[dict(w, grid=cells[w["id"]]) if w.get("id") in cells else w for w in board.spec["widgets"]])
        return self._lx_store(board, spec, t("Layout changed"))

    # -- history, sharing, copies, archive ---------------------------------------------------------------------

    @api.model
    def lx_versions(self, board_id):
        """The saved states of a dashboard, newest first, each with what changed since the one before. Owner and managers only."""
        board = self._lx_board(board_id)
        rows = self.env["levelix.board.version"].search([("board_id", "=", board.id)], order="version desc", limit=HISTORY_LIMIT)
        if not rows and board.user_id != self.env.user:
            raise BoardError("NO_ACCESS", "board_id", t("Only the owner can see the history of a dashboard."))
        by_number = {r.version: r for r in rows}
        out = []
        for row in rows:
            before = by_number.get(row.version - 1)
            out.append({
                "version": row.version, "current": row.version == board.version, "author": row.author_id.name or "",
                "date": row.create_date.isoformat(sep=" ") if row.create_date else "", "origin": row.origin, "note": row.note or "",
                "widgets": len((row.spec or {}).get("widgets", [])),
                "changes": versions_lib.summarize(before.spec if before else None, row.spec),
            })
        return out

    @api.model
    def lx_restore(self, board_id, version, base_version=None):
        """Bring an earlier state back. It becomes a NEW version, so the history never loses anything."""
        board = self._lx_board(board_id, "write")
        if isinstance(version, bool) or not isinstance(version, int):
            raise _bad_argument("version", t("'version' must be a version number."))
        row = self.env["levelix.board.version"].search([("board_id", "=", board.id), ("version", "=", version)], limit=1)
        if not row:
            raise BoardError("NOT_FOUND", "version", t("This dashboard has no version %d.") % version)
        _check_base(board, base_version)
        engine = self.env["levelix.board.engine"]
        clean, _warnings = engine._normalise_spec(row.spec)  # checked again: a field may be gone since
        before = board.version
        board.with_context(lx_note=t("Restored version %d") % version, lx_origin="restore").write({"spec": clean})
        return {"version": board.version, "changed": board.version != before, "warnings": _warnings}

    @api.model
    def lx_share_options(self):
        """The groups a dashboard may be shared with: the access groups of the apps (no portal, no technical ones)."""
        groups = self.env["res.groups"].search([("privilege_id", "!=", False), ("share", "=", False)], order="full_name", limit=200)
        return [{"id": g.id, "name": g.full_name or g.name} for g in groups]

    @api.model
    def lx_share(self, board_id, mode, group_ids=None):
        """Who else may open the dashboard: ``private``, ``groups`` (with ``group_ids``) or ``company``. Owner and managers only.

        Readers calculate with their own rights, so sharing never shows anyone numbers they could not see themselves."""
        board = self._lx_board(board_id, "write")
        if mode not in ("private", "groups", "company"):
            raise _bad_argument("mode", t("'mode' is 'private', 'groups' or 'company'."))
        if board.state != "active" and mode != "private":
            raise BoardError("NOT_KEPT", "mode", t("Keep the dashboard first; a draft can be shared once it is kept."))
        groups = self.env["res.groups"]
        if mode == "groups":
            if (not isinstance(group_ids, (list, tuple)) or not group_ids or len(group_ids) > MAX_SHARE_GROUPS
                    or not all(isinstance(g, int) and not isinstance(g, bool) for g in group_ids)):
                raise _bad_argument("group_ids", t("Choose between 1 and %d groups.") % MAX_SHARE_GROUPS)
            allowed = {o["id"] for o in self.lx_share_options()}
            if not set(group_ids) <= allowed:
                raise _bad_argument("group_ids", t("Some of these groups cannot be chosen."))
            groups = groups.browse(group_ids)
        board.write({"share_mode": mode, "group_ids": [(6, 0, groups.ids)]})
        return board._lx_card()

    @api.model
    def lx_clone(self, board_id, name=None):
        """A copy of a dashboard the caller can open (their own or a shared one), owned by them and private."""
        board = self._lx_board(board_id)
        if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME):
            raise _bad_argument("name", t("The name must be text of up to %d characters.") % MAX_NAME)
        copy_name = (name or t("%s (copy)") % board.name).strip()[:MAX_NAME]
        spec = {k: v for k, v in board.spec.items() if k != "uncertain"}  # the assistant's options belong to the original
        spec["title"] = copy_name  # the page shows the spec's title: a copy must not look like the original
        copy = self.with_context(lx_note=t("Copy of «%s»") % board.name, lx_origin="manual").create({
            "name": copy_name, "spec": spec, "state": "active", "share_mode": "private"})
        return copy._lx_card()

    @api.model
    def lx_archive(self, board_id):
        """Put a dashboard away. It disappears from the lists; an administrator can bring it back from Manage."""
        board = self._lx_board(board_id, "write")
        board.write({"active": False})
        return True

    @api.model
    def lx_meta(self):
        """What an editor needs to know about widget types: how many axes and measures each takes."""
        return {"shapes": {k: {"dimensions": [v[0], v[1]], "measures": [v[2], v[3]]} for k, v in SHAPES.items()}, "grid_columns": GRID_COLUMNS}

    @api.model
    def lx_apply_uncertain(self, board_id, index):
        """Press one of the options the assistant was unsure about: its ready patch is applied, no AI involved.

        The patch comes from the stored spec, never from the browser. Options that no longer fit are dropped.
        """
        board = self._lx_board(board_id, "write")
        items = (board.spec or {}).get("uncertain") or []
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(items):
            raise _bad_argument("index", t("There is no such option."))
        patched = apply_patch(board.spec, items[index]["patch"])
        engine = self.env["levelix.board.engine"]
        # Options point at widgets by position. If this one added or removed a widget the positions moved and the
        # others would hit the wrong widget, so they go; otherwise keep those that still make a valid dashboard.
        same_widgets = [w["id"] for w in board.spec["widgets"]] == [w["id"] for w in patched["widgets"]]
        patched["uncertain"] = [
            item for position, item in enumerate(items)
            if same_widgets and position != index and engine._still_fits(dict(patched, uncertain=[item]))]
        if not patched["uncertain"]:
            del patched["uncertain"]
        return self._lx_store(board, patched, items[index]["text"][:MAX_NOTE])

    @api.model
    def lx_activate(self, board_id):
        """Keep a draft: it becomes a normal dashboard in the owner's list."""
        board = self._lx_board(board_id, "write")
        board.write({"state": "active"})
        return board._lx_card()

    # -- what the "add a widget" form needs -----------------------------------------------------------------------------

    DIMENSION_TYPES = ("selection", "many2one", "date", "datetime", "boolean")
    MEASURE_TYPES = ("monetary", "float", "integer")

    @api.model
    def lx_sources(self):
        """The reporting models the caller may read: the usual source of a widget."""
        catalog = EnvCatalog(self.env)
        out = []
        for name in sorted(self.env.registry):
            model = self.env[name]
            if model._auto or model._abstract or model._transient or not (name.endswith(".report") or name.startswith("report.")):
                continue
            info = catalog.model(name)
            if info is not None and info.accessible:
                out.append({"model": name, "label": info.label})
        return sorted(out, key=lambda o: o["label"])[:60]

    @api.model
    def lx_fields(self, model_name):
        """What a widget on this model can be grouped by and what it can measure, for the caller."""
        if not isinstance(model_name, str):
            raise _bad_argument("model", t("'model' must be a model name."))
        info = EnvCatalog(self.env).model(model_name)
        if info is None or not info.accessible:
            raise BoardError("NO_ACCESS", "model", t("You are not allowed to read '%s'.") % model_name)
        fields = sorted(info.fields.values(), key=lambda f: f.label)
        state = info.field("state")
        return {
            "model": model_name, "label": info.label,
            "dimensions": [{"name": f.name, "label": f.label, "type": f.type} for f in fields
                           if f.store and f.groupable and f.type in self.DIMENSION_TYPES and not f.name.startswith("__")],
            "measures": [{"name": f.name, "label": f.label, "aggregates": list(allowed_aggregates(f))} for f in fields
                         if f.store and f.type in self.MEASURE_TYPES and allowed_aggregates(f)],
            "state": {"name": "state", "values": [list(pair) for pair in state.selection]} if state is not None and state.type == "selection" else None,
        }

    @api.model
    def lx_preview_widget(self, widget):
        """Run one widget that is not saved (a new one, or one being changed) with the caller's rights: its frame or what is wrong."""
        if not isinstance(widget, dict) or not isinstance(widget.get("id"), str):
            raise _bad_argument("widget", t("'widget' must be a widget with an id."))
        engine = self.env["levelix.board.engine"]
        result = engine._validate_spec({"v": 1, "widgets": [widget]})
        if not result["ok"]:
            raise BoardError(result["errors"][0]["code"], result["errors"][0]["path"], result["errors"][0]["message"])
        return engine._run_spec({"v": 1, "widgets": [widget]})["widgets"][widget["id"]]
