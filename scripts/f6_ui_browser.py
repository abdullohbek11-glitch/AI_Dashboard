"""F6 acceptance: every chart type, dashboard filters, cross-filter, comparison, calculated measures, in a real browser.

Run (needs Playwright + Chrome, container levelix-aidash up, scripts/seed_boards.py and scripts/seed_f6.py done):
    <python with playwright> scripts/f6_ui_browser.py

Every step of the UI test table of F6 in AI_DASHBOARD_PHASES.md is an assertion. Expected numbers come from independent SQL,
not from the engine under test. Screenshots go to a temp folder (not the repo). Accounts: password == login.
"""
import json
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import f3_ui_browser as base  # noqa: E402  (helpers: login, odoo_shell, check, number, shot, chartjs, echarts)
from playwright.sync_api import sync_playwright  # noqa: E402

check, shot, number, chartjs, echarts = base.check, base.shot, base.number, base.chartjs, base.echarts
BOARD = "F6 all types"
ALL = ["kpi_revenue", "kpi_year", "line_daily", "area_month", "bar_products", "pie_category", "pie_customers", "table_customers",
       "heatmap_week", "funnel_status", "treemap_mix", "gauge_target", "waterfall_category", "scatter_customers", "combo_month", "bar_seller"]

SETUP_TAX = '''
import json
manager = env["res.users"].search([("login", "=", "boshliq")])
tax = env["account.tax"].create({"name": "F6 test 12%", "amount": 12, "amount_type": "percent", "type_tax_use": "sale", "company_id": 1})
product = env["product.product"].create({"name": "F6 test service", "type": "service", "list_price": 1000000})
partner = env["res.partner"].search([("name", "=", "Hamkor")], limit=1)
pricelist = env["product.pricelist"].create({"name": "F6 test", "currency_id": env["res.company"].browse(1).currency_id.id, "company_id": 1})  # the order stays in company money
order = env["sale.order"].with_user(manager).create({"partner_id": partner.id, "user_id": manager.id, "company_id": 1, "pricelist_id": pricelist.id,
    "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1, "price_unit": 1000000, "tax_ids": [(6, 0, tax.ids)]})]})
order.action_confirm()
env.cr.commit()
print("TAXED " + json.dumps({"order": order.id, "product": product.id, "tax": tax.id, "pricelist": pricelist.id, "untaxed": order.amount_untaxed, "total": order.amount_total}))
'''

TEARDOWN_TAX = '''
for model, ids in (("sale.order", %(order)s), ("product.product", %(product)s), ("account.tax", %(tax)s), ("product.pricelist", %(pricelist)s)):
    records = env[model].browse(ids).exists()
    if model == "sale.order":
        records.sudo()._action_cancel() if hasattr(records, "_action_cancel") else None
        records.sudo().action_cancel()
    try:
        records.sudo().unlink()
    except Exception as error:  # an archived leftover is better than a failed clean-up
        records.sudo().write({"active": False}) if "active" in records._fields else None
        print("could not delete", model, error)
env.cr.commit()
print("CLEAN")
'''

