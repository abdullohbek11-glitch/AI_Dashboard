# One dashboard with every widget type, dashboard filters, a cross-filter and comparisons, for the F6 acceptance test. Run (idempotent):
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/seed_f6.py
# Owner: boshliq (password == login), shared with the company.
MANAGER_LOGIN = "boshliq"
BOARD_NAME = "F6 all types"

manager = env["res.users"].search([("login", "=", MANAGER_LOGIN)])
assert manager, "run scripts/seed_boards.py first (it creates the boshliq account)"

paid = [["state", "=", "sale"]]
REV = {"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}
ORD = {"id": "m2", "field": "name", "agg": "count_distinct", "label": "Orders"}
DAY = {"on_click": {"action": "drill", "open_as": "side_table", "model": "sale.order", "map": {"date": "date_order"},
                    "columns": ["name", "partner_id", "date_order", "amount_total", "state"]}}
CROSS = {"on_click": {"action": "cross_filter"}}


def widget(wid, wtype, title, dims, measures, interact=None, view=None, **data):
    out = {"id": wid, "type": wtype, "title": title,
           "data": dict({"source": "sale.report", "domain": paid, "dimensions": dims, "measures": measures}, **data)}
    if interact:
        out["interact"] = interact
    if view:
        out["view"] = view
    return out


spec = {
    "v": 1,
    "title": "F6 all types",
    "assumptions": ["Sales means confirmed orders"],
    "filters": [
        {"id": "period", "type": "date_range", "label": "Period", "default": "last_30_days", "applies_to": {"sale.report": "date"}},
        {"id": "seller", "type": "select", "label": "Salesperson", "applies_to": {"sale.report": "user_id"}},
        {"id": "amounts", "type": "amount_basis", "label": "Amounts", "default": "untaxed",
         "applies_to": {"sale.report": {"untaxed": "price_subtotal", "taxed": "price_total"}}},
    ],
    "widgets": [
        widget("kpi_revenue", "kpi", "Revenue", [], [REV, ORD], compare="previous_period"),
        widget("kpi_year", "kpi", "Revenue, same days last year", [], [REV], compare="previous_year"),
        widget("line_daily", "line", "Daily revenue", [{"field": "date", "granularity": "day"}], [REV],
               interact=DAY, view={"smooth": True}, fill_gaps=True, order={"by": "date", "dir": "asc"}, compare="previous_period"),
        widget("area_month", "area", "Monthly revenue by category",
               [{"field": "date", "granularity": "month"}, {"field": "categ_id"}], [REV], fill_gaps=True, order={"by": "date", "dir": "asc"}),
        widget("bar_products", "bar", "Top products (click to filter the others)", [{"field": "product_id"}], [REV],
               interact=CROSS, view={"orientation": "horizontal"}, order={"by": "m1", "dir": "desc"}, limit=8, others=True),
        widget("pie_category", "pie", "Revenue share by category", [{"field": "categ_id"}], [REV], interact=CROSS),
        widget("pie_customers", "pie", "Revenue share by customer", [{"field": "partner_id"}], [REV], view={"donut": True}),
        widget("table_customers", "table", "Top customers",
               [{"field": "partner_id"}], [REV, ORD, {"id": "m3", "calc": "m1 / m2", "label": "Average order"},
                {"id": "m4", "field": "price_total", "agg": "sum", "label": "Revenue with tax (always)", "fixed": True}],
               order={"by": "m1", "dir": "desc"}, limit=8),
        widget("heatmap_week", "heatmap", "Orders by weekday and hour",
               [{"field": "date", "granularity": "day_of_week"}, {"field": "date", "granularity": "hour_number"}], [ORD], interact=DAY),
        widget("funnel_status", "funnel", "Orders by status", [{"field": "state"}], [ORD],
               domain=[["state", "in", ["draft", "sent", "sale"]]], order={"by": "m2", "dir": "desc"}),
        widget("treemap_mix", "treemap", "Revenue by category and product", [{"field": "categ_id"}, {"field": "product_id"}], [REV]),
        widget("gauge_target", "gauge", "Revenue against the target", [], [REV], view={"target": 60000000}),
        widget("waterfall_category", "waterfall", "Revenue build-up by category", [{"field": "categ_id"}], [REV],
               order={"by": "m1", "dir": "desc"}),
        widget("scatter_customers", "scatter", "Customers: orders against revenue", [{"field": "partner_id"}], [ORD, REV]),
        widget("combo_month", "combo", "Revenue and orders by month", [{"field": "date", "granularity": "month"}], [REV, ORD],
               view={"line": "m2"}, order={"by": "date", "dir": "asc"}),
        widget("bar_seller", "bar", "Revenue by salesperson", [{"field": "user_id"}], [REV], order={"by": "m1", "dir": "desc"}),
    ],
}
Board = env["levelix.board"].with_user(manager).with_context(tz="Asia/Tashkent")
board = Board.search([("name", "=", BOARD_NAME)]) or Board.create({"name": BOARD_NAME, "share_mode": "company", "spec": spec})
board.spec = spec
env.cr.commit()
print("board", board.id, "version", board.version, "owner", board.user_id.login, "widgets", len(spec["widgets"]))
