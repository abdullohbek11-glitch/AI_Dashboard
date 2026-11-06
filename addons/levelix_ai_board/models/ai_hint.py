from odoo import api, fields, models

from ..lib import hints as hint_lib


class LevelixAiHint(models.Model):
    """A short note that tells the assistant which model answers which kind of question, and the conventions of that data.
    Modules add their own through XML data. A question without a matching hint still works: the assistant then searches."""

    _name = "levelix.ai.hint"
    _description = "Levelix AI Hint"
    _order = "sequence, id"

    name = fields.Char(required=True)
    keywords = fields.Char(required=True, help="Comma-separated words people use for this data, in any language.")
    model = fields.Char(required=True, help="The model the advice is about (usually a reporting model).")
    advice = fields.Text(required=True, help="Short, in English: which fields to use, which status means 'confirmed', what the amounts are in.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.model
    def _matching(self, query):
        """Hints that fit the question, for the models this user may read and that exist in this database."""
        rows = [
            (hint.sequence, hint.keywords, {"model": hint.model, "advice": hint.advice})
            for hint in self.search([])
            if hint.model in self.env and self.env[hint.model].has_access("read")
        ]
        return hint_lib.match(rows, query)
