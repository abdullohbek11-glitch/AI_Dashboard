# Demo dashboards for the dev database. Run (idempotent):
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/seed_boards.py
# Test accounts follow the project convention: password == login.
MANAGER_LOGIN = "boshliq"
BOARD_NAME = "Sales overview"

group_user = env.ref("base.group_user")
group_manager = env.ref("sales_team.group_sale_manager")
manager = env["res.users"].search([("login", "=", MANAGER_LOGIN)])
if not manager:
    manager = env["res.users"].create({
        "name": "Boshliq", "login": MANAGER_LOGIN, "password": MANAGER_LOGIN, "email": "boshliq@example.com",
        "group_ids": [(6, 0, (group_user | group_manager).ids)],
    })

paid = [["state", "=", "sale"], ["date", ">=", "today -90d"]]
drill_orders = {"action": "drill", "open_as": "side_table", "model": "sale.order", "map": {"date": "date_order"},
                "columns": ["name", "partner_id", "date_order", "amount_total", "state"]}
spec = {
    "v": 1,
    "title": "Sales overview",
    "assumptions": ["Sales means confirmed orders", "Last 90 days"],
    "widgets": [
        {"id": "revenue", "type": "kpi", "title": "Revenue",
         "grid": {"x": 0, "y": 0, "w": 6, "h": 4},
         "data": {"source": "sale.report", "domain": paid,
                  "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}]},
         "interact": {"on_click": drill_orders}},
        {"id": "orders", "type": "kpi", "title": "Orders",
         "grid": {"x": 6, "y": 0, "w": 6, "h": 4},
         "data": {"source": "sale.report", "domain": paid,
                  "measures": [{"id": "m1", "field": "name", "agg": "count_distinct", "label": "Orders"}]},
         "interact": {"on_click": drill_orders}},
        {"id": "by_seller", "type": "bar", "title": "Revenue by salesperson",
         "grid": {"x": 12, "y": 0, "w": 12, "h": 4},
         "data": {"source": "sale.report", "domain": paid, "dimensions": [{"field": "user_id"}],
                  "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}],
                  "order": {"by": "m1", "dir": "desc"}},
         "view": {"orientation": "horizontal"},
         "interact": {"on_click": dict(drill_orders, map={"date": "date_order", "user_id": "user_id"})}},
        {"id": "daily", "type": "area", "title": "Daily sales",
         "grid": {"x": 0, "y": 4, "w": 16, "h": 8},
         "data": {"source": "sale.report", "domain": paid, "dimensions": [{"field": "date", "granularity": "day"}],
                  "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}],
                  "order": {"by": "date", "dir": "asc"}, "fill_gaps": True},
         "view": {"smooth": True},
         "interact": {"on_click": drill_orders}},
        {"id": "top_products", "type": "bar", "title": "Top 10 products",
         "grid": {"x": 16, "y": 4, "w": 8, "h": 8},
         "data": {"source": "sale.report", "domain": paid, "dimensions": [{"field": "product_id"}],
                  "measures": [{"id": "m1", "field": "product_uom_qty", "agg": "sum", "label": "Quantity"}],
                  "order": {"by": "m1", "dir": "desc"}, "limit": 10, "others": True},
         "interact": {"on_click": dict(drill_orders, map={"date": "date_order", "product_id": "order_line.product_id"})}},
        {"id": "customers", "type": "table", "title": "Top customers",
         "grid": {"x": 0, "y": 12, "w": 24, "h": 9},
         "data": {"source": "sale.report", "domain": paid, "dimensions": [{"field": "partner_id"}],
                  "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"},
                               {"id": "m2", "field": "name", "agg": "count_distinct", "label": "Orders"}],
                  "order": {"by": "m1", "dir": "desc"}, "limit": 10},
         "interact": {"on_click": dict(drill_orders, map={"date": "date_order"})}},
    ],
}
Board = env["levelix.board"].with_user(manager).with_context(tz="Asia/Tashkent")
board = Board.search([("name", "=", BOARD_NAME)]) or Board.create({"name": BOARD_NAME, "share_mode": "company", "spec": spec})
board.spec = spec
env.cr.commit()
print("board", board.id, "version", board.version, "owner", board.user_id.login)
