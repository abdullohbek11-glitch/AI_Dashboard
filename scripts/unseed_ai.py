# Takes the pretend vendor out of the dev database so a REAL key can be entered in Settings. Idempotent:
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/unseed_ai.py
# Removes the fake keys and the 127.0.0.1:9099 addresses (and nothing else). Put the fake back with scripts/seed_ai.py.
set_param = env["ir.config_parameter"].sudo().set_param
for name in ("anthropic", "openai", "gemini"):
    if env["ir.config_parameter"].sudo().get_param(f"levelix_ai.{name}_key") == "test-key":
        set_param(f"levelix_ai.{name}_key", False)
    if "127.0.0.1" in (env["ir.config_parameter"].sudo().get_param(f"levelix_ai.{name}_base_url") or ""):
        set_param(f"levelix_ai.{name}_base_url", False)
env.cr.commit()
print("fake vendor removed; enter your key in Levelix AI > Settings")
