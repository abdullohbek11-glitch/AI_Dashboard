"""The settings page: a key goes in and never comes back."""
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .fake_ai import GOOD_KEY
from .support import VENDORS, AiCase

SECRET = "sk-settings-secret-424242"


@tagged("post_install", "-at_install", "levelix_ai_core", "-standard")
class TestSettings(AiCase):
    def settings(self, **values):
        admin = self.env.ref("base.user_admin")
        return self.env["res.config.settings"].with_user(admin).create(values)

    def test_a_typed_key_is_saved_but_never_returned(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                record = self.settings(**{"lx_ai_provider": vendor, f"lx_ai_{vendor}_key": SECRET})
                record.execute()
                self.assertEqual(self.env["levelix.ai.engine"]._key(vendor), SECRET)  # stored for the engine
                values = record.get_values()
                self.assertFalse(values[f"lx_ai_{vendor}_key"])  # not handed back to the form
                self.assertTrue(values[f"lx_ai_{vendor}_key_set"])
                self.assertNotIn(SECRET, json.dumps(values, default=str))
                self.assertNotIn(SECRET, json.dumps(record.read(), default=str))  # nor kept in the temporary settings row

    def test_an_empty_field_keeps_the_saved_key(self):
        self.settings(lx_ai_provider="openai", lx_ai_openai_key=SECRET).execute()
        self.settings(lx_ai_provider="openai", lx_ai_openai_key=False, lx_ai_daily_limit=33).execute()
        self.assertEqual(self.env["levelix.ai.engine"]._key("openai"), SECRET)
        self.assertEqual(self.env["levelix.ai.engine"]._param("daily_limit"), "33")

    def test_a_new_key_replaces_and_remove_deletes(self):
        self.settings(lx_ai_provider="gemini", lx_ai_gemini_key=SECRET).execute()
        self.settings(lx_ai_provider="gemini", lx_ai_gemini_key=SECRET + "-2").execute()
        self.assertEqual(self.env["levelix.ai.engine"]._key("gemini"), SECRET + "-2")
        self.settings(lx_ai_provider="gemini").lx_ai_remove_key()
        self.assertFalse(self.env["levelix.ai.engine"]._key("gemini"))

    def test_connection_test_with_every_vendor(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                self.env["ir.config_parameter"].sudo().set_param(f"levelix_ai.{vendor}_base_url", self.ai.url)
                action = self.settings(lx_ai_provider=vendor, **{f"lx_ai_{vendor}_key": GOOD_KEY}).lx_ai_test_connection()
                self.assertEqual(action["tag"], "display_notification")
                self.assertIn("answered: OK", action["params"]["message"])

    def test_connection_test_tells_what_is_wrong(self):
        for vendor in VENDORS:
            with self.subTest(vendor=vendor):
                self.env["ir.config_parameter"].sudo().set_param(f"levelix_ai.{vendor}_base_url", self.ai.url)
                with self.assertRaises(UserError) as ctx:
                    self.settings(lx_ai_provider=vendor, **{f"lx_ai_{vendor}_key": "bad-key"}).lx_ai_test_connection()
                self.assertIn("refused the API key", str(ctx.exception))
                self.assertNotIn("bad-key", str(ctx.exception))
                self.settings(lx_ai_provider=vendor, **{f"lx_ai_{vendor}_key": GOOD_KEY, f"lx_ai_{vendor}_model": "no-such-model"}).execute()
                with self.assertRaises(UserError) as ctx:
                    self.settings(lx_ai_provider=vendor).lx_ai_test_connection()
                self.assertIn("no-such-model", str(ctx.exception))
                self.env["ir.config_parameter"].sudo().set_param(f"levelix_ai.{vendor}_model", False)

    def test_an_ordinary_user_cannot_open_the_settings_or_the_key(self):
        with self.assertRaises(AccessError):
            self.env["res.config.settings"].with_user(self.boss).create({"lx_ai_provider": "openai", "lx_ai_openai_key": SECRET})
        with self.assertRaises(AccessError):
            self.env["ir.config_parameter"].with_user(self.boss).get_param("levelix_ai.anthropic_key")
        with self.assertRaises(AccessError):
            self.env["ir.config_parameter"].with_user(self.boss).search([("key", "like", "levelix_ai")])

    def test_privacy_defaults_and_bad_values(self):
        engine = self.env["levelix.ai.engine"]
        self.env["ir.config_parameter"].sudo().set_param("levelix_ai.privacy", False)
        self.assertEqual(engine._privacy(), "aggregates")  # the default shares totals
        self.env["ir.config_parameter"].sudo().set_param("levelix_ai.privacy", "everything")
        self.assertEqual(engine._privacy(), "aggregates")
        self.env["ir.config_parameter"].sudo().set_param("levelix_ai.privacy", "schema")
        self.assertEqual(engine._privacy(), "schema")

    def test_all_internal_users_setting_grants_the_group(self):
        self.settings(group_lx_ai_user=True).execute()
        self.assertTrue(self.nobody.has_group("levelix_ai_core.group_ai_user"))
        newcomer = new_test_user(self.env, "ai_newcomer", groups="base.group_user")
        self.assertTrue(newcomer.has_group("levelix_ai_core.group_ai_user"))
