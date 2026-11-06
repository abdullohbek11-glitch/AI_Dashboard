"""F5 acceptance: from a question in the chat to a dashboard draft, in a real browser, without a paid key.

The assistant talks to the pretend vendor (addons/levelix_ai_core/tests/fake_ai.py), which plays a careful model for the dashboard
questions: it looks up hints, describes the model, previews, builds, and repairs a spec when the server says so. So this checks
everything *around* the model (tools, repair loop, blocks, buttons, rights, drafts), not the model's own judgement: that is the
golden set (scripts/run_golden.py), which needs a real key (DEFERRED.md).

Run:  PYTHONPATH=<where playwright is installed> python3 scripts/f5_ui_browser.py
Needs: container levelix-aidash up; scripts/seed_boards.py and scripts/seed_ai.py done. Screenshots go to a temp folder.
"""
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import f3_ui_browser as base  # noqa: E402
import f4_ui_browser as f4  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, shot = base.check, base.shot
BUILD = "Build a dashboard of sales this month by day and the top 10 products"
CLEAN = '''
env["levelix.board"].sudo().with_context(active_test=False).search([("name", "in", ["Sales this month", "Sales, changed"])]).unlink()
env["levelix.ai.feedback"].sudo().search([]).unlink()
env.cr.commit()
'''


def new_chat(page):
    page.click(".lxai-side .lxai-btn--primary")
    page.wait_for_function("() => document.querySelectorAll('.lxai-msg').length === 0", timeout=10000)


def ask_dashboard(page, text, expect_draft=True):
    answer = f4.ask(page, text, timeout=60000)
    if expect_draft:
        page.wait_for_selector(".lxai-draft", timeout=20000)
        page.wait_for_function("() => { const c = document.querySelectorAll('.lxai-draft .lxb-card'); return c.length > 0 && [...c].every(e => e.dataset.status === 'ready'); }", timeout=40000)
        page.wait_for_timeout(500)
    return answer


