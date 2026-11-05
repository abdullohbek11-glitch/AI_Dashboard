"""The dashboard record: who owns it, who may see it, the current spec."""
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..lib.errors import BoardError

EMPTY_SPEC = {"v": 1, "widgets": []}


def parse_spec_text(text):
    try:
        return json.loads(text or "")
    except ValueError as error:
        raise BoardError("BAD_SPEC", "", _("The spec is not valid JSON: %s", error)) from error


class LevelixBoard(models.Model):
    _name = "levelix.board"
    _description = "Levelix Board"
    _order = "write_date desc, id desc"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", string="Owner", required=True, default=lambda self: self.env.user, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    spec = fields.Json(default=lambda self: dict(EMPTY_SPEC), copy=True)
    spec_text = fields.Text(string="Spec (JSON)", compute="_compute_spec_text", inverse="_inverse_spec_text")
    version = fields.Integer(readonly=True, copy=False)
    state = fields.Selection([("draft", "Draft"), ("active", "Active")], required=True, default="active")
    share_mode = fields.Selection(
        [("private", "Only me"), ("groups", "Selected groups"), ("company", "Everyone in the company")],
        required=True, default="private")
    group_ids = fields.Many2many("res.groups", "levelix_board_group_rel", "board_id", "group_id", string="Shared with groups")
    active = fields.Boolean(default=True)
    version_ids = fields.One2many("levelix.board.version", "board_id", string="History", readonly=True)

    @api.constrains("share_mode", "group_ids")
    def _check_share_groups(self):
        for board in self:
            if board.share_mode == "groups" and not board.group_ids:
                raise ValidationError(_("Choose at least one group, or change who the dashboard is shared with."))

    # -- the spec as editable text (temporary form until the dashboard designer exists) --

    @api.depends("spec")
    def _compute_spec_text(self):
        for board in self:
            board.spec_text = json.dumps(board.spec, indent=2, ensure_ascii=False) if board.spec else ""

    def _inverse_spec_text(self):
        for board in self:
            board.spec = parse_spec_text(board.spec_text)

    # -- saving: every spec change is validated as the saving user and recorded --------

    @api.model_create_multi
    def create(self, vals_list):
        engine = self.env["levelix.board.engine"]
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if "spec_text" in vals:
                vals["spec"] = parse_spec_text(vals.pop("spec_text"))
            vals["spec"], _warnings = engine._normalise_spec(vals.get("spec") or dict(EMPTY_SPEC))
            vals["version"] = 1
        boards = super().create(vals_list)
        for board in boards:
            board._record_version(self.env.context.get("lx_note"), self.env.context.get("lx_origin") or "manual")
        return boards

    def write(self, vals):
        if "spec" not in vals:
            return super().write(vals)
        spec, _warnings = self.env["levelix.board.engine"]._normalise_spec(vals["spec"])
        rest = {k: v for k, v in vals.items() if k != "spec"}
        note, origin = self.env.context.get("lx_note"), self.env.context.get("lx_origin") or "manual"
        for board in self:
            if board.spec == spec:  # nothing changed: no new version
                super(LevelixBoard, board).write(rest)
                continue
            super(LevelixBoard, board).write(dict(rest, spec=spec, version=board.version + 1))
            board._record_version(note, origin)
        return True

    def _record_version(self, note, origin):
        self.ensure_one()
        self.env["levelix.board.version"].create({
            "board_id": self.id, "version": self.version, "spec": self.spec, "origin": origin, "note": (note or "")[:500],
        })
