from odoo import api, models


class LevelixAiConversation(models.Model):
    _inherit = "levelix.ai.conversation"

    @api.model
    def _pinned_extra(self, model, res_id):
        """The chat in which a dashboard was made belongs to it, first of all."""
        found = super()._pinned_extra(model, res_id)
        if model == "levelix.board":
            board = self.env["levelix.board"].browse(res_id).exists()
            if board and board.source_conversation_id:
                found |= board.source_conversation_id
        return found