def main():
    f4.ensure_fake_vendor()
    base.odoo_shell(f4.RESET + CLEAN)
    f4.set_params(provider="anthropic", privacy="aggregates", daily_limit=500, daily_tokens=0,
                  **{"%s_%s" % (v, k): x for v in f4.VENDORS for k, x in (("key", "test-key"), ("base_url", f4.FAKE))})
    boss_rpc = base.Rpc("boshliq")
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=base.CHROME, headless=True)

        def session(login):
            page = base.login(browser.new_context(viewport={"width": 1300, "height": 950}), login)
            page.on("pageerror", lambda e: errors.append("%s: %s" % (login, str(e)[:200])))
            page.on("console", lambda m: errors.append("%s: %s" % (login, m.text[:200])) if m.type == "error" else None)
            return page

        boss = session("boshliq")
        f4.open_chat(boss)

        # 1 -- the question becomes a draft, drawn live in the chat
        answer = ask_dashboard(boss, BUILD)
        cards = boss.locator(".lxai-draft .lxb-card").count()
        title = boss.inner_text(".lxai-draft .lxai-block__head strong")
        chip = boss.inner_text(".lxai-draft .lxai-block__head .lxai-chip")
        reply = answer.locator(".lxai-text").inner_text()
        check("1", cards == 2 and title == "Sales this month" and chip == "Draft" and "draft is ready" in reply,
              "draft '%s' (%s) with %d live widgets; the assistant says: '%s'" % (title, chip, cards, reply))
        shot(boss, "01_draft")

        # 2 -- "what I did", in plain words
        explain = boss.inner_text(".lxai-explain-block")
        technical = [w for w in ("sale.report", "price_subtotal", "product_uom_qty", "__count", "state =", "date_order") if w in explain]
        details_inside = boss.locator(".lxai-explain-block details").count() >= 1
        important = [boss.locator(".lxai-explain-block__widget").nth(i).locator(":scope > ul > li").count() for i in range(2)]
        check("2", "Status is Sales Order" in explain and "Order Date" in explain and not technical and max(important) <= 5 and details_inside,
              "plain sentences (%s...), no technical names %s, important lines per widget %s, the rest under Details"
              % (explain.split("\n")[2][:50], technical, important))
        shot(boss, "02_explain")

        # 3 -- Keep: it appears in the list, and opening it does not call the AI
        boss.click(".lxai-draft button:has-text('Keep')")
        boss.wait_for_selector(".lxai-draft .lxai-chip:has-text('Saved')", timeout=10000)
        calls_before = len(f4.vendor_log())
        f4.open_menu(boss, None, app="Levelix Boards")
        boss.wait_for_selector(".lxb-board-card:has-text('Sales this month')", timeout=20000)
        saved_card = boss.inner_text(".lxb-board-card:has-text('Sales this month')")
        started = time.time()
        boss.click(".lxb-board-card:has-text('Sales this month')")
        boss.wait_for_selector(".lxb-card[data-widget-id=w1][data-status=ready]", timeout=20000)
        boss.wait_for_selector(".lxb-card[data-widget-id=w2][data-status=ready]", timeout=20000)
        opened_in = time.time() - started
        check("3", "Draft" not in saved_card and len(f4.vendor_log()) == calls_before,
              "kept: no 'Draft' mark on its card; opening it took %.1f s and made no AI call (%d vendor requests before and after)" % (opened_in, calls_before))
        shot(boss, "03_saved_dashboard")

        # 4 -- the F3 drill works on a dashboard the AI built
        boss.locator("section[data-widget-id=w1]").scroll_into_view_if_needed()
        boss.wait_for_selector("section[data-widget-id=w1] canvas", timeout=10000)
        boss.wait_for_timeout(1500)
        point = boss.evaluate("""() => {
            const chart = %s, data = chart.getOption().series[0].data;
            let index = 0; data.forEach((v, i) => { if (v > data[index]) index = i; });
            const [x, y] = chart.convertToPixel({ gridIndex: 0 }, [index, data[index]]);
            const box = chart.getDom().getBoundingClientRect();
            return { x: box.x + x, y: box.y + y };
        }""" % base.echarts(boss, "w1"))
        boss.mouse.click(point["x"], point["y"])
        boss.wait_for_selector(".lxb-drill .lxb-table", timeout=15000)
        day = boss.inner_text(".lxb-drill__sub").strip()
        count_text = boss.inner_text(".lxb-drill__count")
        panel_total = int(re.search(r"(\d+)", count_text.split("of")[-1]).group(1))
        expected = boss_rpc.call("sale.order", "search_count", [[["state", "=", "sale"], ["date_order", ">=", base.utc_midnight(day)], ["date_order", "<", base.utc_midnight(day, 1)]]])
        check("4", panel_total == expected and expected > 0, "clicked %s on the AI-built dashboard: %d orders in the panel, the ORM says %d" % (day, panel_total, expected))
        boss.keyboard.press("Escape")

        # 5 -- counting cancelled orders too: the warning is on screen
        f4.open_chat(boss)
        new_chat(boss)
        answer = ask_dashboard(boss, "Build a dashboard of all sales including cancelled orders")
        warnings = boss.inner_text(".lxai-draft__warnings")
        check("5", "every status is counted" in warnings, "warning shown with the draft: '%s'" % warnings.split("\n")[0][:90])
        shot(boss, "04_warning")

        # 6 -- the options the assistant was unsure about change the dashboard, no AI involved
        new_chat(boss)
        ask_dashboard(boss, BUILD)
        sums = lambda: boss.evaluate("(%s).data.datasets[0].data.reduce((a, b) => a + (b || 0), 0)" % base.chartjs(boss, "w2").replace("section[data-widget-id=w2]", ".lxai-draft section[data-widget-id=w2]"))  # noqa: E731
        boss.wait_for_selector(".lxai-draft section[data-widget-id=w2] canvas", timeout=15000)
        boss.wait_for_timeout(1200)
        before_sum, calls_before = sums(), len(f4.vendor_log())
        option = boss.inner_text(".lxai-draft__option span")
        boss.click(".lxai-draft__option button")
        boss.wait_for_function("() => document.querySelectorAll('.lxai-draft__option').length === 0", timeout=15000)
        boss.wait_for_function("() => [...document.querySelectorAll('.lxai-draft .lxb-card')].every(e => e.dataset.status === 'ready')", timeout=20000)
        boss.wait_for_timeout(1500)
        after_sum = sums()
        draft_id = int(boss.get_attribute(".lxai-draft", "data-board-id"))
        field = boss_rpc.call("levelix.board", "lx_load", [draft_id])["spec"]["widgets"][1]["data"]["measures"][0]["field"]
        check("6", field == "qty_delivered" and after_sum != before_sum and len(f4.vendor_log()) == calls_before,
              "'%s' pressed: the measure became %s, the chart total went from %s to %s, no AI call" % (option, field, before_sum, after_sum))

        # 7 -- something that does not exist: an honest answer, no invented dashboard
        boards_before = boss_rpc.call("levelix.board", "search_count", [[]])
        new_chat(boss)
        answer = f4.ask(boss, "Build a dashboard of sales by mood", timeout=60000)
        text = answer.inner_text()
        check("7", "no data about mood" in text and boss.locator(".lxai-msg--assistant").last.locator(".lxai-draft").count() == 0
              and boss_rpc.call("levelix.board", "search_count", [[]]) == boards_before, "honest answer: '%s'; nothing was built" % text.split("\n")[0][:90])

        # 8 -- two users, the same question, each their own numbers
        seller = session("sotuvchi")
        f4.open_chat(seller)
        ask_dashboard(seller, BUILD)
        mine = int(boss.locator(".lxai-draft").last.get_attribute("data-board-id")) if boss.locator(".lxai-draft").count() else draft_id
        theirs = int(seller.get_attribute(".lxai-draft", "data-board-id"))
        seller_rpc = base.Rpc("sotuvchi")
        total = lambda rpc, board: sum(r[1] for r in rpc.call("levelix.board", "lx_run", [board, ["w1"]])["widgets"]["w1"]["frame"]["rows"])  # noqa: E731
        check("8", total(boss_rpc, draft_id) > total(seller_rpc, theirs) > 0 and mine != theirs,
              "the same question: boshliq's dashboard totals %.0f, sotuvchi's (own orders only) %.0f" % (total(boss_rpc, draft_id), total(seller_rpc, theirs)))
        shot(seller, "05_seller_draft")

        # 9 -- "Wrong answer?" is kept for the golden set
        boss.reload()
        f4.open_chat(boss)
        boss.locator(".lxai-conv").first.click()
        boss.wait_for_selector(".lxai-msg--assistant", timeout=10000)
        boss.locator(".lxai-mark button:has-text('Wrong answer?')").last.click()
        boss.fill(".lxai-mark__form input", "I wanted last month")
        boss.click(".lxai-mark__form button:has-text('Send')")
        boss.wait_for_selector(".lxai-mark:has-text('Marked as wrong')", timeout=10000)
        rows = base.Rpc("lxadmin").call("levelix.ai.feedback", "search_read", [[], ["question", "note", "block_types", "privacy"]])
        check("9", rows and rows[0]["note"] == "I wanted last month" and "dashboard" in rows[0]["question"].lower(),
              "the mark is in the log: question '%s', note '%s', answer blocks %s" % (rows[0]["question"][:40], rows[0]["note"], rows[0]["block_types"]) if rows else "no row")

        # 10 -- leaving without keeping: the draft is still there
        ask_dashboard(boss, "Build a dashboard of sales this month (repair)")
        f4.open_menu(boss, None, app="Levelix Boards")
        boss.wait_for_selector(".lxb-board-card", timeout=20000)
        listed = boss.inner_text(".lxb")
        boss.goto(base.BASE + "/odoo")
        f4.open_chat(boss)
        boss.locator(".lxai-conv").first.click()
        boss.wait_for_selector(".lxai-draft", timeout=15000)
        back = boss.locator(".lxai-draft").last.get_attribute("data-state")
        still_keep = boss.locator(".lxai-draft").last.locator("button:has-text('Keep')").count() == 1
        check("10", "Draft" in listed and back == "draft" and still_keep, "left the chat; the draft is in the dashboards list (marked Draft) and in the conversation with its Keep button")

        # extra -- the repair loop and the honest give-up, seen in the audit log
        ask_dashboard(boss, "Build a dashboard of sales this month (hopeless)", expect_draft=False)
        gave_up = boss.locator(".lxai-msg--assistant").last.inner_text()
        admin = session("lxadmin")
        f4.open_menu(admin, "Tool Calls")
        admin.wait_for_selector(".o_list_view", timeout=20000)
        admin.wait_for_timeout(800)
        rows = admin.eval_on_selector_all(".o_data_row", "els => els.map(e => [e.querySelector('td[name=name]').innerText.trim(), e.querySelector('td[name=error]')?.innerText.trim() || ''])")
        builds = [r for r in rows if r[0] == "build_dashboard"]
        failed = [r for r in builds if r[1]]
        check("x.repair", len(failed) >= 5 and "could not build" in gave_up and any("price_subtotl" in r[1] for r in failed),
              "audit log: %d build_dashboard calls, %d failed (the typo is named in the log); after the last allowed repair the assistant says: '%s'" % (len(builds), len(failed), gave_up.split("\n")[0][:70]))

        # extra -- every provider builds a draft end to end
        set_by = {}
        for vendor in ("openai", "gemini"):
            f4.set_params(provider=vendor)
            f4.open_chat(boss)
            new_chat(boss)
            ask_dashboard(boss, BUILD)
            set_by[vendor] = boss.locator(".lxai-draft .lxb-card").count()
        f4.set_params(provider="anthropic")
        check("x.vendors", set_by == {"openai": 2, "gemini": 2}, "the same question builds a 2-widget draft through OpenAI and Gemini formats too: %s" % set_by)

        check("-", not errors, "no JavaScript errors in the console%s" % ("" if not errors else ": " + errors[0]))
        browser.close()
    base.odoo_shell(f4.RESET + CLEAN)
    print("\nscreenshots (not part of the repo):", base.OUT)
    failed = [r for r in base.RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(base.RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
