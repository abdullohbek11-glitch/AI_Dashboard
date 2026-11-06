from odoo import fields, models
from odoo.exceptions import UserError

from ..providers import PROVIDERS, ProviderError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    lx_ai_provider = fields.Selection(
        [(name, cls.label) for name, cls in PROVIDERS.items()],
        string="AI Provider", config_parameter="levelix_ai.provider", default="anthropic",
    )
    # API keys are write-only: the form never receives a stored key back, only "a key is saved"
    lx_ai_anthropic_key = fields.Char("Anthropic API Key")
    lx_ai_openai_key = fields.Char("OpenAI API Key")
    lx_ai_gemini_key = fields.Char("Gemini API Key")
    lx_ai_anthropic_key_set = fields.Boolean(readonly=True)
    lx_ai_openai_key_set = fields.Boolean(readonly=True)
    lx_ai_gemini_key_set = fields.Boolean(readonly=True)
    lx_ai_anthropic_model = fields.Char("Anthropic Model", config_parameter="levelix_ai.anthropic_model", default=PROVIDERS["anthropic"].default_model)
    lx_ai_openai_model = fields.Char("OpenAI Model", config_parameter="levelix_ai.openai_model", default=PROVIDERS["openai"].default_model)
    lx_ai_gemini_model = fields.Char("Gemini Model", config_parameter="levelix_ai.gemini_model", default=PROVIDERS["gemini"].default_model)
    lx_ai_anthropic_base_url = fields.Char("Anthropic Address", config_parameter="levelix_ai.anthropic_base_url", help="Leave empty for the vendor's own address. Set it to use a proxy.")
    lx_ai_openai_base_url = fields.Char("OpenAI Address", config_parameter="levelix_ai.openai_base_url", help="Leave empty for the vendor's own address. Set it to use a proxy.")
    lx_ai_gemini_base_url = fields.Char("Gemini Address", config_parameter="levelix_ai.gemini_base_url", help="Leave empty for the vendor's own address. Set it to use a proxy.")
    lx_ai_timeout = fields.Integer("Timeout (seconds)", config_parameter="levelix_ai.timeout", default=120,
                                   help="How long to wait for the provider's answer before giving up.")
    lx_ai_temperature = fields.Char("Temperature", config_parameter="levelix_ai.temperature",
                                    help="Leave empty for the vendor's default. Low values (0 to 0.2) give steadier answers.")
    lx_ai_reasoning = fields.Selection(
        [("minimal", "Fastest"), ("low", "Fast (recommended)"), ("medium", "Balanced"), ("high", "Most careful"), ("default", "Provider's own default (slowest)")],
        string="Thinking Time", config_parameter="levelix_ai.reasoning", default="low",
        help="How long a thinking model (OpenAI GPT-5, Gemini 3) may think before each step. Shorter is much faster: on a typical question "
             "'Fast' answered in a third of the time of the provider's default. 'Fastest' can slip on subtle points (for example counting "
             "order lines instead of orders). Models that do not think ignore this.")
    lx_ai_privacy = fields.Selection(
        [("aggregates", "Share totals and search results"), ("schema", "Share structure only")],
        string="Privacy Mode", config_parameter="levelix_ai.privacy", default="aggregates",
        help="What the AI provider may see of your data. 'Structure only' sends models, fields and the shape of results, never a value or a name: "
             "the user still sees the full result on screen.",
    )
    lx_ai_daily_limit = fields.Integer("Daily Questions per User", config_parameter="levelix_ai.daily_limit", default=200,
                                       help="Each user stops at this number of questions per day. 0 means no limit.")
    lx_ai_daily_tokens = fields.Integer("Daily Tokens per User", config_parameter="levelix_ai.daily_tokens", default=0,
                                        help="Each user stops after this many tokens per day. 0 means no limit.")
    group_lx_ai_user = fields.Boolean(
        "Assistant for All Internal Users", implied_group="levelix_ai_core.group_ai_user",
        help="Off: pick who may use the assistant on each user's form.",
    )

    def get_values(self):
        res = super().get_values()
        engine = self.env["levelix.ai.engine"]
        for name in PROVIDERS:
            res[f"lx_ai_{name}_key"] = False  # never sent back
            res[f"lx_ai_{name}_key_set"] = bool(engine._key(name))
        return res

    def set_values(self):
        super().set_values()
        cleared = {}
        for name in PROVIDERS:
            key = (self[f"lx_ai_{name}_key"] or "").strip()
            if key:
                self.env["ir.config_parameter"].sudo().set_param(f"levelix_ai.{name}_key", key)
            cleared[f"lx_ai_{name}_key"] = False
        self.write(cleared)  # the typed key must not linger in the temporary settings row

    def lx_ai_remove_key(self):
        self.ensure_one()
        self.set_values()
        name = self.env["levelix.ai.engine"]._param("provider", "anthropic")
        self.env["ir.config_parameter"].sudo().set_param(f"levelix_ai.{name}_key", False)
        return {"type": "ir.actions.client", "tag": "reload"}

    def lx_ai_test_connection(self):
        self.ensure_one()
        self.set_values()  # test what was just typed
        engine = self.env["levelix.ai.engine"]
        try:
            provider = engine._provider()
            answer = provider.check()
        except ProviderError as error:
            raise UserError(str(error)) from error
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success", "sticky": False,
                "title": self.env._("The connection works"),
                "message": self.env._("%(provider)s (%(model)s) answered: %(text)s", provider=provider.label, model=provider.model, text=answer[:80] or "…"),
            },
        }
