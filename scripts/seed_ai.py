# Dev set-up of the assistant against the pretend vendor (addons/levelix_ai_core/tests/fake_ai.py). Idempotent:
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/seed_ai.py
# NOT for production: it stores the fake vendor's test key and points every provider at 127.0.0.1:9099.
# Test accounts follow the project convention: password == login.
FAKE = "http://127.0.0.1:9099"
admin = env["res.users"].search([("login", "=", "lxadmin")])
if not admin:
    admin = env["res.users"].create({
        "name": "AI Admin", "login": "lxadmin", "password": "lxadmin", "email": "lxadmin@example.com",
        "group_ids": [(6, 0, (env.ref("base.group_user") | env.ref("base.group_system")).ids)],
    })
env["res.config.settings"].create({"group_lx_ai_user": True}).execute()  # every internal user may use the assistant
set_param = env["ir.config_parameter"].sudo().set_param
set_param("levelix_ai.provider", "anthropic")
for name in ("anthropic", "openai", "gemini"):
    set_param(f"levelix_ai.{name}_key", "test-key")
    set_param(f"levelix_ai.{name}_base_url", FAKE)
set_param("levelix_ai.privacy", "aggregates")
set_param("levelix_ai.daily_limit", "200")
env.cr.commit()
print("assistant ready against", FAKE, "| admin:", admin.login)
