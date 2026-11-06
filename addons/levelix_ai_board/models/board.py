from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.levelix_board.lib.errors import BoardError, SpecInvalid
from odoo.addons.levelix_board.models.env_catalog import EnvCatalog

from ..lib import from_chat

DEFAULT_MAX_WIDGETS = 8
MAX_NAME = 80


class LevelixBoard(models.Model):
    _inherit = "levelix.board"

    source_conversation_id = fields.Many2one(
        "levelix.ai.conversation", string="Built in conversation", ondelete="set null", copy=False, index=True,
        help="The chat this dashboard was built in. A draft is rebuilt by further questions of the same conversation.")

    # -- keeping a chat answer as a dashboard ------------------------------------------------------------------

    @api.model
    def lx_save_chat_answer(self, message_id, name=None):
        """The charts, numbers and tables of one assistant answer become a dashboard of the caller.

        The browser names only the answer; the queries come from what the server stored, never from the browser. Pressing
        the button twice opens the dashboard that was made the first time. Widgets that cannot be kept are left out and said so.
        """
        if isinstance(message_id, bool) or not isinstance(message_id, int):
            raise UserError(self.env._("Unknown answer."))
        if name is not None and (not isinstance(name, str) or len(name) > MAX_NAME):
            raise UserError(self.env._("The name must be text of up to %d characters.", MAX_NAME))
        message = self.env["levelix.ai.message"].browse(message_id).exists()
        try:
            message.check_access("read")
        except AccessError:
            message = message.browse()
        if not message or message.role != "assistant" or message.user_id != self.env.user:
            raise UserError(self.env._("Unknown answer."))
        blocks = list(message.blocks or [])
        offer = next((b for b in blocks if b.get("type") == "save_offer"), None)
        if offer is None:
            raise UserError(self.env._("There is nothing in this answer to keep as a dashboard."))
        if offer.get("board_id"):
            board = self.browse(offer["board_id"]).exists()
            if board and board.active:
                return self._lx_saved(board, [])
        limit = int(self.env["levelix.ai.engine"]._param("max_widgets", str(DEFAULT_MAX_WIDGETS)) or DEFAULT_MAX_WIDGETS)
        catalog = EnvCatalog(self.env)

        def is_date(model_name, field_name):
            model = catalog.model(model_name)
            field = model.field(field_name.split(".")[0]) if model else None
            return bool(field and field.is_temporal)

        title = (name or "").strip() or self._lx_default_name(message, blocks)
        spec, notes = from_chat.spec_from_blocks(blocks, title, is_date, limit)
        clean = self._lx_clean(spec, notes)
        board = self.with_context(lx_origin="ai", lx_note=self.env._("Saved from the chat")).create({
            "name": title, "spec": clean, "state": "active", "source_conversation_id": message.conversation_id.id})
        offer["board_id"] = board.id
        message.sudo().write({"blocks": blocks})  # bookkeeping: the button shows "Saved" when the chat is opened again
        return self._lx_saved(board, notes)

    def _lx_default_name(self, message, blocks):
        titles = [b.get("title") for b in blocks if from_chat.savable(b) and b.get("title")]
        return (titles[0] if len(titles) == 1 else message.conversation_id.name or self.env._("Chat answer"))[:MAX_NAME]

    def _lx_clean(self, spec, notes):
        """The spec as it will be stored. A widget the checks refuse is left out (and noted); with none left there is nothing to keep."""
        engine = self.env["levelix.board.engine"]
        for _attempt in range(len(spec["widgets"]) + 1):
            if not spec["widgets"]:
                break
            try:
                clean, _warnings = engine._normalise_spec(spec)
                return clean
            except SpecInvalid as error:
                bad = {int(e.path.split("]")[0].split("[")[1]) for e in error.errors if e.path.startswith("widgets[")}
                if not bad:
                    raise
                for index in sorted(bad, reverse=True):
                    gone = spec["widgets"].pop(index)
                    notes.append("%s: left out (%s)" % (gone.get("title") or gone["id"], next(e.detail for e in error.errors if e.path.startswith("widgets[%d]" % index))))
            except BoardError:
                raise
        raise UserError(self.env._("These results cannot be kept as a dashboard: %s", "; ".join(notes) or self.env._("nothing could be saved")))

    def _lx_saved(self, board, notes):
        return {"board_id": board.id, "name": board.name, "widgets": len((board.spec or {}).get("widgets", [])), "notes": notes}