EXPECTED_CODE = '''
import json, pytz
from datetime import datetime, timedelta, date
tz = pytz.timezone("Asia/Tashkent")
today = datetime.utcnow().astimezone(tz).date()

def utc(day):
    return tz.localize(datetime.combine(day, datetime.min.time())).astimezone(pytz.utc).replace(tzinfo=None)

def totals(first, last, user=None, product=None):
    """Revenue and orders of confirmed sales between two local days (inclusive), straight from the tables."""
    extra = ""
    args = [utc(first), utc(last + timedelta(days=1))]
    if user:
        extra += " AND o.user_id = %s"
        args.append(user)
    if product:
        extra += " AND l.product_id = %s"
        args.append(product)
    env.cr.execute("""SELECT COALESCE(SUM(l.price_subtotal / NULLIF(o.currency_rate, 0)), 0), COUNT(DISTINCT o.id),
               COALESCE(SUM(l.price_total / NULLIF(o.currency_rate, 0)), 0)
        FROM sale_order_line l JOIN sale_order o ON o.id = l.order_id
        WHERE o.state = 'sale' AND o.company_id = 1 AND l.display_type IS NULL AND o.date_order >= %s AND o.date_order < %s""" + extra, args)
    revenue, orders, taxed = env.cr.fetchone()
    return {"revenue": float(revenue), "orders": orders, "taxed": float(taxed)}

def pct(now, before):
    return None if not before else round((now - before) / before * 100, 1)

first30, first7 = today - timedelta(days=29), today - timedelta(days=6)
prev30 = (today - timedelta(days=59), today - timedelta(days=30))
sotuvchi = env["res.users"].search([("login", "=", "sotuvchi")]).id
cheese = env["product.product"].search([("name", "=", "Cheese 1kg")], limit=1)
now30, before30 = totals(first30, today), totals(*prev30)
env.cr.execute("""SELECT EXTRACT(dow FROM o.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tashkent')::int,
           EXTRACT(hour FROM o.date_order AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tashkent')::int, COUNT(DISTINCT o.id) AS n
    FROM sale_order o WHERE o.state = 'sale' AND o.company_id = 1 AND o.date_order >= %s AND o.date_order < %s
    GROUP BY 1, 2 ORDER BY n DESC, 1, 2 LIMIT 1""", [utc(first30), utc(today + timedelta(days=1))])
dow, hour, n = env.cr.fetchone()
oct_, sep_ = totals(date(2026, 10, 1), date(2026, 10, 31)), totals(date(2026, 9, 1), date(2026, 9, 30))
print("EXPECTED " + json.dumps({
    "today": str(today), "now30": now30, "before30": before30, "delta30": pct(now30["revenue"], before30["revenue"]), "delta_orders30": pct(now30["orders"], before30["orders"]),
    "last7": totals(first7, today), "seller30": totals(first30, today, user=sotuvchi), "cheese30": totals(first30, today, product=cheese.id),
    "heat": {"dow": dow, "hour": hour, "orders": n}, "october": oct_, "september": sep_, "delta_oct": pct(oct_["revenue"], sep_["revenue"]),
    "sotuvchi_id": sotuvchi,
}))
'''


def open_board(page, name):
    base.open_boards(page)
    page.click(".lxb-board-card:has-text('%s')" % name)
    page.wait_for_selector(".lxb-card", timeout=15000)


def settle(page, pause=700):
    """After a click that reloads the widgets: let the requests start, then wait until every card is ready again."""
    page.wait_for_timeout(pause)
    page.wait_for_function("() => [...document.querySelectorAll('.lxb-card')].filter(c => c.dataset.status === 'loading').length === 0", timeout=30000)
    page.wait_for_timeout(300)


def load_all(page):
    """Cards below the fold load when they scroll into view: scroll through the whole page once."""
    for _ in range(6):
        page.evaluate("() => { const e = document.querySelector('.lxb'); e.scrollTop = e.scrollTop + e.clientHeight * 0.8; }")
        page.wait_for_timeout(400)
    page.evaluate("document.querySelector('.lxb').scrollTop = 0")
    page.wait_for_function("() => [...document.querySelectorAll('.lxb-card')].every(c => ['ready', 'error'].includes(c.dataset.status))", timeout=60000)


def kpi_value(page, wid, index=0):
    return number(page.locator("section[data-widget-id=%s] .lxb-kpi__value" % wid).nth(index).get_attribute("title"))


def pick_period(page, value):
    page.select_option(".lxb-filter[data-filter-id=period] select", value=value)
    settle(page)


