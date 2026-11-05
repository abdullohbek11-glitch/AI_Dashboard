"""Conversations, messages and the audit log of tool calls.

Users own their conversations but never write messages or tool-call rows by hand: the engine writes them
(the model's own history is replayed to the vendor, and the log is evidence), so the user has read-only
access to both. The engine writes them with ``sudo()``: bookkeeping rows, no business data is read that way.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

STALE_AFTER = timedelta(minutes=4)
MAX_QUESTION = 8000
MAX_MENTIONS = 5
CONTEXT_KEYS = ("model", "res_id", "view_type", "title", "mentions", "choice")
CHOICE_TEXT = "I chose the record named in mentioned_records."


class LevelixAiConversation(models.Model):
    _name = "levelix.ai.conversation"
    _description = "Levelix AI Conversation"
    _order = "write_date desc, id desc"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    message_ids = fields.One2many("levelix.ai.message", "conversation_id")
    active = fields.Boolean(default=True)

    # -- what the chat page calls -------------------------------------------------------------------------

    @api.model
    def lx_bootstrap(self, context=None):
        """Everything the chat needs to open: readiness, suggestions, recent conversations."""
        engine = self.env["levelix.ai.engine"]
        return {
            "configured": engine._is_configured(),
            "is_admin": self.env.user.has_group("base.group_system"),
            "privacy": engine._privacy(),
            "suggestions": self.env["levelix.ai.tools"]._suggestions(self._clean_context(context)),
            "conversations": [{"id": c.id, "name": c.name} for c in self.search([("user_id", "=", self.env.uid)], limit=20)],
        }

    @api.model
    def lx_suggestions(self, context=None):
        return self.env["levelix.ai.tools"]._suggestions(self._clean_context(context))

    @api.model
    def _clean_context(self, context):
        """The screen the question comes from. Only known keys, plain values: it ends up in a prompt."""
        if not isinstance(context, dict):
            return {}
        clean = {}
        for key in CONTEXT_KEYS:
            value = context.get(key)
            if key in ("model", "view_type", "title") and isinstance(value, str):
                clean[key] = value[:80]
            elif key == "res_id" and isinstance(value, int) and not isinstance(value, bool):
                clean[key] = value
            elif key == "choice" and value is True:  # a button the assistant offered was pressed
                clean[key] = True
            elif key == "mentions" and isinstance(value, list):
                clean[key] = [
                    {"model": m["model"][:80], "id": m["id"]} for m in value[:MAX_MENTIONS]
                    if isinstance(m, dict) and isinstance(m.get("model"), str) and isinstance(m.get("id"), int) and not isinstance(m["id"], bool)
                ]
        return clean

    @api.model
    def lx_send(self, conversation_id, text, context=None):
        """Store the question and start answering it; the answer arrives over the bus."""
        if not isinstance(text, str) or not text.strip():
            raise UserError(self.env._("Type a question first."))
        if conversation_id and (isinstance(conversation_id, bool) or not isinstance(conversation_id, int)):
            raise UserError(self.env._("Unknown conversation."))
        text = text.strip()[:MAX_QUESTION]
        engine = self.env["levelix.ai.engine"]
        engine._check_ready()
        conversation = self.browse(conversation_id).exists() if conversation_id else self.browse()
        if conversation_id and not conversation:
            raise UserError(self.env._("Unknown conversation."))
        if conversation:
            conversation.check_access("write")
            if conversation.message_ids.filtered(lambda m: m.state == "streaming" and not m._is_stale()):
                raise UserError(self.env._("Wait for the current answer to finish."))
        else:
            conversation = self.create({"name": text[:60]})
        Message = self.env["levelix.ai.message"].sudo()  # bookkeeping rows; the conversation was checked above
        context = self._clean_context(context)
        # In structure-only mode a pressed choice button must not carry the record's name to the vendor as text:
        # the screen shows the name, the vendor gets the id in the context line.
        said = CHOICE_TEXT if context.get("choice") and context.get("mentions") and engine._privacy() == "schema" else text
        question = Message.create({
            "conversation_id": conversation.id, "role": "user", "text": text,
            "llm_content": [{"role": "user", "content": [
                {"type": "text", "text": f"{engine._context_line(context)}\n\n{said}"},
            ]}],
        })
        answer = Message.create({"conversation_id": conversation.id, "role": "assistant", "state": "streaming"})
        conversation.write({"name": conversation.name})  # bumps write_date for the ordering
        engine._launch(answer)
        return {
            "conversation": {"id": conversation.id, "name": conversation.name},
            "messages": [question._lx_payload(), answer._lx_payload()],
        }

    def lx_load(self):
        self.ensure_one()
        return {
            "conversation": {"id": self.id, "name": self.name},
            "messages": [m._lx_payload() for m in self.message_ids.sorted("id")],
        }

    def lx_archive(self):
        self.write({"active": False})
        return True


class LevelixAiMessage(models.Model):
    _name = "levelix.ai.message"
    _description = "Levelix AI Message"
    _order = "id"

    conversation_id = fields.Many2one("levelix.ai.conversation", required=True, index=True, ondelete="cascade")
    user_id = fields.Many2one(related="conversation_id.user_id", store=True, index=True)
    company_id = fields.Many2one(related="conversation_id.company_id", store=True)
    role = fields.Selection([("user", "User"), ("assistant", "Assistant")], required=True)
    state = fields.Selection([("streaming", "Answering"), ("done", "Done"), ("error", "Failed")], default="done", required=True)
    text = fields.Text()
    blocks = fields.Json()
    explain = fields.Json()
    error = fields.Char()
    # neutral provider messages produced by this row, replayed as history
    llm_content = fields.Json()
    provider = fields.Char()
    model = fields.Char()
    tokens_in = fields.Integer()
    tokens_out = fields.Integer()
    tokens_cached = fields.Integer()
    duration_ms = fields.Integer()
    tool_call_ids = fields.One2many("levelix.ai.tool.call", "message_id")

    def _is_stale(self):
        return self.state == "streaming" and self.write_date < fields.Datetime.now() - STALE_AFTER

    def _lx_payload(self):
        self.ensure_one()
        stale = self._is_stale()
        return {
            "id": self.id,
            "conversation_id": self.conversation_id.id,
            "role": self.role,
            "state": "error" if stale else self.state,
            "text": self.text or "",
            "blocks": self.blocks or [],
            "explain": self.explain or [],
            "error": self.env._("The answer was interrupted. Ask again.") if stale else (self.error or ""),
        }


class LevelixAiToolCall(models.Model):
    """Evidence of what the assistant did for a user: one row per tool call. Never holds a key."""

    _name = "levelix.ai.tool.call"
    _description = "Levelix AI Tool Call"
    _order = "id desc"

    message_id = fields.Many2one("levelix.ai.message", required=True, index=True, ondelete="cascade")
    user_id = fields.Many2one(related="message_id.user_id", store=True, index=True)
    company_id = fields.Many2one(related="message_id.company_id", store=True)
    name = fields.Char(required=True)
    res_model = fields.Char("Model")
    arguments = fields.Json()
    result_size = fields.Integer()
    record_count = fields.Integer()
    is_error = fields.Boolean()
    error = fields.Char()
    duration_ms = fields.Integer()
    privacy = fields.Char(help="Privacy mode in force when the tool ran: what the model was allowed to see.")
