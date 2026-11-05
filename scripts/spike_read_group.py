# F0 spikes 1 and 2: formatted_read_group behaviour on sale.report.
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http --log-level=warn < scripts/spike_read_group.py
import json, time
from datetime import date, timedelta

admin = env.ref("base.user_admin")
admin.tz = "Asia/Tashkent"
c1 = env.ref("base.main_company")
Report = env["sale.report"].with_user(admin).with_context(allowed_company_ids=[c1.id], tz="Asia/Tashkent")
Order = env["sale.order"].with_user(admin).with_context(allowed_company_ids=[c1.id])
print("fields date:", Report._fields["date"].type, "| name:", "name" in Report._fields,
      "| qty_delivered:", "qty_delivered" in Report._fields)

today = date.today()
start = today - timedelta(days=29)
dom = [("state", "in", ["sale", "done"]), ("date", ">=", start.isoformat()), ("date", "<", (today + timedelta(days=1)).isoformat())]

print("\n== 1. group by day, no fill ==")
rows = Report.formatted_read_group(dom, ["date:day"], ["price_subtotal:sum", "__count"])
print(len(rows), "groups; first:", rows[0])

print("\n== 2. fill_temporal on a datetime field with tz ==")
for label, ctx in (("explicit bounds (date strings)", {"fill_from": start.isoformat(), "fill_to": today.isoformat()}),
                   ("explicit bounds (datetime strings)", {"fill_from": start.isoformat() + " 00:00:00", "fill_to": today.isoformat() + " 00:00:00"}),
                   ("fill_temporal=True (existing bounds)", True)):
    try:
        out = Report.with_context(fill_temporal=ctx).formatted_read_group(dom, ["date:day"], ["price_subtotal:sum", "__count"])
        print(label, "->", len(out), "groups; empty:", sum(1 for r in out if not r["__count"]))
    except Exception as e:
        print(label, "-> FAILS:", type(e).__name__, e)
rows_f = rows  # gap filling is done by our own Frame code (see notes)

print("\n== 3. fill_temporal + limit ==")
try:
    Report.with_context(fill_temporal=True).formatted_read_group(dom, ["date:day"], ["__count"], limit=5)
except Exception as e:
    print("raises:", type(e).__name__, e)

print("\n== 4. __extra_domain shape for a day, JSON-serialisable? ==")
row = max(rows, key=lambda r: r["__count"])
print("busiest day:", row["date:day"], row["__count"], "lines")
print("extra_domain:", row["__extra_domain"])
try:
    json.dumps(row["__extra_domain"])
    print("json: ok")
except TypeError as e:
    print("json: FAILS ->", e)

print("\n== 5. drill: map sale.report.date -> sale.order.date_order, compare counts ==")
def map_domain(extra, mapping):
    out = []
    for leaf in extra:
        if isinstance(leaf, (list, tuple)) and len(leaf) == 3:
            f, op, v = leaf
            out.append((mapping.get(f, f), op, v))
        else:
            out.append(leaf)
    return out
orders_dom = map_domain(row["__extra_domain"], {"date": "date_order"}) + [("state", "in", ["sale", "done"])]
print("mapped:", orders_dom)
n_orders = Order.search_count(orders_dom)
distinct = Report.formatted_read_group(row["__extra_domain"] + [("state", "in", ["sale", "done"])], [], ["name:count_distinct"])[0]["name:count_distinct"]
print("sale.order rows:", n_orders, "| distinct orders in sale.report:", distinct, "| MATCH" if n_orders == distinct else "| MISMATCH")

print("\n== 6. every day: drill count == report distinct count? ==")
bad = 0
for r in rows:
    d = Order.search_count(map_domain(r["__extra_domain"], {"date": "date_order"}) + [("state", "in", ["sale", "done"])])
    k = Report.formatted_read_group(r["__extra_domain"] + [("state", "in", ["sale", "done"])], [], ["name:count_distinct"])[0]["name:count_distinct"]
    if d != k:
        bad += 1
        print("  mismatch", r["date:day"], d, k)
print("days checked:", len(rows), "mismatches:", bad)

print("\n== 7. timezone: day boundary check (order at 23:30 UTC belongs to next day in Tashkent) ==")
print("admin tz:", admin.tz, "| first row key:", rows[0]["date:day"])

print("\n== 8. compare: previous period (shift by 30 days) with fill ==")
prev_start, prev_end = start - timedelta(days=30), today - timedelta(days=30)
dom_p = [("state", "in", ["sale", "done"]), ("date", ">=", prev_start.isoformat()), ("date", "<", (prev_end + timedelta(days=1)).isoformat())]
rows_p = Report.formatted_read_group(dom_p, ["date:day"], ["price_subtotal:sum"])
print("previous groups (no fill):", len(rows_p), "| first key:", rows_p[0]["date:day"])

print("\n== 9. date parts / top-N / having ==")
print("day_of_week:", Report.formatted_read_group(dom, ["date:day_of_week"], ["__count"])[:2])
print("hour_number:", Report.formatted_read_group(dom, ["date:hour_number"], ["__count"])[:2])
t0 = time.time()
top = Report.formatted_read_group(dom, ["product_id"], ["product_uom_qty:sum"], limit=3, order="product_uom_qty:sum desc")
print("top3:", [(r["product_id"][1], r["product_uom_qty:sum"]) for r in top], "%.0fms" % ((time.time() - t0) * 1000))
print("having:", len(Report.formatted_read_group(dom, ["product_id"], ["product_uom_qty:sum"], having=[("product_uom_qty:sum", ">", 100)])))

print("\n== 10. non-aggregatable measure (price_unit?) ==")
for f in ("price_unit", "discount", "product_uom_qty", "price_subtotal", "qty_delivered"):
    if f in Report._fields:
        print(f, "-> aggregator:", Report._fields[f].aggregator)
