"""F3 acceptance: the dashboard page in a real browser (headless Chrome through Playwright).

Run (needs `pip install playwright`, Chrome installed, container levelix-aidash up, scripts/seed_boards.py done):
    PYTHONPATH=<where playwright is installed> python3 scripts/f3_ui_browser.py [--keep]

Every step of the UI test table in AI_DASHBOARD_PHASES.md (F3) is an assertion. Expected numbers come from
independent SQL / ORM calls, not from the engine under test. Screenshots go to a temp folder (not the repo).
Test accounts follow the seed convention: password == login.
"""
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8075"
DB = "aidash"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = tempfile.mkdtemp(prefix="f3_ui_") + "/"
ENV = dict(os.environ, DOCKER_HOST="unix://%s/.colima/default/docker.sock" % os.path.expanduser("~"))
RESULTS = []


def check(step, condition, note=""):
    RESULTS.append((step, bool(condition), note))
    print("%-5s %-4s %s" % (step, "OK" if condition else "FAIL", note))


# -- helpers: odoo shell, JSON-RPC ------------------------------------------------------------

def odoo_shell(code):
    run = subprocess.run(["docker", "exec", "-i", "levelix-aidash", "odoo", "shell", "-d", DB, "--no-http", "--log-level=error"],
                         input=code, capture_output=True, text=True, env=ENV, timeout=180)
    if run.returncode:
        raise RuntimeError(run.stderr[-800:])
    return run.stdout


class Rpc:
    def __init__(self, login):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        out = self.post("/web/session/authenticate", {"db": DB, "login": login, "password": login})
        assert out.get("result", {}).get("uid"), out

    def post(self, path, params):
        body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}).encode()
        request = urllib.request.Request(BASE + path, body, {"Content-Type": "application/json"})
        return json.load(self.opener.open(request))

    def call(self, model, method, args=None, kwargs=None):
        out = self.post("/web/dataset/call_kw/%s/%s" % (model, method), {"model": model, "method": method, "args": args or [], "kwargs": kwargs or {}})
        if "error" in out:
            raise RuntimeError(out["error"]["data"]["message"])
        return out["result"]


EXPECTED_CODE = '''
import json, pytz
from datetime import datetime, timedelta
tz = pytz.timezone("Asia/Tashkent")
today = datetime.utcnow().astimezone(tz).date()
start = tz.localize(datetime.combine(today - timedelta(days=90), datetime.min.time())).astimezone(pytz.utc).replace(tzinfo=None)
def totals(extra=""):
    env.cr.execute("""SELECT COALESCE(SUM(l.price_subtotal / NULLIF(o.currency_rate, 0)), 0), COUNT(DISTINCT o.id), COALESCE(SUM(l.product_uom_qty), 0)
        FROM sale_order_line l JOIN sale_order o ON o.id = l.order_id
        WHERE o.state = 'sale' AND o.company_id = 1 AND l.display_type IS NULL AND o.date_order >= %s """ + extra, [start])
    revenue, orders, qty = env.cr.fetchone()
    return {"revenue": float(revenue), "orders": orders, "qty": float(qty)}
seller = env["res.users"].search([("login", "=", "sotuvchi")]).id
print("EXPECTED " + json.dumps({"all": totals(), "seller": totals(" AND o.user_id = %d" % seller), "start_utc": str(start), "today": str(today)}))
'''

