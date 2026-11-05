from odoo import fields, models


class LevelixBoardVersion(models.Model):
    """One saved state of a dashboard's spec. Written on every save, never edited."""

    _name = "levelix.board.version"
    _description = "Levelix Board version"
    _order = "board_id, version desc"

    board_id = fields.Many2one("levelix.board", required=True, index=True, ondelete="cascade")
    version = fields.Integer(required=True)
    spec = fields.Json(required=True)
    author_id = fields.Many2one("res.users", default=lambda self: self.env.user, ondelete="set null")
    origin = fields.Selection(
        [("manual", "Manual"), ("ai", "AI"), ("restore", "Restore")], required=True, default="manual")
    note = fields.Char()

    _board_version_unique = models.Constraint(
        "UNIQUE(board_id, version)", "A dashboard has only one version with a given number.")
