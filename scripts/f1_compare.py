# F1 acceptance: engine numbers vs an independent SQL calculation straight from the order tables.
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http --log-level=warn < scripts/f1_compare.py
admin = env.ref("base.user_admin")
eng = env["levelix.board.engine"].with_user(admin).with_context(allowed_company_ids=[1], tz="Asia/Tashkent")
cr = env.cr

def sql(query, *params):
    cr.execute(query, params)
    return cr.fetchall()

spec = {"v": 1, "widgets": [
    {"id": "kpi", "type": "kpi", "data": {"source": "sale.report", "domain": [["state", "=", "sale"]],
        "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"}, {"id": "m2", "field": "name", "agg": "count_distinct"}]}},
    {"id": "days", "type": "area", "data": {"source": "sale.report",
        "domain": [["state", "=", "sale"], ["date", ">=", "today -29d"], ["date", "<=", "today"]],
        "dimensions": [{"field": "date", "granularity": "day"}], "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"}],
        "order": {"by": "date", "dir": "asc"}, "fill_gaps": True}},
    {"id": "top", "type": "bar", "data": {"source": "sale.report", "domain": [["state", "=", "sale"]],
        "dimensions": [{"field": "product_id"}], "measures": [{"id": "m1", "field": "product_uom_qty", "agg": "sum"}],
        "order": {"by": "m1", "dir": "desc"}, "limit": 5, "others": True}},
    {"id": "sellers", "type": "table", "data": {"source": "sale.report", "domain": [["state", "=", "sale"]],
        "dimensions": [{"field": "user_id"}], "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"},
                                                              {"id": "m2", "field": "name", "agg": "count_distinct", "label": "Orders"}],
        "order": {"by": "m1", "dir": "desc"}}},
]}
res = eng._run_spec(spec)["widgets"]
ok = True

def check(label, engine_value, sql_value, tol=0.01):
    global ok
    good = abs(engine_value - sql_value) <= tol
    ok &= good
    print("%-34s engine %18s | SQL %18s | %s" % (label, "{:,.2f}".format(engine_value), "{:,.2f}".format(sql_value), "OK" if good else "MISMATCH"))

# 1. totals (main company, confirmed orders, company currency)
total_sql, orders_sql = sql("""SELECT COALESCE(SUM(l.price_subtotal / NULLIF(o.currency_rate, 0)), 0), COUNT(DISTINCT o.id)
    FROM sale_order_line l JOIN sale_order o ON o.id = l.order_id
    WHERE o.state = 'sale' AND o.company_id = 1 AND l.display_type IS NULL""")[0]
total, orders = res["kpi"]["frame"]["rows"][0]
check("Total revenue", total, float(total_sql), 1.0)
check("Confirmed orders", orders, orders_sql)

# 2. daily series for the last 30 days: sum and number of non-empty days
rows = res["days"]["frame"]["rows"]
day_sql = sql("""SELECT (o.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tashkent')::date AS d,
                        SUM(l.price_subtotal / NULLIF(o.currency_rate, 0))
    FROM sale_order_line l JOIN sale_order o ON o.id = l.order_id
    WHERE o.state = 'sale' AND o.company_id = 1 AND l.display_type IS NULL
      AND (o.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tashkent')::date >= (now() AT TIME ZONE 'Asia/Tashkent')::date - 29
      AND (o.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tashkent')::date <= (now() AT TIME ZONE 'Asia/Tashkent')::date
    GROUP BY 1""")
by_day = {str(d): float(v) for d, v in day_sql}
print("%-34s %d rows (30 expected, empty days filled with 0)" % ("Daily series", len(rows)))
bad_days = [r[0] for r in rows if abs(r[1] - by_day.get(r[0], 0.0)) > 1.0]
ok &= len(rows) == 30 and not bad_days
print("%-34s %s" % ("Every day equals the SQL value", "OK" if not bad_days else "MISMATCH on %s" % bad_days))

# 3. top 5 products by quantity, and "Others" = the rest
top = res["top"]["frame"]["rows"]
prod_sql = sql("""SELECT pt.name->>'en_US', SUM(l.product_uom_qty) FROM sale_order_line l
    JOIN sale_order o ON o.id = l.order_id JOIN product_product pp ON pp.id = l.product_id JOIN product_template pt ON pt.id = pp.product_tmpl_id
    WHERE o.state = 'sale' AND o.company_id = 1 AND l.display_type IS NULL GROUP BY 1 ORDER BY 2 DESC""")
for (name, qty), row in zip(prod_sql[:5], top[:5]):
    check("Top product: %s" % name, row[1], float(qty))
check("'Others' (all remaining products)", top[5][1], float(sum(q for _, q in prod_sql[5:])))

# 4. per salesperson
for name, value, count in [(r[0], r[1], r[2]) for r in res["sellers"]["frame"]["rows"]]:
    uid_sql = sql("""SELECT COALESCE(SUM(l.price_subtotal / NULLIF(o.currency_rate, 0)), 0), COUNT(DISTINCT o.id)
        FROM sale_order_line l JOIN sale_order o ON o.id = l.order_id JOIN res_users u ON u.id = o.user_id JOIN res_partner p ON p.id = u.partner_id
        WHERE o.state = 'sale' AND o.company_id = 1 AND l.display_type IS NULL AND p.name = %s""", name)[0]
    check("Salesperson revenue: %s" % name, value, float(uid_sql[0]), 1.0)
    check("Salesperson orders: %s" % name, count, uid_sql[1])
print("\nALL MATCH" if ok else "\nSOME VALUES DIFFER")