SETUP_STATES = '''
import json
manager = env["res.users"].search([("login", "=", "boshliq")])
Board = env["levelix.board"].with_user(manager)
Board.search([("name", "=", "F3 UI states")]).unlink()
def kpi(wid, title, x, **data):
    return {"id": wid, "type": "kpi", "title": title, "grid": {"x": x, "y": 0, "w": 6, "h": 4},
            "data": dict({"source": "sale.report", "domain": [["state", "=", "sale"]], "measures": [{"id": "m1", "agg": "count"}]}, **data)}
good = {"v": 1, "widgets": [kpi("ok", "Healthy", 0)]}
board = Board.create({"name": "F3 UI states", "share_mode": "company", "spec": good})
bad = {"v": 1, "widgets": [
    kpi("ok", "Healthy", 0),
    kpi("broken", "Broken model", 6, source="no.such.model"),
    {"id": "empty", "type": "area", "title": "Empty period", "grid": {"x": 6, "y": 4, "w": 12, "h": 6},
     "data": {"source": "sale.report", "domain": [["state", "=", "sale"], ["date", ">=", "today +400d"]],
              "dimensions": [{"field": "date", "granularity": "day"}], "measures": [{"id": "m1", "agg": "count"}]}},
    kpi("secret", "No access", 18, source="ir.config_parameter", domain=[]),
    {"id": "future", "type": "funnel", "title": "Not built yet", "grid": {"x": 0, "y": 10, "w": 12, "h": 6},
     "data": {"source": "sale.report", "domain": [["state", "=", "sale"]], "dimensions": [{"field": "partner_id"}], "measures": [{"id": "m1", "agg": "count"}]}},
]}
env.cr.execute("UPDATE levelix_board SET spec = %s::jsonb WHERE id = %s", [json.dumps(bad), board.id])  # skips the save-time check on purpose
env.cr.commit()
print("BOARD", board.id)
'''

TEARDOWN_STATES = '''
env["levelix.board"].sudo().search([("name", "=", "F3 UI states")]).unlink()
env.cr.commit()
'''


# -- helpers: browser ---------------------------------------------------------------------------

def login(context, user):
    page = context.new_page()
    page.goto(BASE + "/web/login?db=" + DB)
    page.fill("input[name=login]", user)
    page.fill("input[name=password]", user)
    page.click("button[type=submit]")
    page.wait_for_selector(".o_navbar", timeout=30000)
    return page


def open_boards(page):
    page.goto(BASE + "/odoo")
    page.wait_for_selector(".o_navbar", timeout=20000)
    page.click(".o_menu_toggle, .o_navbar_apps_menu button")
    page.click(".o-dropdown-item:has-text('Levelix Boards'), a:has-text('Levelix Boards')")
    page.wait_for_selector(".lxb", timeout=20000)


def open_board(page, name):
    open_boards(page)
    page.click(".lxb-board-card:has-text('%s')" % name)
    page.wait_for_selector(".lxb-card", timeout=15000)


def wait_ready(page, ids):
    for wid in ids:
        page.locator("section[data-widget-id=%s]" % wid).scroll_into_view_if_needed()
        page.wait_for_selector("section[data-widget-id=%s][data-status=ready]" % wid, timeout=20000)


def number(text):
    digits = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    return float(digits)


def chartjs(page, wid):
    return "window.Chart.getChart(document.querySelector('section[data-widget-id=%s] canvas'))" % wid


def echarts(page, wid):
    return "window.echarts.getInstanceByDom(document.querySelector('section[data-widget-id=%s] .lxb-chart__canvas'))" % wid


def shot(page, name):
    page.screenshot(path=OUT + name + ".png")


# -- the steps -----------------------------------------------------------------------------------------

