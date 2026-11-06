import json
import logging

from odoo import api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.levelix_board.lib.errors import BoardError

from ..lib import from_chat
from ..lib import prepared as prepared_lib
from ..lib.guide import DASHBOARD_RULES

CONTEXT_SPEC_CHARS = 12000

_logger = logging.getLogger(__name__)


class LevelixAiEngine(models.AbstractModel):
    _inherit = "levelix.ai.engine"

    @api.model
    def _prompt_pieces(self):
        return super()._prompt_pieces() + [DASHBOARD_RULES]

    @api.model
    def _finish_blocks(self, answer, blocks):
        """Charts, numbers and tables the assistant calculated can be kept as a dashboard: offer it (once per answer).

        No offer when the answer already is a dashboard (the draft has its own Keep button)."""
        blocks = super()._finish_blocks(answer, blocks)
        if any(b.get("type") == "board_draft" for b in blocks):
            return blocks
        count = sum(1 for b in blocks if from_chat.savable(b))
        if not count:
            return blocks
        return blocks + [{"type": "save_offer", "message_id": answer.id, "count": count, "board_id": None}]

    @api.model
    def _context_line(self, context):
        """A dashboard the user pinned to the chat (or mentioned) is handed over with its current spec, so a change can be a small patch."""
        line = super()._context_line(context)
        extra = []
        seen = set()
        for mention in (context or {}).get("mentions") or []:
            if mention.get("model") != "levelix.board" or mention.get("id") in seen:
                continue
            seen.add(mention.get("id"))
            try:
                board = self.env["levelix.board"]._lx_board(mention["id"], "write")
            except (BoardError, AccessError, UserError):
                continue
            shown = board.spec
            if self._privacy() == "schema":  # structure only: no titles, no conditions, no values; the model still sees what to address
                shown = {"widgets": [{"id": w.get("id"), "type": w.get("type"), "source": (w.get("data") or {}).get("source"),
                                      "dimensions": [d.get("field") for d in (w.get("data") or {}).get("dimensions") or [] if isinstance(d, dict)],
                                      "measures": [m.get("field") for m in (w.get("data") or {}).get("measures") or [] if isinstance(m, dict)]}
                                     for w in board.spec.get("widgets", [])],
                         "filters": [{"id": f.get("id"), "type": f.get("type")} for f in board.spec.get("filters") or []]}
            spec = json.dumps(shown, ensure_ascii=False, separators=(",", ":"))
            if len(spec) > CONTEXT_SPEC_CHARS:
                spec = spec[:CONTEXT_SPEC_CHARS] + "…(cut)"
            extra.append('[dashboard #%d v%d state=%s] The user wants to change this dashboard (update_dashboard with board_id=%d). Spec: %s'
                         % (board.id, board.version, board.state, board.id, spec))
        return line + ("\n" + "\n".join(extra) if extra else "")

    @api.model
    def _prepared(self, text, conversation):
        """The hint and the fields of the reporting model the question is about, put right after the question.

        Without this the model spends two or three round trips (get_hints, describe_model, sometimes find_models) before it
        does anything, and every round trip costs seconds. Only the best matching hint, only once per conversation and model.
        """
        extra = super()._prepared(text, conversation)
        try:
            found = self.env["levelix.ai.hint"]._matching(text)
            if not found:
                return extra
            hint = found[0]
            marker = prepared_lib.marker(hint["model"])
            if conversation and any(marker in json.dumps(m.llm_content or []) for m in conversation.message_ids if m.role == "user"):
                return extra  # an earlier question of this chat carries it already
            described, _side = self.env["levelix.ai.tools"]._tool_describe_model({"model": hint["model"]}, None)
        except (AccessError, UserError):
            return extra
        except Exception:  # noqa: BLE001 - preparing is an optimisation: a failure here must never stop the answer
            _logger.exception("Levelix AI: could not prepare the hint")
            return extra
        return (extra + "\n\n" if extra else "") + prepared_lib.block(hint, described)
