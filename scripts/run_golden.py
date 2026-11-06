#!/usr/bin/env python3
"""The golden set: real questions, asked through the real chat, checked against Odoo's own numbers.

For every question in golden/questions.json this asks the assistant (as the question's user), then checks
  1. what it built: reporting model, measure, the filter that matters (status), number of widgets;
  2. the NUMBER: the dashboard is run and compared with an ORACLE, a plain Odoo query evaluated now on the same database
     (so the expected value never goes stale and never comes from the assistant's own engine path);
  3. honesty: a question that cannot or must not be answered must not produce a dashboard.
It needs a real AI key (DEFERRED.md); with the pretend vendor only the smoke question (F00) is meaningful: --smoke.

    python3 scripts/run_golden.py                      # every question this database can answer
    python3 scripts/run_golden.py --only S01,S02       # some
    python3 scripts/run_golden.py --smoke              # F00 only: proves the runner itself, works with the pretend vendor
    python3 scripts/run_golden.py --write notes/F5_golden_v1.md

Accounts follow the dev convention: password == login (override with --password). Standard library only.
"""
import argparse
import collections
import http.cookiejar
import json
import sys
import time
import urllib.request
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = __file__.rsplit("/", 2)[0]
TOLERANCE = 0.005  # half a percent


class Rpc:
    def __init__(self, base, db, login, password):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        out = self.post("/web/session/authenticate", {"db": db, "login": login, "password": password})
        if not out.get("result", {}).get("uid"):
            raise SystemExit("cannot log in as %s" % login)

    def post(self, path, params):
        body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}).encode()
        request = urllib.request.Request(self.base + path, body, {"Content-Type": "application/json"})
        return json.load(self.opener.open(request, timeout=300))

    def call(self, model, method, args=None, kwargs=None, tz=None):
        kwargs = dict(kwargs or {})
        if tz:
            kwargs["context"] = dict(kwargs.get("context") or {}, tz=tz)
        out = self.post("/web/dataset/call_kw/%s/%s" % (model, method), {"model": model, "method": method, "args": args or [], "kwargs": kwargs})
        if "error" in out:
            raise RuntimeError(out["error"]["data"]["message"].strip().split("\n")[0])
        return out["result"]


# -- dates: the asking user's local midnights --------------------------------------------------------------------

