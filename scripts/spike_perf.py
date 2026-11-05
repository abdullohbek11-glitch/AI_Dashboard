# F0 spike: sale.report speed on a bigger table. Everything is rolled back at the end.
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http --log-level=warn < scripts/spike_perf.py
import time
from datetime import date, timedelta

FACTOR = 100
cr = env.cr
def cols(table, skip):
    cr.execute("select column_name from information_schema.columns where table_name=%s order by ordinal_position", [table])
    return [c for (c,) in cr.fetchall() if c not in skip]

oc = cols("sale_order", {"id", "name"})
lc = cols("sale_order_line", {"id", "order_id"})
t0 = time.time()
cr.execute("""INSERT INTO sale_order (name, %s)
              SELECT o.name || '-' || g, %s FROM sale_order o CROSS JOIN generate_series(1, %%s) g
              WHERE o.client_order_ref LIKE 'SEED-%%%%'""" % (
    ", ".join('"%s"' % c for c in oc), ", ".join('o."%s"' % c for c in oc)), [FACTOR])
cr.execute("""INSERT INTO sale_order_line (order_id, %s)
              SELECT n.id, %s FROM sale_order_line l
              JOIN sale_order o ON o.id = l.order_id
              CROSS JOIN generate_series(1, %%s) g
              JOIN sale_order n ON n.name = o.name || '-' || g""" % (
    ", ".join('"%s"' % c for c in lc), ", ".join('l."%s"' % c for c in lc)), [FACTOR])
cr.execute("analyze sale_order; analyze sale_order_line")
cr.execute("select count(*) from sale_order_line")
print("lines now:", cr.fetchone()[0], "| insert took %.1fs" % (time.time() - t0))
env.invalidate_all()

admin = env.ref("base.user_admin")
R = env["sale.report"].with_user(admin).with_context(tz="Asia/Tashkent", allowed_company_ids=[1, 2])
start = (date.today() - timedelta(days=29)).isoformat()
dom = [("state", "=", "sale"), ("date", ">=", start)]
def timeit(label, fn, n=3):
    best = 1e9
    for _ in range(n):
        t = time.time(); r = fn(); best = min(best, time.time() - t)
    print("%-42s %6.0f ms  (%d groups)" % (label, best * 1000, len(r)))
timeit("30 days by day (sum)", lambda: R.formatted_read_group(dom, ["date:day"], ["price_subtotal:sum"]))
timeit("all time by month", lambda: R.formatted_read_group([("state", "=", "sale")], ["date:month"], ["price_subtotal:sum"]))
timeit("top 10 products by qty", lambda: R.formatted_read_group(dom, ["product_id"], ["product_uom_qty:sum"], limit=10, order="product_uom_qty:sum desc"))
timeit("by customer x month (2 dims)", lambda: R.formatted_read_group([("state", "=", "sale")], ["partner_id", "date:month"], ["price_subtotal:sum"]))
timeit("heatmap weekday x hour", lambda: R.formatted_read_group(dom, ["date:day_of_week", "date:hour_number"], ["__count"]))
timeit("distinct orders per day", lambda: R.formatted_read_group(dom, ["date:day"], ["name:count_distinct"]))
sotuvchi = env.ref("seed_aidash.sotuvchi")
Rs = env["sale.report"].with_user(sotuvchi).with_context(tz="Asia/Tashkent")
timeit("30 days by day as salesman (rules)", lambda: Rs.formatted_read_group(dom, ["date:day"], ["price_subtotal:sum"]))
cr.rollback()
cr.execute("select count(*) from sale_order")
print("rolled back, orders:", cr.fetchone()[0])
