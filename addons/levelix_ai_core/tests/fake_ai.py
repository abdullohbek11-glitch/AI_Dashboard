"""A pretend AI vendor for tests: speaks the real wire format of Anthropic, OpenAI and Gemini.

Why: the provider adapters, the tool loop and the chat page can then be tested end to end
without a paid key. The server *reads* each vendor's request the way the real one does
(roles, tool results, tool declarations, auth header), so a wrong translation fails here.

In tests:      with FakeAI() as ai: ... ai.url ... ai.requests
From a shell:  python3 fake_ai.py --port 9099     (the browser tests use this inside the container)

Keys: "test-key" works; "bad-key" -> 401; "limit-key" -> 429; "down-key" -> 500. Model "no-such-model" -> 404.
"""
import argparse
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GOOD_KEY = "test-key"
CONTEXT = re.compile(r"^\[context\][^\n]*\n\n", re.S)
PREPARED = re.compile(r"\n\n\[prepared:.*", re.S)  # what the system looked up for the model: not what the user typed


def typed(blocks):
    """What the user typed in a message: no context line, no prepared block."""
    return PREPARED.sub("", CONTEXT.sub("", "".join(b.get("text", "") for b in blocks if b["type"] == "text"))).strip().lower()


# -- reading a vendor's request into one neutral shape -----------------------------------------------