def placeholders(tz_name):
    zone = ZoneInfo(tz_name)
    today = datetime.now(zone).date()
    first = lambda d: d.replace(day=1)  # noqa: E731
    month = first(today)
    last_month = first(month - timedelta(days=1))
    quarter = month.replace(month=3 * ((month.month - 1) // 3) + 1)
    return {
        "$today": today, "$week_start": today - timedelta(days=today.weekday()), "$month_start": month,
        "$last_month_start": last_month, "$quarter_start": quarter, "$year_start": today.replace(month=1, day=1),
        "$days_ago_7": today - timedelta(days=7),
    }, zone


def resolve_domain(domain, field_types, tz_name):
    days, zone = placeholders(tz_name)
    out = []
    for leaf in domain:
        if isinstance(leaf, list) and len(leaf) == 3 and leaf[2] in days:
            day = days[leaf[2]]
            if field_types.get(leaf[0]) == "date":
                leaf = [leaf[0], leaf[1], day.isoformat()]
            else:
                local = datetime.combine(day, dtime.min, tzinfo=zone)
                leaf = [leaf[0], leaf[1], local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")]
        out.append(leaf)
    return out


# -- the oracle --------------------------------------------------------------------------------------------------------------

def oracle_value(rpc, oracle, tz_name):
    """Odoo's own answer: ``{"total": number}`` or ``{"names": [...], "total": number}``. ``None`` when there is no oracle."""
    if not oracle or oracle.get("kind") == "none":
        return None
    types = {n: v["type"] for n, v in rpc.call(oracle["model"], "fields_get", [], {"attributes": ["type"]}).items()}
    domain = resolve_domain(oracle["domain"], types, tz_name)
    groupby = [oracle["groupby"]] if oracle.get("groupby") else []
    order = "%s %s" % (oracle["measure"], oracle["order"]) if oracle.get("order") else None
    groups = rpc.call(oracle["model"], "formatted_read_group", [domain], {
        "groupby": groupby, "aggregates": [oracle["measure"]], "order": order, "limit": oracle.get("top")}, tz=tz_name)
    if groupby:
        return {"names": [g[groupby[0]][1] if isinstance(g[groupby[0]], list) else g[groupby[0]] for g in groups], "total": sum(g[oracle["measure"]] or 0 for g in groups)}
    return {"total": sum(g[oracle["measure"]] or 0 for g in groups)}


# -- what was built -------------------------------------------------------------------------------------------------------------

def leaves(domain):
    return [l for l in domain if isinstance(l, list) and len(l) == 3]


def has_filter(domain, wanted):
    field, op, value = wanted
    for leaf in leaves(domain):
        if leaf[0] != field:
            continue
        if leaf[1] == op and (leaf[2] == value or (isinstance(value, list) and isinstance(leaf[2], list) and set(leaf[2]) == set(value))):
            return True
        if op == "=" and leaf[1] == "in" and isinstance(leaf[2], list) and leaf[2] == [value]:
            return True
    return False


def check_build(spec, expect):
    problems = []
    widgets = spec.get("widgets", [])
    low, high = expect.get("widgets", [1, 8])
    if not low <= len(widgets) <= high:
        problems.append("%d widgets (expected %d to %d)" % (len(widgets), low, high))
    for widget in widgets:
        source = widget["data"]["source"]
        if expect.get("source") and source not in expect["source"]:
            problems.append("widget %s reads %s (expected %s)" % (widget["id"], source, " or ".join(expect["source"])))
    first = widgets[0]["data"] if widgets else {}
    if expect.get("measures_any"):
        fields = {m.get("field") or "__count" for w in widgets for m in w["data"].get("measures", [])}
        if not fields & set(expect["measures_any"]):
            problems.append("measures %s (expected one of %s)" % (sorted(fields), expect["measures_any"]))
    for wanted in expect.get("must_filter", []):
        if not any(has_filter(w["data"].get("domain", []), wanted) for w in widgets):
            problems.append("no filter %s" % (wanted,))
    return problems, first


def compare_value(rpc, board_id, spec, compare, expected, tz_name):
    widget = spec["widgets"][min(compare.get("widget", 0), len(spec["widgets"]) - 1)]
    out = rpc.call("levelix.board", "lx_run", [board_id, [widget["id"]]], tz=tz_name)["widgets"][widget["id"]]
    if "frame" not in out:
        return ["widget %s does not run: %s" % (widget["id"], (out.get("error") or {}).get("message"))]
    frame = out["frame"]
    dims = [c for c in frame["columns"] if c["role"] == "dimension"]
    measure_column = next(i for i, c in enumerate(frame["columns"]) if c["role"] == "measure")
    how = compare["how"]
    if how == "any_value":
        return [] if frame["rows"] else ["the widget is empty"]
    if how == "sum_rows":
        got = sum(r[measure_column] or 0 for r in frame["rows"])
        want = expected["total"]
        ok = abs(got - want) <= max(abs(want) * TOLERANCE, 0.01)
        return [] if ok else ["the dashboard shows %s, Odoo says %s" % (round(got, 2), round(want, 2))]
    if how == "top_names":
        names = [str(r[0]) for r in frame["rows"] if r[0] not in ("Others",)][: len(expected["names"])]
        ok = bool(dims) and set(names) == set(expected["names"])
        return [] if ok else ["top: dashboard %s, Odoo %s" % (names, expected["names"])]
    return ["unknown comparison '%s'" % how]


# -- one question -----------------------------------------------------------------------------------------------------------------

def installed(rpc, modules):
    return all(rpc.call("ir.module.module", "search_count", [[["name", "=", m], ["state", "=", "installed"]]]) for m in modules)


def has_data(admin, rpc, model):
    """The model exists (asked as the administrator, who may look at models) and the asking user can see rows of it."""
    return bool(admin.call("ir.model", "search_count", [[["model", "=", model]]])) and bool(rpc.call(model, "search_count", [[]]))


def ask(rpc, text, tz_name, timeout):
    sent = rpc.call("levelix.ai.conversation", "lx_send", [False, text, {}], tz=tz_name)
    conversation = sent["conversation"]["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.5)
        message = rpc.call("levelix.ai.conversation", "lx_load", [[conversation]])["messages"][-1]
        if message["state"] != "streaming":
            return message
    raise TimeoutError("no answer in %d s" % timeout)


def run_question(rpcs, question, args):
    user = question["user"]
    rpc = rpcs.setdefault(user, Rpc(args.base, args.db, user, args.password or user))
    admin = rpcs["_admin"]
    missing = [m for m in question.get("requires", []) if not installed(admin, [m])]
    if missing:
        return {"status": "SKIP", "why": "module not installed: %s" % ", ".join(missing)}
    if question.get("needs_data"):
        try:
            if not has_data(admin, rpc, question["needs_data"]):
                return {"status": "SKIP", "why": "no data in %s on this database" % question["needs_data"]}
        except RuntimeError as error:  # the asking user may not read it at all
            return {"status": "SKIP", "why": "%s cannot read %s: %s" % (user, question["needs_data"], str(error)[:60])}
    started = time.time()
    try:
        answer = ask(rpc, question["question"], args.tz, args.timeout)
    except Exception as error:  # noqa: BLE001 - a failing question must not stop the run
        return {"status": "ERROR", "why": str(error)[:200]}
    result = {"seconds": round(time.time() - started, 1), "answer": answer["text"][:200], "error": answer["error"]}
    draft = next((b for b in answer["blocks"] if b["type"] == "board_draft"), None)
    expect = question["expect"]
    if answer["state"] == "error":
        return dict(result, status="FAIL", why="the assistant failed: %s" % answer["error"])
    if expect.get("refuse"):
        return dict(result, status="FAIL" if draft else "PASS", why="it built a dashboard for a question it should refuse" if draft else "")
    if not draft:
        return dict(result, status="FAIL", why="no dashboard was built; it said: %s" % (answer["text"][:120] or answer["error"]))
    spec = rpc.call("levelix.board", "lx_load", [draft["board_id"]])["spec"]
    problems, _first = check_build(spec, expect)
    compare = (question.get("oracle") or {}).get("compare")
    if compare:
        expected = oracle_value(rpc, question["oracle"], args.tz)  # as the same user: a salesperson's oracle sees his own orders
        if expected is not None:
            problems += compare_value(rpc, draft["board_id"], spec, compare, expected, args.tz)
    return dict(result, status="FAIL" if problems else "PASS", why="; ".join(problems), board=draft["board_id"])


def report(results, questions, args):
    ran = [(q, r) for q, r in zip(questions, results) if r["status"] in ("PASS", "FAIL", "ERROR")]
    passed = sum(1 for _q, r in ran if r["status"] == "PASS")
    by_category = collections.OrderedDict()
    for question, result in ran:
        row = by_category.setdefault(question["category"], [0, 0])
        row[1] += 1
        row[0] += result["status"] == "PASS"
    lines = ["# Golden set: first measurement" if args.write else "# Golden set", "",
             "Date: %s. Database: %s. Questions asked: %d, skipped: %d. **Correct: %d of %d (%.0f%%).**" % (
                 datetime.now().strftime("%Y-%m-%d %H:%M"), args.db, len(ran), len(results) - len(ran), passed, len(ran), 100.0 * passed / max(1, len(ran))), "",
             "| Category | Correct | Asked |", "|---|---|---|"]
    lines += ["| %s | %d | %d |" % (name, ok, total) for name, (ok, total) in by_category.items()]
    lines += ["", "## Every question", "", "| Id | Role | Question | Result | Why |", "|---|---|---|---|---|"]
    for question, result in zip(questions, results):
        lines.append("| %s | %s | %s | %s | %s |" % (question["id"], question["role"], question["question"], result["status"], (result.get("why") or "").replace("|", "/")))
    return "\n".join(lines) + "\n", passed, len(ran)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://localhost:8075")
    parser.add_argument("--db", default="aidash")
    parser.add_argument("--admin", default="lxadmin")
    parser.add_argument("--password", default=None, help="one password for every account (default: the login itself)")
    parser.add_argument("--tz", default="Asia/Tashkent")
    parser.add_argument("--only", default="", help="comma-separated question ids")
    parser.add_argument("--smoke", action="store_true", help="only the smoke question F00 (works with the pretend vendor)")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--write", default="", help="also write the report to this file")
    args = parser.parse_args()
    questions = json.load(open(ROOT + "/golden/questions.json"))["questions"]
    if args.smoke:
        questions = [q for q in questions if q.get("smoke")]
    elif args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    else:
        questions = [q for q in questions if not q.get("smoke")]
    rpcs = {"_admin": Rpc(args.base, args.db, args.admin, args.password or args.admin)}
    results = []
    for question in questions:
        result = run_question(rpcs, question, args)
        results.append(result)
        print("%-5s %-6s %-60s %s" % (question["id"], result["status"], question["question"][:60], result.get("why", "")[:110]), flush=True)
    text, passed, asked = report(results, questions, args)
    print("\n" + text.split("\n## Every question")[0])
    if args.write:
        open(args.write if args.write.startswith("/") else ROOT + "/" + args.write, "w").write(text)
    sys.exit(0 if passed == asked else 1)


if __name__ == "__main__":
    main()