def main():
    made = json.loads(re.search(r"TAXED (\{.*\})", base.odoo_shell(SETUP_TAX)).group(1))
    try:
        run(made)
    finally:
        print(base.odoo_shell(TEARDOWN_TAX % {"order": [made["order"]], "product": [made["product"]], "tax": [made["tax"]], "pricelist": [made["pricelist"]]}).strip()[-40:])
    print("\nscreenshots (not part of the repo):", base.OUT)
    failed = [r for r in base.RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(base.RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


def run(made):
    expected = json.loads(re.search(r"EXPECTED (\{.*\})", base.odoo_shell(EXPECTED_CODE)).group(1))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=base.CHROME, headless=True)
        context = browser.new_context(viewport={"width": 1500, "height": 1000})
        page = base.login(context, "boshliq")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:300]))
        page.on("console", lambda m: errors.append(m.text[:300]) if m.type == "error" else None)
        open_board(page, BOARD)
        load_all(page)

        # 1 -- every type is drawn, readable, in light and in dark
        status = page.evaluate("() => Object.fromEntries([...document.querySelectorAll('.lxb-card')].map(c => [c.dataset.widgetId, c.dataset.status]))")
        drawn = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.lxb-card')].map(c => [c.dataset.widgetId,
            Boolean(c.querySelector('canvas, table.lxb-table, .lxb-kpi__value'))]))""")
        check("1", all(status[w] == "ready" for w in ALL) and all(drawn[w] for w in ALL),
              "%d widgets ready and drawn (kpi, line, area, bar, pie x2, table, heatmap, funnel, treemap, gauge, waterfall, scatter, combo)" % len(ALL))
        shot(page, "01_light")
        page.click("button:has-text('Dark')")
        page.wait_for_timeout(1200)
        dark_ok = page.evaluate("() => document.querySelector('.lxb').dataset.theme === 'dark' && document.querySelectorAll('canvas').length >= 10")
        shot(page, "02_dark")
        check("1b", dark_ok, "the same board in dark mode: charts redrawn (%d canvases)" % page.locator("canvas").count())
        page.click("button:has-text('Light')")
        page.wait_for_timeout(600)

        # 4 -- the arrow compares with the stretch before, by hand: (now - before) / before
        text = page.inner_text("section[data-widget-id=kpi_revenue] .lxb-kpi__delta")
        shown = float(re.search(r"([\d.]+)%", text).group(1)) * (1 if "▲" in text else -1)
        revenue = kpi_value(page, "kpi_revenue")
        orders_text = page.locator("section[data-widget-id=kpi_revenue] .lxb-kpi__delta").nth(1).inner_text()
        shown_orders = float(re.search(r"([\d.]+)%", orders_text).group(1)) * (1 if "▲" in orders_text else -1)
        check("4", abs(revenue - expected["now30"]["revenue"]) < 1 and shown == expected["delta30"] and shown_orders == expected["delta_orders30"]
              and "vs previous period" in text,
              "revenue %.0f (SQL %.0f); arrow %s%% (by hand %s%%), orders %s%% (%s%%); caption '%s'"
              % (revenue, expected["now30"]["revenue"], shown, expected["delta30"], shown_orders, expected["delta_orders30"], text.split("%")[-1].strip()))
        # a smooth line is drawn by ECharts: the earlier period is one dashed series next to the current one
        dashed = page.evaluate("(%s).getOption().series.filter(s => s.lineStyle && s.lineStyle.type === 'dashed').length" % echarts(page, "line_daily"))
        check("4b", dashed == 1, "the daily line draws the earlier period as one dashed series")

        # 2 -- changing the period reloads every widget on the model
        pick_period(page, "last_7_days")
        week = kpi_value(page, "kpi_revenue")
        line_rows = page.evaluate("(%s).getOption().xAxis[0].data.length" % echarts(page, "line_daily"))
        check("2", abs(week - expected["last7"]["revenue"]) < 1 and line_rows == 7,
              "last 7 days: revenue %.0f (SQL %.0f); the daily line has %d days" % (week, expected["last7"]["revenue"], line_rows))
        shot(page, "03_last_7_days")
        pick_period(page, "last_30_days")

        # a salesperson chosen from the list of the people the reader may see
        page.select_option(".lxb-filter[data-filter-id=seller] select", label="Sotuvchi")
        settle(page)
        seller = kpi_value(page, "kpi_revenue")
        check("2b", abs(seller - expected["seller30"]["revenue"]) < 1, "salesperson Sotuvchi: revenue %.0f (SQL %.0f)" % (seller, expected["seller30"]["revenue"]))
        page.select_option(".lxb-filter[data-filter-id=seller] select", index=0)
        settle(page)

        # a calendar month compares with the calendar month before (not with "the 31 days before")
        page.select_option(".lxb-filter[data-filter-id=period] select", value="custom")
        page.fill("input[aria-label=From]", "2026-10-01")
        page.dispatch_event("input[aria-label=From]", "change")
        page.fill("input[aria-label=To]", "2026-10-31")
        page.dispatch_event("input[aria-label=To]", "change")
        settle(page)
        october = kpi_value(page, "kpi_revenue")
        text = page.inner_text("section[data-widget-id=kpi_revenue] .lxb-kpi__delta")
        shown = float(re.search(r"([\d.]+)%", text).group(1)) * (1 if "▲" in text else -1)
        title = page.get_attribute("section[data-widget-id=kpi_revenue] .lxb-kpi__delta", "title")
        check("2c", abs(october - expected["october"]["revenue"]) < 1 and shown == expected["delta_oct"] and title.startswith("2026-09-01"),
              "1-31 October: revenue %.0f (SQL %.0f); arrow %s%% (October against September by hand: %s%%); compared days %s"
              % (october, expected["october"]["revenue"], shown, expected["delta_oct"], title))
        pick_period(page, "last_30_days")

        # 3 -- clicking a bar filters the others; clicking it again lifts the filter
        page.locator("section[data-widget-id=bar_products]").scroll_into_view_if_needed()
        page.wait_for_timeout(300)

        def click_first_bar():
            point = page.evaluate("""() => {
                const chart = %s, element = chart.getDatasetMeta(0).data[0], box = chart.canvas.getBoundingClientRect();
                const c = element.getCenterPoint(); return { x: box.x + c.x, y: box.y + c.y, label: chart.data.labels[0] };
            }""" % chartjs(page, "bar_products"))
            page.mouse.click(point["x"], point["y"])
            return point["label"]

        product = click_first_bar()
        settle(page)
        page.evaluate("document.querySelector('.lxb').scrollTop = 0")
        filtered = kpi_value(page, "kpi_revenue")
        chip = page.inner_text(".lxb-cross") if page.locator(".lxb-cross").count() else ""
        keeps = page.evaluate("(%s).data.labels.length" % chartjs(page, "bar_products"))  # the clicked chart keeps its context
        pie_slices = page.evaluate("(%s).data.labels.join('|')" % chartjs(page, "pie_category"))
        check("3", product == "Cheese 1kg" and abs(filtered - expected["cheese30"]["revenue"]) < 1 and product in chip and keeps > 3,
              "clicked '%s': revenue %.0f (SQL for that product %.0f); chip: '%s'; the clicked chart still lists %d products; pie now: %s"
              % (product, filtered, expected["cheese30"]["revenue"], " ".join(chip.split())[:50], keeps, pie_slices))
        shot(page, "04_cross_filter")
        page.locator("section[data-widget-id=bar_products]").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        click_first_bar()
        settle(page)
        page.evaluate("document.querySelector('.lxb').scrollTop = 0")
        back = kpi_value(page, "kpi_revenue")
        check("3b", abs(back - expected["now30"]["revenue"]) < 1 and page.locator(".lxb-cross").count() == 0,
              "clicked again: the filter is gone, revenue back to %.0f (SQL %.0f)" % (back, expected["now30"]["revenue"]))

        # 5 -- a heat map cell opens that weekday and hour's orders
        page.locator("section[data-widget-id=heatmap_week]").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        heat = expected["heat"]
        point = page.evaluate("""([dow, hour]) => {
            const chart = %s, option = chart.getOption();
            const x = option.xAxis[0].data.indexOf(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][(dow + 6) %% 7]);
            const y = option.yAxis[0].data.indexOf(String(hour).padStart(2, '0') + ':00');
            const [px, py] = chart.convertToPixel({ seriesIndex: 0 }, [x, y]);
            const box = chart.getDom().getBoundingClientRect();
            return { x: box.x + px, y: box.y + py, found: x >= 0 && y >= 0 };
        }""" % echarts(page, "heatmap_week"), [heat["dow"], heat["hour"]])
        page.mouse.click(point["x"], point["y"])
        page.wait_for_selector(".lxb-drill .lxb-table", timeout=15000)
        count_text = page.inner_text(".lxb-drill__count")
        panel_total = int(re.search(r"(\d+)", count_text.split("of")[-1]).group(1))
        check("5", point["found"] and panel_total == heat["orders"],
              "cell weekday %d, %02d:00: panel shows %d orders, SQL says %d" % (heat["dow"], heat["hour"], panel_total, heat["orders"]))
        shot(page, "05_heatmap_drill")
        page.keyboard.press("Escape")

        # 6 -- a calculated measure: average order = revenue / orders, row by row and in the total
        rows = page.eval_on_selector_all("section[data-widget-id=table_customers] tbody tr", "els => els.map(e => [...e.children].map(c => c.textContent.trim()))")
        good = all(abs(number(r[1]) / number(r[2]) - number(r[3])) < 1 for r in rows[:-1] if r[0] != "Total")
        check("6", len(rows) >= 5 and good, "'Average order' equals revenue / orders in all %d rows" % (len(rows) - 1))

        # 7 -- a pie with many slices keeps the biggest ones and groups the rest
        labels = page.evaluate("(%s).data.labels" % chartjs(page, "pie_customers"))
        sizes = page.evaluate("(%s).data.datasets[0].data" % chartjs(page, "pie_customers"))
        revenue_all = expected["now30"]["revenue"]
        check("7", len(labels) == 8 and labels[-1] == "Others" and abs(sum(sizes) - revenue_all) < 1 and sizes[-1] > 0,
              "15 customers -> %d slices, the last is '%s'; slices add up to %.0f (SQL %.0f)" % (len(labels), labels[-1], sum(sizes), revenue_all))

        # 10 -- one switch for the amounts: every money widget follows, a pinned one does not, a count does not move
        page.evaluate("document.querySelector('.lxb').scrollTop = 0")
        segment = page.locator(".lxb-segment__btn")
        shown = [segment.nth(i).inner_text() for i in range(segment.count())]
        untaxed_total = kpi_value(page, "kpi_revenue")
        orders_before = kpi_value(page, "kpi_revenue", 1)
        table_rows = lambda: page.eval_on_selector_all("section[data-widget-id=table_customers] tbody tr", "els => els.map(e => [...e.children].map(c => c.textContent.trim()))")  # noqa: E731
        hamkor = lambda rows: next(r for r in rows if r[0] == "Hamkor")  # noqa: E731
        before = hamkor(table_rows())
        page.click(".lxb-segment__btn:has-text('With tax')")
        settle(page)
        taxed_total = kpi_value(page, "kpi_revenue")
        orders_after = kpi_value(page, "kpi_revenue", 1)
        after = hamkor(table_rows())
        pie_total = sum(page.evaluate("(%s).data.datasets[0].data" % chartjs(page, "pie_customers")))
        gauge_text = page.inner_text("section[data-widget-id=gauge_target]")
        check("10", shown == ["Without tax", "With tax"] and abs(untaxed_total - expected["now30"]["revenue"]) < 1
              and abs(taxed_total - expected["now30"]["taxed"]) < 1 and taxed_total > untaxed_total and orders_before == orders_after
              and abs(number(after[1]) - number(before[1]) - (made["total"] - made["untaxed"])) < 1
              and abs(number(after[4]) - number(before[4])) < 1 and abs(pie_total - expected["now30"]["taxed"]) < 1,
              "without tax %.0f (SQL %.0f) -> with tax %.0f (SQL %.0f); orders stay %d; Hamkor's revenue +%.0f (the order's tax %.0f), "
              "his pinned 'with tax' column unchanged; pie adds up to %.0f"
              % (untaxed_total, expected["now30"]["revenue"], taxed_total, expected["now30"]["taxed"], orders_after,
                 number(after[1]) - number(before[1]), made["total"] - made["untaxed"], pie_total))
        shot(page, "06_with_tax")
        page.click("section[data-widget-id=kpi_revenue] button[aria-label='How it was calculated']")
        page.wait_for_selector(".lxb-explain", timeout=10000)
        said = "Amounts: with tax." in page.inner_text(".lxb-explain")
        page.keyboard.press("Escape")
        page.click(".lxb-segment__btn:has-text('Without tax')")
        settle(page)
        back = kpi_value(page, "kpi_revenue")
        check("10b", said and abs(back - untaxed_total) < 1, "the explanation says 'Amounts: with tax.'; back to without tax: %.0f" % back)

        # the explanation names the period, the comparison and the formula without technical names
        page.locator("section[data-widget-id=kpi_revenue]").scroll_into_view_if_needed()
        page.click("section[data-widget-id=kpi_revenue] button[aria-label='How it was calculated']")
        page.wait_for_selector(".lxb-explain", timeout=10000)
        explain = page.inner_text(".lxb-explain")
        check("8", "Compared with the previous period" in explain and re.search(r"\d{4}-\d{2}-\d{2} – \d{4}-\d{2}-\d{2}", explain),
              "how it was calculated: %s" % " / ".join(l for l in explain.split("\n") if "Compared" in l or "Order Date" in l)[:120])
        page.keyboard.press("Escape")

        # 9 -- the same dashboard with another person's rights: their own numbers
        other = base.login(browser.new_context(viewport={"width": 1500, "height": 1000}), "sotuvchi")
        open_board(other, BOARD)
        other.wait_for_selector("section[data-widget-id=kpi_revenue][data-status=ready]", timeout=20000)
        mine = kpi_value(other, "kpi_revenue")
        check("9", abs(mine - expected["seller30"]["revenue"]) < 1 and mine < revenue_all,
              "the seller sees %.0f (SQL for his orders %.0f), the manager %.0f" % (mine, expected["seller30"]["revenue"], revenue_all))

        check("-", not errors, "no JavaScript errors in the console%s" % ("" if not errors else ": " + errors[0]))
        browser.close()


if __name__ == "__main__":
    main()
