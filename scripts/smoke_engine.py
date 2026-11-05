# Quick manual check of the engine on the seeded data (compare with Odoo's own dashboard).
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http --log-level=warn < scripts/smoke_engine.py
import json
admin = env.ref("base.user_admin")
admin.tz = "Asia/Tashkent"
eng = env["levelix.board.engine"].with_user(admin).with_context(allowed_company_ids=[1], tz="Asia/Tashkent")
spec = {
    "v": 1, "title": "Sales analysis",
    "widgets": [
        {"id": "w1", "type": "area", "title": "Daily sales", "data": {
            "source": "sale.report",
            "domain": [["state", "=", "sale"], ["date", ">=", "today -29d"], ["date", "<=", "today"]],
            "dimensions": [{"field": "date", "granularity": "day"}],
            "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}],
            "order": {"by": "date", "dir": "asc"}, "fill_gaps": True}},
        {"id": "w2", "type": "bar", "title": "Top 5 products", "data": {
            "source": "sale.report", "domain": [["state", "=", "sale"]],
            "dimensions": [{"field": "product_id"}],
            "measures": [{"id": "m1", "field": "product_uom_qty", "agg": "sum"}],
            "order": {"by": "m1", "dir": "desc"}, "limit": 5, "others": True}},
        {"id": "w3", "type": "kpi", "data": {
            "source": "sale.report", "domain": [["state", "=", "sale"]],
            "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum"}, {"id": "m2", "field": "name", "agg": "count_distinct", "label": "Orders"}]}},
        {"id": "w4", "type": "bar", "data": {  # deliberately wrong
            "source": "sale.report", "dimensions": [{"field": "product_id"}],
            "measures": [{"id": "m1", "field": "price_unit", "agg": "sum"}]}},
    ],
}
print(json.dumps(eng._validate_spec(spec), indent=1)[:1500])
res = eng._run_spec(spec, explain=True)["widgets"]
w1 = res["w1"]["frame"]
print("w1 rows:", len(w1["rows"]), w1["rows"][:3], "...", w1["rows"][-2:], "| currency", w1["meta"]["currency"])
print("w1 explain:", *[("  - " + l["text"]) for l in res["w1"]["explain"]], sep="\n")
print("w2 rows:", res["w2"]["frame"]["rows"])
print("w3:", res["w3"]["frame"]["rows"], [c["label"] for c in res["w3"]["frame"]["columns"]])
print("w4:", res["w4"])
