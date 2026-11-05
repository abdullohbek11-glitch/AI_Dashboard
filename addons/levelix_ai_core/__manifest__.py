{
    "name": "Levelix AI Core",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "AI foundation: providers, chat, tools, privacy modes, limits and an audit log",
    "description": """
Levelix AI Core
===============
Provider adapters (Anthropic, OpenAI, Gemini), a tool registry other modules extend, the
chat (streamed over the bus), conversations and an audit log of every tool call. Every
tool runs with the asking user's own access rights. It knows nothing about dashboards.
""",
    "author": "Levelix",
    "license": "LGPL-3",
    "depends": ["web", "bus", "base_setup"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/res_config_settings_views.xml",
        "views/audit_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["levelix_ai_core/static/src/**/*"],
    },
    "installable": True,
    "application": False,
}
