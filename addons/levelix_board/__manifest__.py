{
    "name": "Levelix Board",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Dashboards described by a JSON spec and computed live with the viewer's access rights",
    "description": """
Levelix Board
=============
A dashboard is a JSON spec (data source, filters, groupings, measures, widgets).
The spec is validated and executed on the server with the rights of the current
user, so every viewer sees only the data he may read. No AI is needed to use it.
""",
    "author": "Levelix",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/board_views.xml",
        "views/board_page.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "levelix_board/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