def main():
    expected = json.loads(re.search(r"EXPECTED (\{.*\})", odoo_shell(EXPECTED_CODE)).group(1))
    manager_rpc = Rpc("boshliq")
    start = expected["start_utc"]
    base_domain = [["state", "=", "sale"], ["date_order", ">=", start]]
    odoo_shell(SETUP_STATES)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, headless=True)
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = login(context, "boshliq")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)[:300]))
            page.on("console", lambda m: errors.append(m.text[:300]) if m.type == "error" else None)

            # 1 -- open the page: full screen, skeleton first, charts after
            open_boards(page)
            shot(page, "01_list")
            page.route("**/lx_run", lambda route: (time.sleep(0.8), route.continue_()))
            page.click(".lxb-board-card:has-text('Sales overview')")
            page.wait_for_selector(".lxb-card", timeout=15000)
            skeletons = page.locator(".lxb-card .lxb-skeleton").count()
            shot(page, "02_skeleton")
            page.unroute("**/lx_run")
            wait_ready(page, ["revenue", "orders", "by_seller", "daily", "top_products", "customers"])
            height = page.evaluate("document.querySelector('.lxb').getBoundingClientRect().height")
            check("1", skeletons >= 1 and height >= 800, "skeleton cards while loading: %d, then 6 ready cards; page height %dpx" % (skeletons, height))
            page.locator("section[data-widget-id=revenue]").scroll_into_view_if_needed()
            shot(page, "03_board_light")

            # 2 -- numbers equal the independent SQL, in both chart libraries
            revenue = number(page.get_attribute("section[data-widget-id=revenue] .lxb-kpi__value", "title"))
            orders = number(page.inner_text("section[data-widget-id=orders] .lxb-kpi__value"))
            daily_sum = page.evaluate("(%s).getOption().series[0].data.reduce((a, b) => a + (b || 0), 0)" % echarts(page, "daily"))
            qty_sum = page.evaluate("(%s).data.datasets[0].data.reduce((a, b) => a + (b || 0), 0)" % chartjs(page, "top_products"))
            check("2", abs(revenue - expected["all"]["revenue"]) < 1 and orders == expected["all"]["orders"]
                  and abs(daily_sum - expected["all"]["revenue"]) < 1 and abs(qty_sum - expected["all"]["qty"]) < 0.01,
                  "revenue %.2f vs SQL %.2f; orders %d vs %d; area (ECharts) sums to %.2f; top-10 + Others (Chart.js) sums to %.2f vs %.2f"
                  % (revenue, expected["all"]["revenue"], orders, expected["all"]["orders"], daily_sum, qty_sum, expected["all"]["qty"]))

            # 3 -- click a day of the wave chart: that day's orders open in the side panel
            page.locator("section[data-widget-id=daily]").scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            point = page.evaluate("""() => {
                const chart = %s, data = chart.getOption().series[0].data;
                let index = 0; data.forEach((v, i) => { if (v > data[index]) index = i; });
                const [x, y] = chart.convertToPixel({ gridIndex: 0 }, [index, data[index]]);
                const box = chart.getDom().getBoundingClientRect();
                return { x: box.x + x, y: box.y + y };
            }""" % echarts(page, "daily"))
            page.mouse.click(point["x"], point["y"])
            page.wait_for_selector(".lxb-drill .lxb-table", timeout=15000)
            day = page.inner_text(".lxb-drill__sub").strip()
            panel_rows = page.locator(".lxb-drill tbody tr").count()
            count_text = page.inner_text(".lxb-drill__count")
            panel_total = int(re.search(r"(\d+)", count_text.split("of")[-1]).group(1))
            expected_day = manager_rpc.call("sale.order", "search_count", [[["state", "=", "sale"], ["date_order", ">=", utc_midnight(day)], ["date_order", "<", utc_midnight(day, 1)]]])
            dates = page.eval_on_selector_all(".lxb-drill tbody tr td:nth-child(3)", "els => els.map(e => e.textContent)")
            check("3", panel_total == expected_day and panel_rows == min(expected_day, 80) and all(d.startswith(day) for d in dates),
                  "clicked %s: panel shows %d of %d orders, ORM says %d; every row dated that local day: %s" % (day, panel_rows, panel_total, expected_day, all(d.startswith(day) for d in dates)))
            shot(page, "04_drill_day")
            page.keyboard.press("Escape")
            page.wait_for_selector(".lxb-drill", state="detached", timeout=5000)

            # 4 -- click the first product bar (Chart.js): orders containing that product
            page.locator("section[data-widget-id=top_products]").scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            point = page.evaluate("""() => {
                const chart = %s, bar = chart.getDatasetMeta(0).data[0].getCenterPoint();
                const box = chart.canvas.getBoundingClientRect();
                return { x: box.x + bar.x, y: box.y + bar.y };
            }""" % chartjs(page, "top_products"))
            page.mouse.click(point["x"], point["y"])
            page.wait_for_selector(".lxb-drill .lxb-table", timeout=15000)
            product = page.inner_text(".lxb-drill__sub").strip()
            text = page.inner_text(".lxb-drill__count")
            product_total = int(re.search(r"(\d+)", text.split("of")[-1]).group(1))
            expected_product = manager_rpc.call("sale.order", "search_count", [base_domain + [["order_line.product_id.display_name", "=", product]]])
            check("4", product_total == expected_product and expected_product > 0,
                  "bar '%s': panel total %d, ORM count of orders with that product %d" % (product, product_total, expected_product))
            shot(page, "05_drill_product")

            # 5 -- "Open in Odoo": the full list with the same filter
            page.click(".lxb-drill__foot .lxb-btn")
            page.wait_for_selector(".o_list_view", timeout=20000)
            page.wait_for_timeout(800)
            pager = page.inner_text(".o_pager_value").strip() + " / " + page.inner_text(".o_pager_limit").strip()
            list_total = int(page.inner_text(".o_pager_limit").strip().replace(",", ""))
            check("5", list_total == expected_product, "Odoo list opened with pager '%s' (expected %d records)" % (pager, expected_product))
            shot(page, "06_open_in_odoo")

            # 6 -- "how was this calculated": plain language, no technical names
            open_board(page, "Sales overview")
            wait_ready(page, ["daily"])
            page.click("section[data-widget-id=daily] .lxb-icon-btn")
            page.wait_for_selector(".lxb-explain", timeout=10000)
            explain = page.inner_text("section[data-widget-id=daily] .lxb-explain")
            page.click("section[data-widget-id=daily] .lxb-explain .lxb-link")
            page.wait_for_selector("section[data-widget-id=daily] .lxb-explain__list--detail", timeout=5000)
            full = page.inner_text("section[data-widget-id=daily] .lxb-explain")
            technical = [w for w in ("sale.report", "price_subtotal", "formatted_read_group", "__count", "state =", "date_order") if w in full]
            check("6", "Status" in explain and "Order Date" in explain and "Data source: Sales Analysis Report" in full and not technical,
                  "main lines: %s | details add the data source | technical names found: %s" % (" / ".join(explain.split("\n")[1:4]), technical))
            shot(page, "07_explain")
            page.click("section[data-widget-id=daily] .lxb-explain .lxb-icon-btn")

            # 7 -- dark / light: both libraries use the same colours
            page.click(".lxb-top__right .lxb-btn:has-text('Dark')")
            page.wait_for_function("document.querySelector('.lxb').dataset.theme === 'dark'")
            page.wait_for_timeout(1200)
            token = page.evaluate("getComputedStyle(document.querySelector('.lxb')).getPropertyValue('--lxb-cat-1').trim()")
            ec_color = page.evaluate("(%s).getOption().color[0]" % echarts(page, "daily"))
            cj = page.evaluate("(function(){const b = (%s).data.datasets[0].backgroundColor; return Array.isArray(b) ? b[0] : b})()" % chartjs(page, "top_products"))
            check("7", token.lower() == ec_color.lower() == cj.lower() == "#56a8e8",
                  "dark first colour: token %s, ECharts %s, Chart.js %s" % (token, ec_color, cj))
            shot(page, "08_board_dark")
            page.click(".lxb-top__right .lxb-btn:has-text('Light')")
            page.wait_for_function("document.querySelector('.lxb').dataset.theme === 'light'")
            page.wait_for_timeout(800)
            token_light = page.evaluate("getComputedStyle(document.querySelector('.lxb')).getPropertyValue('--lxb-cat-1').trim()")
            ec_light = page.evaluate("(%s).getOption().color[0]" % echarts(page, "daily"))
            check("7b", token_light.lower() == ec_light.lower() == "#0072b2", "light first colour: token %s, ECharts %s" % (token_light, ec_light))

            # 8 -- narrow window: one column, readable, in reading order
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(1000)
            columns = page.evaluate("getComputedStyle(document.querySelector('.lxb-grid')).gridTemplateColumns.split(' ').length")
            widths = page.evaluate("[...document.querySelectorAll('.lxb-card')].map(c => Math.round(c.getBoundingClientRect().width))")
            overflow = page.evaluate("document.querySelector('.lxb').scrollWidth > document.querySelector('.lxb').clientWidth + 1")
            check("8", columns == 1 and len(set(widths)) == 1 and not overflow, "grid columns %d, card widths %s, horizontal overflow %s" % (columns, set(widths), overflow))
            shot(page, "09_mobile")
            page.set_viewport_size({"width": 1400, "height": 900})

            # 10, 11 -- broken / empty / forbidden / unknown widgets stay inside their own cards
            open_board(page, "F3 UI states")
            page.wait_for_selector("section[data-widget-id=ok][data-status=ready]", timeout=20000)
            page.wait_for_selector("section[data-widget-id=broken][data-status=error]", timeout=20000)
            page.wait_for_selector("section[data-widget-id=empty][data-status=ready]", timeout=20000)
            page.wait_for_selector("section[data-widget-id=secret][data-status=error]", timeout=20000)
            page.locator("section[data-widget-id=future]").scroll_into_view_if_needed()
            page.wait_for_selector("section[data-widget-id=future][data-status=error]", timeout=20000)
            status = {w: page.get_attribute("section[data-widget-id=%s]" % w, "data-status") for w in ("ok", "broken", "empty", "secret", "future")}
            broken = page.inner_text("section[data-widget-id=broken]")
            check("10", status["ok"] == "ready" and status["broken"] == "error" and "Try again" in broken and "does not exist" in broken,
                  "statuses %s; broken card says: %s" % (status, " / ".join(broken.split("\n")[1:4])))
            empty = page.inner_text("section[data-widget-id=empty]")
            secret = page.inner_text("section[data-widget-id=secret]")
            future = page.inner_text("section[data-widget-id=future]")
            check("11", "No data for this period" in empty and "do not have access" in secret and "Try again" not in secret and "cannot be shown yet" in future and "Try again" not in future,
                  "empty card: '%s'; forbidden card: '%s'; unknown type: '%s'" % (empty.split("\n")[-1], secret.split("\n")[1], future.split("\n")[-1][:40]))
            shot(page, "10_states")

            # 9 -- the same dashboard with the seller's own rights
            seller_page = login(browser.new_context(viewport={"width": 1400, "height": 900}), "sotuvchi")
            open_board(seller_page, "Sales overview")
            wait_ready(seller_page, ["revenue", "orders"])
            seller_revenue = number(seller_page.get_attribute("section[data-widget-id=revenue] .lxb-kpi__value", "title"))
            seller_orders = number(seller_page.inner_text("section[data-widget-id=orders] .lxb-kpi__value"))
            chip = seller_page.locator(".lxb-chip:has-text('Based on your access rights')").count()
            check("9", abs(seller_revenue - expected["seller"]["revenue"]) < 1 and seller_orders == expected["seller"]["orders"]
                  and seller_revenue < revenue and chip == 1,
                  "seller sees %.2f / %d orders (SQL %.2f / %d), manager %.2f / %d; badge shown: %s"
                  % (seller_revenue, seller_orders, expected["seller"]["revenue"], expected["seller"]["orders"], revenue, orders, chip == 1))
            shot(seller_page, "11_seller")

            check("-", not errors, "no JavaScript errors in the console%s" % ("" if not errors else ": " + errors[0]))
            browser.close()
    finally:
        odoo_shell(TEARDOWN_STATES)
    print("\nscreenshots (not part of the repo):", OUT)
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


def utc_midnight(day, plus_days=0):
    """UTC string of local (Tashkent) midnight of ``day`` (+ days), the way Odoo stores datetimes."""
    import datetime
    from zoneinfo import ZoneInfo
    d = datetime.date.fromisoformat(day) + datetime.timedelta(days=plus_days)
    local = datetime.datetime.combine(d, datetime.time.min, tzinfo=ZoneInfo("Asia/Tashkent"))
    return local.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    main()
