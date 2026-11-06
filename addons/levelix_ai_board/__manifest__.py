{
    "name": "Levelix AI Board",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Ask in the chat, get a dashboard draft: the AI side of Levelix Board",
    "description": """
Levelix AI Board
================
Connects the assistant (levelix_ai_core) to dashboards (levelix_board): tools to find the right data
(hints, preview) and to build a draft dashboard from a question, a repair loop that feeds validation
errors back to the model, "what I did" explanations written by code, and the draft block in the chat
with Keep / Change buttons. The model only writes a spec; the server checks and runs it with the
user's own rights.
""",
    "author": "Levelix",
    "license": "LGPL-3",
    "depends": ["levelix_board", "levelix_ai_core"],
    "data": [
        "security/ir.model.access.csv",
        "data/hints.xml",
        "views/hint_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["levelix_ai_board/static/src/**/*"],
    },
    "installable": True,
    "application": False,
}
