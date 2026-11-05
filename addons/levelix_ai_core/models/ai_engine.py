"""The conversation loop: history -> provider -> tool calls -> answer, streamed to the browser over the bus."""
import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import pytz
from psycopg2 import errors as pg_errors

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.registry import Registry
from odoo.tools import config

from ..lib import privacy, prompt
from ..providers import PROVIDERS, ProviderError

_logger = logging.getLogger(__name__)

MAX_STEPS = 8  # model <-> tool round trips per question
HISTORY_TURNS = 10
RESULT_CHARS = 12000  # what one tool result may weigh when it goes to the model
FLUSH_EVERY = 0.12
BUS_EVENT = "levelix_ai/event"
TOOL_TIMEOUT_MS = 8000
DEFAULT_DAILY_LIMIT = 200
GROUP = "levelix_ai_core.group_ai_user"


class LevelixAiEngine(models.AbstractModel):
    _name = "levelix.ai.engine"
    _description = "Levelix AI Engine"

    # ------------------------------------------------------------------
    # Configuration (read with sudo: settings, never business data)
    # ------------------------------------------------------------------
    @api.model
    def _param(self, key, default=""):
        return self.env["ir.config_parameter"].sudo().get_param(f"levelix_ai.{key}", default)

    @api.model
    def _key(self, name):
        return self._param(f"{name}_key") or config.get(f"levelix_ai_{name}_key")

    @api.model
    def _privacy(self):
        mode = self._param("privacy", privacy.MODE_AGGREGATES)
        return mode if mode in privacy.MODES else privacy.MODE_AGGREGATES

    @api.model
    def _provider(self):
        name = self._param("provider", "anthropic")
        if name not in PROVIDERS:
            raise UserError(self.env._("Choose an AI provider in the settings."))
        key = self._key(name)
        if not key:
            raise UserError(self.env._("The AI provider has no API key yet. Ask your administrator to add one in Settings."))
        try:
            temperature = float(self._param("temperature")) if self._param("temperature") else None
        except ValueError:
            temperature = None
        timeout = int(self._param("timeout", "120") or 120)
        return PROVIDERS[name](key, self._param(f"{name}_model") or None, self._param(f"{name}_base_url") or None,
                               timeout=max(5, timeout), temperature=temperature)

    @api.model
    def _is_configured(self):
        name = self._param("provider", "anthropic")
        return bool(name in PROVIDERS and self._key(name))

    @api.model
    def _day_start(self):
        """Local midnight of the user's day, as the UTC string the database holds."""
        zone = pytz.timezone(self.env.context.get("tz") or self.env.user.tz or "UTC")
        local = datetime.now(timezone.utc).astimezone(zone).replace(hour=0, minute=0, second=0, microsecond=0)
        return fields.Datetime.to_string(local.astimezone(pytz.utc).replace(tzinfo=None))

    @api.model
    def _check_ready(self):
        if not self.env.user.has_group(GROUP):
            raise AccessError(self.env._("You do not have access to the assistant."))
        self._provider()
        since = self._day_start()
        mine = [("user_id", "=", self.env.uid), ("create_date", ">=", since)]
        limit = int(self._param("daily_limit", str(DEFAULT_DAILY_LIMIT)) or 0)
        if limit and self.env["levelix.ai.message"].search_count(mine + [("role", "=", "user")]) >= limit:
            raise UserError(self.env._("You reached today's limit of %s questions.", limit))
        token_limit = int(self._param("daily_tokens", "0") or 0)
        if token_limit:
            used = sum(self.env["levelix.ai.message"].search(mine + [("role", "=", "assistant")]).mapped(lambda m: m.tokens_in + m.tokens_out))
            if used >= token_limit:
                raise UserError(self.env._("You reached today's limit of %s tokens.", token_limit))

    # ------------------------------------------------------------------
    # What the model is told
    # ------------------------------------------------------------------
    @api.model
    def _prompt_pieces(self):
        """Extra rules of other modules: ``return super()._prompt_pieces() + [MY_RULES]``."""
        return []

    @api.model
    def _context_line(self, context):
        """What the model needs to resolve "today" and "this record". Kept out of the system prompt so the
        cached prefix stays identical between turns."""
        Tools = self.env["levelix.ai.tools"]
        schema = self._privacy() == privacy.MODE_SCHEMA
        parts = [f"today={fields.Date.context_today(self)}", f"language={self.env.lang or 'en_US'}"]
        if not schema:  # structure-only mode tells the vendor no names at all, not even the asker's or the company's
            parts += [f"company={self.env.company.name}", f"user={self.env.user.name}"]
        model = context.get("model")
        if isinstance(model, str) and model in self.env:
            try:
                Model = Tools._model(model)
                parts.append(f"screen_model={model} ({Tools._label(model)})")
                record = Model.browse(int(context.get("res_id") or 0)).exists()
                if record:
                    record.check_access("read")
                    parts.append(f"screen_record_id={record.id}")
                elif context.get("view_type"):
                    parts.append(f"screen_view={str(context['view_type'])[:20]}")
            except (AccessError, UserError, ValueError):
                pass
        mentioned = []
        for mention in context.get("mentions") or []:
            try:
                record = Tools._model(mention.get("model")).browse(int(mention.get("id") or 0)).exists()
                if record:
                    record.check_access("read")
                    mentioned.append(f"{record._name}#{record.id}" if schema else f"{record._name}#{record.id} \"{record.display_name}\"")
            except (AccessError, UserError, ValueError, AttributeError):
                continue
        if mentioned:
            parts.append("mentioned_records=" + ", ".join(mentioned))
        return "[context] " + "; ".join(parts)

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    @api.model
    def _launch(self, answer):
        """Answer in a background thread so no HTTP worker waits on the provider."""
        if config["test_enable"] or self.env.context.get("lx_ai_sync"):
            self._answer(answer)
            return
        args = (self.env.cr.dbname, self.env.uid, dict(self.env.context), answer.id)
        thread = threading.Thread(target=self._thread, args=args, name=f"levelix_ai.{answer.id}", daemon=True)
        self.env.cr.postcommit.add(thread.start)

    @api.model
    def _thread(self, dbname, uid, context, answer_id):
        try:
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, uid, context)
                answer = env["levelix.ai.message"].browse(answer_id).exists()
                if answer:
                    env["levelix.ai.engine"]._answer(answer)
        except Exception:  # noqa: BLE001 - last line of defence for a detached thread
            _logger.exception("Levelix AI answer %s crashed", answer_id)

    def _send(self, answer, payload, commit=True):
        self.env.user._bus_send(BUS_EVENT, dict(payload, message_id=answer.id, conversation_id=answer.conversation_id.id))
        if commit and not config["test_enable"]:
            self.env.cr.commit()  # the bus only delivers on commit

    def _history(self, answer):
        rows = self.env["levelix.ai.message"].search(
            [("conversation_id", "=", answer.conversation_id.id), ("id", "<", answer.id), ("llm_content", "!=", False)],
            order="id desc", limit=HISTORY_TURNS * 3,
        ).sorted("id")
        merged = []
        for row in rows:
            for message in row.llm_content or []:
                if merged and merged[-1]["role"] == message["role"]:  # providers want strictly alternating roles
                    merged[-1] = {"role": message["role"], "content": merged[-1]["content"] + message["content"]}
                else:
                    merged.append({"role": message["role"], "content": list(message["content"])})
        while merged and merged[0]["role"] != "user":
            merged.pop(0)
        return merged

    @api.model
    def _answer(self, answer):
        started = time.monotonic()
        Tools = self.env["levelix.ai.tools"]
        text, blocks, explain, produced = "", [], [], []
        usage = {"input": 0, "output": 0, "cached": 0}
        provider = None
        try:
            provider = self._provider()
            system = prompt.assemble(self._prompt_pieces())
            tools = Tools._available_tools()
            messages = self._history(answer)
            for _step in range(MAX_STEPS):
                step_text, calls, buffer, last = "", [], "", time.monotonic()
                for kind, value in provider.stream(system, messages, tools):
                    if kind == "text":
                        step_text += value
                        buffer += value
                        if time.monotonic() - last >= FLUSH_EVERY:
                            self._send(answer, {"kind": "delta", "text": buffer})
                            buffer, last = "", time.monotonic()
                    elif kind == "tool_use":
                        calls.append(value)
                    elif kind == "usage":
                        for key in usage:
                            usage[key] += value.get(key) or 0
                if buffer:
                    self._send(answer, {"kind": "delta", "text": buffer})
                content = ([{"type": "text", "text": step_text}] if step_text else []) + calls
                if not content:
                    break
                turn = {"role": "assistant", "content": content}
                messages.append(turn)
                produced.append(turn)
                text += step_text
                if not calls:
                    break
                text = ""  # text before a tool call is working notes, not the answer
                self._send(answer, {"kind": "reset"})
                results = [self._call_tool(Tools, call, answer, blocks, explain) for call in calls]
                turn = {"role": "user", "content": results}
                messages.append(turn)
                produced.append(turn)
            else:
                text = text or self.env._("I could not finish this in a reasonable number of steps. Try a narrower question.")
            if not text and not blocks:
                text = self.env._("I found nothing to answer that with.")
            values = {"state": "done", "text": text, "blocks": blocks, "explain": explain, "llm_content": produced}
        except (ProviderError, UserError, AccessError) as error:
            values = {"state": "error", "error": str(error)[:500], "text": text}
        except Exception:  # noqa: BLE001 - the user must get an answer either way
            _logger.exception("Levelix AI answer %s failed", answer.id)
            if not config["test_enable"]:
                self.env.cr.rollback()
            values = {"state": "error", "error": self.env._("Something went wrong while answering. Try again."), "text": text}
        values.update({
            "provider": provider.name if provider else False, "model": provider.model if provider else False,
            "tokens_in": usage["input"], "tokens_out": usage["output"], "tokens_cached": usage["cached"],
            "duration_ms": int((time.monotonic() - started) * 1000),
        })
        answer.sudo().write(values)  # bookkeeping: users cannot write messages by hand
        self._send(answer, {"kind": "done", "message": answer._lx_payload()})

    @contextmanager
    def _tool_guard(self):
        """A savepoint and a statement timeout around one tool, so a slow or failing tool cannot take the answer down."""
        cr = self.env.cr
        cr.execute("SELECT current_setting('statement_timeout')")
        previous = cr.fetchone()[0]
        with cr.savepoint():
            cr.execute("SELECT set_config('statement_timeout', %s, true)", [str(TOOL_TIMEOUT_MS)])
            yield
        cr.execute("SELECT set_config('statement_timeout', %s, true)", [previous])

    def _call_tool(self, Tools, call, answer, blocks, explain):
        started = time.monotonic()
        name, args = call.get("name"), call.get("input") or {}
        mode = self._privacy()
        log = {"message_id": answer.id, "name": name or "?", "arguments": args, "privacy": mode,
               "res_model": args.get("model") if isinstance(args.get("model"), str) else False}
        self._send(answer, {"kind": "status", "tool": name, "model": log["res_model"] or ""})
        try:
            with self._tool_guard():
                result, side = Tools._run(name, args, answer)
            payload = json.dumps(Tools._to_ai(name, result), default=str, ensure_ascii=False)
            if len(payload) > RESULT_CHARS:
                payload = payload[:RESULT_CHARS] + "… (truncated: narrow the query)"
            if side.get("block"):
                blocks.append(side["block"])
            if side.get("explain"):
                explain.append(side["explain"])
            log.update({"record_count": side.get("count") or 0, "res_model": side.get("model") or log["res_model"]})
            is_error = False
        except AccessError:
            payload, is_error = "Access denied: the current user is not allowed to do this.", True
        except pg_errors.QueryCanceled:
            payload, is_error = "Error: the query took too long. Narrow the period or the filters.", True
        except (UserError, ValidationError, ValueError, KeyError, TypeError) as error:
            payload, is_error = f"Error: {error}"[:600], True
        except Exception as error:  # noqa: BLE001 - reported back so the model can correct itself
            _logger.info("Levelix AI tool %s failed: %s", name, error)
            payload, is_error = f"Error: {type(error).__name__}: {error}"[:600], True
        log.update({
            "result_size": len(payload), "is_error": is_error, "error": payload[:200] if is_error else False,
            "duration_ms": int((time.monotonic() - started) * 1000),
        })
        self.env["levelix.ai.tool.call"].sudo().create(log)  # the audit log is written by the server only
        return {"type": "tool_result", "tool_use_id": call.get("id"), "name": name, "content": payload, "is_error": is_error}