def neutral_request(vendor, path, headers, body):
    """-> dict(system, messages[(role, [block])], tools[names], key, model). Blocks: text / tool_use / tool_result."""
    if vendor == "anthropic":
        system = " ".join(b["text"] for b in body.get("system", []))
        messages = [(m["role"], m["content"]) for m in body["messages"]]
        tools = [t["name"] for t in body.get("tools", [])]
        return {"system": system, "messages": messages, "tools": tools, "key": headers.get("x-api-key"), "model": body.get("model")}
    if vendor == "openai":
        messages, system = [], ""
        for m in body["messages"]:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "tool":
                messages.append(("user", [{"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}]))
            elif m["role"] == "assistant":
                blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
                for call in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"], "input": json.loads(call["function"]["arguments"])})
                messages.append(("assistant", blocks))
            else:
                messages.append(("user", [{"type": "text", "text": m["content"]}]))
        tools = [t["function"]["name"] for t in body.get("tools", [])]
        key = (headers.get("authorization") or "").replace("Bearer ", "")
        return {"system": system, "messages": messages, "tools": tools, "key": key, "model": body.get("model")}
    # gemini
    messages = []
    for c in body["contents"]:
        blocks = []
        for part in c["parts"]:
            if "text" in part:
                blocks.append({"type": "text", "text": part["text"]})
            elif "functionCall" in part:
                blocks.append({"type": "tool_use", "id": "g", "name": part["functionCall"]["name"], "input": part["functionCall"]["args"]})
            elif "functionResponse" in part:
                blocks.append({"type": "tool_result", "tool_use_id": "g", "content": part["functionResponse"]["response"]["result"]})
        messages.append(("assistant" if c["role"] == "model" else "user", blocks))
    tools = [d["name"] for t in body.get("tools", []) for d in t.get("functionDeclarations", [])]
    model = re.search(r"/models/([^:]+):", path).group(1)
    return {"system": body["systemInstruction"]["parts"][0]["text"], "messages": messages, "tools": tools,
            "key": headers.get("x-goog-api-key"), "model": model}


# -- what the pretend AI does ----------------------------------------------------------------------------

def say(request, text):
    return [("text", text)]


def call(name, **args):
    return [("tool_use", {"type": "tool_use", "id": "call_" + uuid.uuid4().hex[:8], "name": name, "input": args})]


def summarise(content):
    """Turn a tool result (JSON text) into one plain sentence, the way a model would."""
    try:
        data = json.loads(content)
    except ValueError:
        return content[:200]
    if data.get("shape"):
        return "Result shape: %s" % data["shape"]
    if isinstance(data.get("groups"), list) and data["groups"]:
        groups = data["groups"]
        if len(groups) == 1 and len(groups[0]) == 1:
            return "There are %g." % groups[0][0]
        return "Top: " + ", ".join("%s = %g" % (g[0], g[-1]) for g in groups[:5])
    if isinstance(data.get("groups"), list):
        return "There is no data."
    if "models" in data:
        return "Models: " + ", ".join(m["model"] for m in data["models"][:5])
    if "rows" in data:
        return "Found %s records." % data.get("total")
    return "Done: " + content[:150]


def turn_results(request):
    """Tool results of the question being answered now (everything after the last typed user message)."""
    found = []
    for role, blocks in reversed(request["messages"]):
        if role == "user" and any(b["type"] == "text" for b in blocks):
            break
        found = [b for b in blocks if b["type"] == "tool_result"] + found
    return found


def current_question(request):
    for role, blocks in reversed(request["messages"]):
        if role == "user" and any(b["type"] == "text" for b in blocks):
            return typed(blocks)
    return ""


DRILL = {"action": "drill", "model": "sale.order", "columns": ["name", "partner_id", "date_order", "amount_total", "state"]}


def sales_dashboard(variant):
    """A dashboard spec as a careful model would write it for 'sales this month by day and the top 10 products'."""
    state = [] if "cancelled" in variant else [["state", "=", "sale"]]
    daily = {
        "id": "w1", "type": "area", "title": "Daily sales", "view": {"smooth": True},
        "data": {"source": "sale.report", "domain": state + [["date", ">=", "today =1d"]],
                 "dimensions": [{"field": "date", "granularity": "day"}],
                 "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}],
                 "order": {"by": "date", "dir": "asc"}, "fill_gaps": True},
        "interact": {"on_click": dict(DRILL, map={"date": "date_order"})},
    }
    top = {
        "id": "w2", "type": "bar", "title": "Top 10 products",
        "data": {"source": "sale.report", "domain": state + [["date", ">=", "today =1d"]], "dimensions": [{"field": "product_id"}],
                 "measures": [{"id": "m1", "field": "product_uom_qty", "agg": "sum", "label": "Quantity"}],
                 "order": {"by": "m1", "dir": "desc"}, "limit": 10, "others": True},
        "interact": {"on_click": dict(DRILL, map={"date": "date_order", "product_id": "order_line.product_id"})},
    }
    return {
        "v": 1, "title": "Sales this month", "assumptions": ["Sales means confirmed orders.", "The date is the order date."],
        "widgets": [daily, top],
        "uncertain": [{"text": "Did you mean delivered quantities?",
                       "patch": [{"op": "replace", "path": "/widgets/1/data/measures/0/field", "value": "qty_delivered"}]}],
    }


def dashboard_step(request, text):
    """get_hints -> describe_model -> preview_widget -> build_dashboard, repairing when the server says so."""
    results = turn_results(request)
    if "mood" in text:  # nothing to build it from: say so
        return say(request, "I have no data about mood, so I cannot build that dashboard. I can show sales, products or customers instead.")
    if not results:
        return call("get_hints", query="sales")
    if len(results) == 1:
        return call("describe_model", model="sale.report")
    if len(results) == 2:
        return call("preview_widget", widget=json.dumps(sales_dashboard("")["widgets"][1]))  # the top-products widget: its rows hold names
    last = results[-1]["content"]
    try:
        outcome = json.loads(last)
    except ValueError:
        outcome = {}
    broken = json.loads(json.dumps(sales_dashboard(text)))
    broken["widgets"][0]["data"]["measures"][0]["field"] = "price_subtotl"  # the typo a model might make
    if outcome.get("board_id"):  # build_dashboard succeeded (a preview also says ok, but has no board)
        return say(request, "Your draft is ready: daily sales this month and the top 10 products.")
    if outcome.get("give_up"):
        return say(request, "I could not build this dashboard after several tries, so nothing was saved. Please ask again with a simpler request.")
    if len(results) == 3:  # the first build_dashboard
        return call("build_dashboard", spec=json.dumps(broken if ("repair" in text or "hopeless" in text) else sales_dashboard(text)))
    return call("build_dashboard", spec=json.dumps(broken if "hopeless" in text else sales_dashboard(text)))  # a repair


def decide(request):
    """The pretend AI's brain: a few canned intentions, enough to exercise every code path."""
    last_role, last_blocks = request["messages"][-1]
    if "dashboard" in current_question(request):
        return dashboard_step(request, current_question(request))
    results = [b for b in last_blocks if b["type"] == "tool_result"]
    first = typed(request["messages"][0][1])
    if "loop" in first:
        return call("find_models", query="sales")  # never answers: tests the step limit
    if results:
        if results[0]["content"].startswith(("Error", "Access denied")):
            return say(request, "I could not read that: " + results[0]["content"][:120])
        return say(request, summarise(results[0]["content"]))
    text = typed(last_blocks)
    if "ping" == text:
        return say(request, "OK")
    if "how many sales orders" in text:
        return call("aggregate", model="sale.order", domain=json.dumps([["state", "=", "sale"]]), aggregates=["__count"], show="kpi", title="Sales orders")
    if "top 5 customers" in text:
        return call("aggregate", model="sale.order", domain=json.dumps([["state", "=", "sale"]]), groupby=["partner_id"],
                    aggregates=["amount_total:sum"], order="amount_total:sum desc", limit=5, show="table", title="Top customers")
    if "orders of customer" in text:
        name = text.split("orders of customer", 1)[1].strip(" .?") or "ali"
        if "search_records" in request["tools"]:
            return call("search_records", model="sale.order", domain=json.dumps([["partner_id.name", "ilike", name]]), fields=["name", "amount_total"], limit=5, show="table")
        return call("pick_record", model="res.partner", query=name)
    if "find models" in text:
        return call("find_models", query="sales")
    if "ask me" in text:
        return call("ask_user", question="Which period?", options=["This month", "Last month"])
    if "slow" in text:
        time.sleep(1.5)
    if "markdown" in text:
        return say(request, "**Bold** and `code` <b>raw</b>\n- one\n- two")
    return say(request, "Hello from the fake AI.")


# -- speaking a vendor's response ---------------------------------------------------------------------------

def chunks(text, size=7):
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def stream_events(vendor, events, model):
    """Yield the SSE ``data:`` payloads (already JSON text) the vendor would send."""
    text_events = [v for k, v in events if k == "text"]
    tools = [v for k, v in events if k == "tool_use"]
    cut = any(k == "cut" for k, _v in events)  # the vendor ran out of output room
    out = []
    if vendor == "anthropic":
        out.append({"type": "message_start", "message": {"usage": {"input_tokens": 11, "cache_read_input_tokens": 3}}})
        index = 0
        for text in text_events:
            out.append({"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}})
            for piece in chunks(text):
                out.append({"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": piece}})
            out.append({"type": "content_block_stop", "index": index})
            index += 1
        for tool in tools:
            out.append({"type": "content_block_start", "index": index, "content_block": {"type": "tool_use", "id": tool["id"], "name": tool["name"], "input": {}}})
            raw = json.dumps(tool["input"])
            for piece in chunks(raw, 11):
                out.append({"type": "content_block_delta", "index": index, "delta": {"type": "input_json_delta", "partial_json": piece}})
            out.append({"type": "content_block_stop", "index": index})
            index += 1
        out.append({"type": "message_delta", "delta": {"stop_reason": "max_tokens" if cut else "tool_use" if tools else "end_turn"}, "usage": {"output_tokens": 7}})
        out.append({"type": "message_stop"})
    elif vendor == "openai":
        for text in text_events:
            for piece in chunks(text):
                out.append({"choices": [{"index": 0, "delta": {"content": piece}}]})
        for n, tool in enumerate(tools):
            raw = json.dumps(tool["input"])
            first = True
            for piece in chunks(raw, 11):
                call_delta = {"index": n, "function": {"arguments": piece}}
                if first:
                    call_delta.update({"id": tool["id"], "type": "function"})
                    call_delta["function"]["name"] = tool["name"]
                    first = False
                out.append({"choices": [{"index": 0, "delta": {"tool_calls": [call_delta]}}]})
        out.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "length" if cut else "tool_calls" if tools else "stop"}]})
        out.append({"choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 7, "prompt_tokens_details": {"cached_tokens": 3}}})
    else:
        for text in text_events:
            for piece in chunks(text):
                out.append({"candidates": [{"content": {"role": "model", "parts": [{"text": piece}]}}]})
        parts = [{"functionCall": {"name": t["name"], "args": t["input"]}} for t in tools]
        out.append({"candidates": [{"content": {"role": "model", "parts": parts or [{"text": ""}]}, "finishReason": "MAX_TOKENS" if cut else "STOP"}],
                    "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7, "cachedContentTokenCount": 3}})
    return [json.dumps(item) for item in out]


def error_body(vendor, status, message):
    if vendor == "gemini":
        return {"error": {"code": status, "message": message, "status": "ERROR"}}
    return {"error": {"message": message, "type": "error"}}


# -- the HTTP server ---------------------------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence
        pass

    def vendor(self):
        if self.path.startswith("/v1/messages"):
            return "anthropic"
        if self.path.startswith("/chat/completions"):
            return "openai"
        if ":streamGenerateContent" in self.path:
            return "gemini"
        return None

    def send_json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        """Test helpers: /_log shows what the vendor received, /_reset forgets it."""
        if self.path == "/_reset":
            self.server.requests.clear()
            return self.send_json(200, {"ok": True})
        if self.path == "/_log":
            return self.send_json(200, [{"vendor": r["vendor"], "raw": r["raw"]} for r in self.server.requests])
        return self.send_json(404, {})

    def do_POST(self):  # noqa: N802
        vendor = self.vendor()
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if vendor is None:
            return self.send_json(404, {"error": {"message": "unknown route " + self.path}})
        headers = {k.lower(): v for k, v in self.headers.items()}
        request = neutral_request(vendor, self.path, headers, body)
        server = self.server
        server.requests.append({"vendor": vendor, "request": request, "raw": body, "headers": headers})
        if server.fail_next:
            status = server.fail_next.pop(0)
            return self.send_json(status, error_body(vendor, status, "scripted failure for key " + (request["key"] or "")))
        key = request["key"]
        if key == "limit-key":
            return self.send_json(429, error_body(vendor, 429, "Rate limit reached for key " + (key or "")))
        if key == "down-key":
            return self.send_json(500, error_body(vendor, 500, "internal"))
        if key != server.valid_key:
            return self.send_json(401, error_body(vendor, 401, "Incorrect API key provided: " + (key or "")))
        if request["model"] == "no-such-model":
            return self.send_json(404, error_body(vendor, 404, "model not found"))
        events = (server.script or decide)(request)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for payload in stream_events(vendor, events, request["model"]):
            frame = ("data: %s\n\n" % payload).encode()
            self.wfile.write(b"%x\r\n%s\r\n" % (len(frame), frame))
            self.wfile.flush()
        if vendor == "openai":
            frame = b"data: [DONE]\n\n"
            self.wfile.write(b"%x\r\n%s\r\n" % (len(frame), frame))
        self.wfile.write(b"0\r\n\r\n")


class FakeAI:
    def __init__(self, port=0, valid_key=GOOD_KEY):
        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.requests, self.server.fail_next, self.server.script = [], [], None
        self.server.valid_key = valid_key
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.server.server_address[1]

    @property
    def requests(self):
        return self.server.requests

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9099)
    parser.add_argument("--key", default=GOOD_KEY)
    args = parser.parse_args()
    with FakeAI(args.port, args.key) as ai:
        print("fake AI on", ai.url, flush=True)
        threading.Event().wait()
