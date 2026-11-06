# F7 chat-editing check with the REAL model (needs the AI key the user entered; never prints it). Everything is rolled back at the end.
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/f7_ai_check.py
import copy
import json
import time

user = env["res.users"].search([("login", "=", "boshliq")], limit=1)
uenv = env(user=user.id, context=dict(env.context, tz="Asia/Tashkent", lx_ai_sync=True))
Board = uenv["levelix.board"]
spec = {
    "v": 1, "title": "F7 AI check",
    "widgets": [
        {"id": "w1", "type": "area", "title": "Daily sales", "grid": {"x": 0, "y": 0, "w": 12, "h": 8},
         "data": {"source": "sale.report", "domain": [["state", "=", "sale"], ["date", ">=", "today -89d"]],
                  "dimensions": [{"field": "date", "granularity": "day"}],
                  "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}],
                  "order": {"by": "date", "dir": "asc"}, "fill_gaps": True}},
        {"id": "w2", "type": "bar", "title": "Top products", "grid": {"x": 12, "y": 0, "w": 12, "h": 8},
         "data": {"source": "sale.report", "domain": [["state", "=", "sale"], ["date", ">=", "today -89d"]],
                  "dimensions": [{"field": "product_id"}],
                  "measures": [{"id": "m1", "field": "product_uom_qty", "agg": "sum", "label": "Quantity"}],
                  "order": {"by": "m1", "dir": "desc"}, "limit": 10}},
    ],
}
board = Board.create({"name": "F7 AI check", "spec": spec, "state": "active"})
original = copy.deepcopy(board.spec)
chat = uenv["levelix.ai.conversation"]


def ask(conversation_id, text):
    started = time.time()
    data = chat.lx_send(conversation_id, text, {"mentions": [{"model": "levelix.board", "id": board.id}]})
    answer = uenv["levelix.ai.message"].browse(data["messages"][1]["id"])
    calls = [(c.name, "ERR " + (c.error or "") if c.is_error else "ok") for c in answer.tool_call_ids]
    print("Q: %s | state %s | %.1fs | tools %s | err %s\n   A: %s" % (text, answer.state, time.time() - started, calls, answer.error or "-", (answer.text or "")[:200]))
    return data["conversation"]["id"]


def widgets():
    return {w["id"]: w for w in board.invalidate_recordset() or board.spec["widgets"]}


conversation = ask(False, "Make the Top products chart a column chart (vertical bars), change nothing else.")
w = {x["id"]: x for x in board.spec["widgets"]}
print("   -> w2 view:", w["w2"].get("view"), "| w1 unchanged:", w["w1"] == original["widgets"][0], "| grids kept:", all(x.get("grid") for x in w.values()))
ask(conversation, "Now show only the last 3 months in the daily sales chart, keep the layout.")
w = {x["id"]: x for x in board.spec["widgets"]}
print("   -> w1 domain:", w["w1"]["data"]["domain"], "| w1 grid same:", w["w1"].get("grid") == original["widgets"][0]["grid"], "| ids:", list(w))
print("versions:", [(v.version, v.origin, v.note) for v in board.version_ids.sorted("version")])
env.cr.rollback()
print("rolled back")
