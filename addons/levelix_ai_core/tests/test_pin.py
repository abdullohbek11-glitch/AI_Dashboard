"""A chat opened from a record stays about it: the link is stored, listed for that reader only, and checked on read."""
from odoo.tests import tagged

from .support import AiCase


@tagged("post_install", "-at_install", "levelix_ai_core", "-standard")
class TestPinnedChats(AiCase):
    def setUp(self):
        super().setUp()
        self.record = self.env["res.partner"].create({"name": "Pinned Partner"})
        self.pin = {"model": "res.partner", "id": self.record.id}

    def conversation(self, id_):
        return self.env["levelix.ai.conversation"].with_user(self.boss).browse(id_)

    def test_a_chat_started_from_a_record_remembers_it(self):
        conversation_id, _answer = self.ask(self.boss, "hello", context={"pin": self.pin})
        conversation = self.conversation(conversation_id)
        self.assertEqual((conversation.pin_model, conversation.pin_id), ("res.partner", self.record.id))
        self.assertEqual(conversation.lx_load()["conversation"]["pin"], {"model": "res.partner", "id": self.record.id, "label": "Pinned Partner"})

    def test_a_plain_chat_has_no_pin(self):
        conversation_id, _answer = self.ask(self.boss, "hello")
        self.assertFalse(self.conversation(conversation_id).lx_load()["conversation"]["pin"])

    def test_earlier_chats_about_the_record_are_listed_for_their_owner_only(self):
        first, _a = self.ask(self.boss, "one", context={"pin": self.pin})
        self.ask(self.boss, "unrelated")
        listed = self.env["levelix.ai.conversation"].with_user(self.boss).lx_pinned("res.partner", self.record.id)
        self.assertEqual([c["id"] for c in listed], [first])
        self.assertEqual(self.env["levelix.ai.conversation"].with_user(self.plain).lx_pinned("res.partner", self.record.id), [])

    def test_a_bad_pin_is_ignored(self):
        for pin in ({"model": "res.partner", "id": True}, {"model": 5, "id": 1}, "x", {"model": "res.partner"}):
            conversation_id, _a = self.ask(self.boss, "hello", context={"pin": pin})
            self.assertFalse(self.conversation(conversation_id).pin_model, pin)

    def test_a_record_that_is_gone_or_unreadable_shows_no_pin(self):
        conversation_id, _answer = self.ask(self.boss, "hello", context={"pin": self.pin})
        self.record.unlink()
        self.assertFalse(self.conversation(conversation_id).lx_load()["conversation"]["pin"])
