"""The shared set-up of the assistant tests: a pretend vendor, three kinds of user, a few orders."""
from odoo.tests.common import TransactionCase, new_test_user

from ..providers import PROVIDERS
from .fake_ai import GOOD_KEY, FakeAI

VENDORS = sorted(PROVIDERS)
TZ = "Asia/Tashkent"


class AiCase(TransactionCase):
    """Common set-up: a fake vendor, three kinds of user, a few orders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ai = FakeAI().__enter__()
        cls.addClassCleanup(cls.ai.__exit__)
        env = cls.env
        # a dev database may have "assistant for all internal users" switched on; the tests choose who may chat
        env.ref("base.group_user").write({"implied_ids": [(3, env.ref("levelix_ai_core.group_ai_user").id)]})
        cls.boss = new_test_user(env, "ai_boss", groups="base.group_user,levelix_ai_core.group_ai_user,sales_team.group_sale_manager")
        cls.plain = new_test_user(env, "ai_plain", groups="base.group_user,levelix_ai_core.group_ai_user")  # may chat, may not read sales
        cls.nobody = new_test_user(env, "ai_nobody", groups="base.group_user")  # may not chat
        for user in (cls.boss, cls.plain, cls.nobody):
            user.tz = TZ
        cls.customer = env["res.partner"].create({"name": "AI test customer"})
        cls.product = env["product.product"].create({"name": "AI test product", "list_price": 10, "type": "consu"})

    def setUp(self):
        super().setUp()
        self.ai.requests.clear()
        self.ai.server.script = None
        self.use("anthropic")

    def use(self, vendor, key=GOOD_KEY, **params):
        """Point the assistant at the fake vendor with the given provider."""
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param("levelix_ai.provider", vendor)
        set_param(f"levelix_ai.{vendor}_key", key)
        set_param(f"levelix_ai.{vendor}_base_url", self.ai.url)
        for name, value in dict({"privacy": "aggregates", "daily_limit": "200", "daily_tokens": "0"}, **params).items():
            set_param(f"levelix_ai.{name}", value)

    def order(self, when="2024-03-10 10:00:00", partner=None, qty=1, price=10, confirm=True):
        order = self.env["sale.order"].create({
            "partner_id": (partner or self.customer).id, "date_order": when,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": qty, "price_unit": price})],
        })
        if confirm:
            order.action_confirm()
            order.date_order = when
        return order

    def ask(self, user, text, conversation=False, context=None):
        Conversation = self.env["levelix.ai.conversation"].with_user(user)
        sent = Conversation.lx_send(conversation, text, context)
        answer = self.env["levelix.ai.message"].browse(sent["messages"][1]["id"])
        return sent["conversation"]["id"], answer

    def calls(self, answer):
        return answer.sudo().tool_call_ids.sorted("id")
