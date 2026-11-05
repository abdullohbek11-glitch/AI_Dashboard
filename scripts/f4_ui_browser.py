"""F4 acceptance: the settings page and the chat in a real browser, for all three providers, without a paid key.

The assistant talks to a pretend vendor (addons/levelix_ai_core/tests/fake_ai.py) that speaks the real wire format of
Anthropic, OpenAI and Gemini. The same steps with a real key are listed in DEFERRED.md.

Run:  PYTHONPATH=<where playwright is installed> python3 scripts/f4_ui_browser.py
Needs: container levelix-aidash up, scripts/seed_boards.py and scripts/seed_ai.py done. Screenshots go to a temp folder.
Test accounts follow the seed convention: password == login (the key "test-key" is the pretend vendor's, not a real one).
"""
import json
import re
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import f3_ui_browser as base  # noqa: E402  (helpers: login, odoo_shell, Rpc, check, CHROME)
from playwright.sync_api import sync_playwright  # noqa: E402

FAKE = "http://127.0.0.1:9099"
VENDORS = {"anthropic": "Anthropic Claude", "openai": "OpenAI", "gemini": "Google Gemini"}
RESET = '''
for login in ("boshliq", "omborchi", "sotuvchi", "lxadmin"):
    user = env["res.users"].search([("login", "=", login)])
    env["levelix.ai.conversation"].sudo().with_context(active_test=False).search([("user_id", "=", user.id)]).unlink()
env.cr.commit()
'''
check, shot = base.check, base.shot


_ADMIN = []


def set_params(**params):
    """Change settings through the running server (as the administrator would), so its caches stay right."""
    if not _ADMIN:
        _ADMIN.append(base.Rpc("lxadmin"))
    for key, value in params.items():
        _ADMIN[0].call("ir.config_parameter", "set_param", ["levelix_ai." + key, value])


def in_container(code):
    run = subprocess.run(["docker", "exec", "levelix-aidash", "python3", "-c", code], capture_output=True, text=True, env=base.ENV, timeout=60)
    return run.stdout


def ensure_fake_vendor():
    if "[" not in in_container("import urllib.request;print(urllib.request.urlopen('%s/_log').read().decode())" % FAKE):
        subprocess.run(["docker", "exec", "-d", "levelix-aidash", "python3", "/mnt/extra-addons/levelix_ai_core/tests/fake_ai.py", "--port", "9099"], env=base.ENV)
        time.sleep(2)
    in_container("import urllib.request;urllib.request.urlopen('%s/_reset')" % FAKE)


def vendor_log():
    return json.loads(in_container("import urllib.request;print(urllib.request.urlopen('%s/_log').read().decode())" % FAKE) or "[]")


def open_menu(page, entry, app="Levelix AI"):
    page.goto(base.BASE + "/odoo")
    page.wait_for_selector(".o_navbar", timeout=20000)
    page.click(".o_menu_toggle, .o_navbar_apps_menu button")
    page.click(".o-dropdown-item:has-text('%s'), a:has-text('%s')" % (app, app))
    if entry:
        page.click(".o_menu_sections a:has-text('%s'), .o_menu_sections button:has-text('%s')" % (entry, entry))


def save_and_test(page, vendor, key):
    """Type a key, save the settings (Odoo asks for it before any button), then press Test Connection."""
    page.fill("[name=lx_ai_%s_key] input" % vendor, key)
    page.fill("[name=lx_ai_%s_base_url] input" % vendor, FAKE)
    page.click("button.o_form_button_save")
    page.wait_for_function("v => { const e = document.querySelector('[name=lx_ai_' + v + '_key] input'); return e && e.value === ''; }", arg=vendor, timeout=20000)  # the form came back without the key
    page.wait_for_timeout(500)
    page.click("button[name=lx_ai_test_connection]")


def open_chat(page):
    open_menu(page, None)
    page.wait_for_selector(".lxai textarea:not([disabled]), .lxai-empty", timeout=20000)
    page.wait_for_timeout(600)


def ask(page, text, timeout=30000):
    count = page.locator(".lxai-msg--assistant").count()
    page.fill(".lxai textarea", text)
    page.keyboard.press("Enter")
    try:
        page.wait_for_function("n => document.querySelectorAll('.lxai-msg--assistant').length > n", arg=count, timeout=10000)
    except Exception:
        banner = page.inner_text(".lxai-error--banner") if page.locator(".lxai-error--banner").count() else "(no banner)"
        raise RuntimeError("the question '%s' got no answer; banner: %s; state: %s" % (text, banner, page.inner_text(".lxai")[:300].replace("\n", " | ")))
    page.wait_for_selector(".lxai-msg--assistant:last-child:not([data-state=streaming])", timeout=timeout)
    page.wait_for_timeout(300)
    return page.locator(".lxai-msg--assistant").last


def main():
    ensure_fake_vendor()
    base.odoo_shell(RESET)
    set_params(provider="anthropic", privacy="aggregates", daily_limit=200, daily_tokens=0, timeout=120,
               **{"%s_%s" % (v, k): x for v in VENDORS for k, x in (("key", "test-key"), ("base_url", FAKE))})  # a clean start, whatever an aborted run left
    manager_rpc = base.Rpc("boshliq")
    orders = manager_rpc.call("sale.order", "search_count", [[["state", "=", "sale"]]])
    top = manager_rpc.call("sale.order", "formatted_read_group", [[["state", "=", "sale"]]],
                           {"groupby": ["partner_id"], "aggregates": ["amount_total:sum"], "order": "amount_total:sum desc", "limit": 5})
    top_names = [g["partner_id"][1] for g in top]
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=base.CHROME, headless=True)

        def session(login):
            page = base.login(browser.new_context(viewport={"width": 1300, "height": 850}), login)
            page.on("pageerror", lambda e: errors.append("%s: %s" % (login, str(e)[:200])))
            page.on("console", lambda m: errors.append("%s: %s" % (login, m.text[:200])) if m.type == "error" else None)
            page.on("response", lambda r: errors.append("%s: HTTP %d %s" % (login, r.status, r.url[:120])) if r.status == 404 else None)
            return page

        # 1 -- settings: key in, key never back, connection test says what is wrong (every provider)
        admin = session("lxadmin")
        leaked, bodies = [], []
        admin.on("response", lambda r: bodies.append(r) if "/web/dataset/call_kw" in r.url else None)
        for vendor, label in VENDORS.items():
            open_menu(admin, "Settings")
            admin.wait_for_selector("[name=lx_ai_provider]", timeout=20000)
            admin.click("[name=lx_ai_provider] label:has-text('%s')" % label)
            save_and_test(admin, vendor, "bad-key")
            admin.wait_for_selector(".modal-body", timeout=20000)
            message = admin.inner_text(".modal-body")
            wrong_key_said = "refused the API key" in message and "bad-key" not in message
            admin.click(".modal-footer button")
            save_and_test(admin, vendor, "test-key")
            admin.wait_for_selector(".o_notification:has-text('The connection works')", timeout=20000)
            works = "answered: OK" in admin.inner_text(".o_notification")
            admin.wait_for_timeout(500)
            shot(admin, "01_settings_" + vendor)
            admin.reload()
            admin.wait_for_selector("[name=lx_ai_provider]", timeout=20000)
            html = admin.content()
            key_field = admin.input_value("[name=lx_ai_%s_key] input" % vendor) if admin.locator("[name=lx_ai_%s_key] input" % vendor).count() else ""
            saved_note = "A key is saved" in admin.inner_text("body")
            leaked.append("test-key" in html or "bad-key" in html)
            check("1." + vendor, wrong_key_said and works and not key_field and saved_note and not leaked[-1],
                  "wrong key -> '%s…'; right key -> works; after reload the key field is empty (%s), 'a key is saved' shown (%s), key in page HTML (%s)"
                  % (message.split(".")[0][:46], not key_field, saved_note, leaked[-1]))
        seen = []
        for response in bodies:
            try:
                seen.append(response.text())
            except Exception:  # noqa: BLE001 - a navigation may have dropped the body
                pass
        check("1.rpc", seen and not any("test-key" in text or "bad-key" in text for text in seen),
              "%d RPC answers of the settings page, none contains a key" % len(seen))
        set_params(provider="anthropic", anthropic_key="test-key", openai_key="test-key", gemini_key="test-key")

        # 2, 3 -- the chat answers with the real numbers, for each provider
        boss = session("boshliq")
        for vendor in VENDORS:
            set_params(provider=vendor)
            open_chat(boss)
            answer = ask(boss, "How many sales orders are there?")
            text = answer.locator(".lxai-text").inner_text()
            kpi = boss.locator(".lxai-msg--assistant").last.locator(".lxai-kpi__value").inner_text()
            check("2." + vendor, "There are %d." % orders in text and kpi.replace(",", "").replace(" ", "") == str(orders),
                  "[%s] answer '%s', KPI card %s, Odoo says %d" % (vendor, text, kpi, orders))
            answer = ask(boss, "Who are my top 5 customers?")
            rows = answer.locator("tbody tr").count()
            shown = answer.locator("tbody tr td:first-child").all_inner_texts()
            check("3." + vendor, rows == 5 and shown == top_names, "[%s] table of %d customers; names match Odoo's own grouping: %s" % (vendor, rows, shown == top_names))
        shot(boss, "02_chat_table")
        set_params(provider="anthropic")

        # 2b -- "Open in Odoo" from an answer opens the same records
        open_chat(boss)
        ask(boss, "How many sales orders are there?")
        boss.click(".lxai-msg--assistant:last-child .lxai-link:has-text('Open in Odoo')")
        boss.wait_for_selector(".o_list_view", timeout=20000)
        boss.wait_for_timeout(600)
        total = int(boss.inner_text(".o_pager_limit").strip().replace(",", ""))
        check("2.open", total == orders, "'Open in Odoo' lists %d orders (Odoo: %d)" % (total, orders))

        # 4 -- a user without sales rights hears "no access", and learns nothing
        keeper = session("omborchi")
        open_chat(keeper)
        answer = keeper.locator(".lxai-msg--assistant")
        answer = ask(keeper, "How many sales orders are there?")
        body = keeper.inner_text(".lxai")
        check("4", "could not read" in body and str(orders) not in body.replace("How many sales orders are there?", "") and answer.locator(".lxai-block").count() == 0,
              "omborchi: '%s'; no number, no block" % answer.locator(".lxai-text").inner_text()[:70])
        shot(keeper, "03_no_access")

        # 5 -- structure-only mode: the vendor never sees a name; the user picks one on screen
        set_params(privacy="schema")
        base.odoo_shell("env['res.partner'].search([('name', '=', 'F4 Test Customer')]).unlink(); env['res.partner'].create({'name': 'F4 Test Customer'}); env.cr.commit()")
        open_chat(boss)
        boss.wait_for_selector(".lxai-chip")
        chip = boss.inner_text(".lxai-chip")
        in_container("import urllib.request;urllib.request.urlopen('%s/_reset')" % FAKE)
        answer = ask(boss, "Show the orders of customer F4")
        options = answer.locator(".lxai-choices button").all_inner_texts()
        shot(boss, "04_choices")
        boss.locator(".lxai-msg--assistant").last.locator(".lxai-choices button:has-text('F4 Test Customer')").click()
        boss.wait_for_selector(".lxai-msg--user:has-text('F4 Test Customer')", timeout=10000)
        boss.wait_for_selector(".lxai-msg--assistant:last-child:not([data-state=streaming])", timeout=20000)
        sent = json.dumps(vendor_log())
        names = ["F4 Test Customer", "Boshliq", "My Company"]
        check("5", chip == "Structure only" and "F4 Test Customer" in options and all(n not in sent for n in names),
              "mode '%s'; the user was offered %s; %d vendor requests hold no customer, user or company name (the user's own typed words only)"
              % (chip, options, len(vendor_log())))
        set_params(privacy="aggregates")
        base.odoo_shell("env['res.partner'].search([('name', '=', 'F4 Test Customer')]).unlink(); env.cr.commit()")

        # 6 -- the audit log shows every call, and no key
        open_menu(admin, "Tool Calls")
        admin.wait_for_selector(".o_list_view", timeout=20000)
        admin.wait_for_timeout(800)
        names_in_log = admin.eval_on_selector_all(".o_data_row td[name=name]", "els => els.map(e => e.innerText.trim())")
        page_text = admin.inner_text("body")
        check("6", {"aggregate", "pick_record"} <= set(names_in_log) and "test-key" not in page_text,
              "%d tool calls logged (%s); no key on the page" % (len(names_in_log), ", ".join(sorted(set(names_in_log)))))
        shot(admin, "05_audit")

        # 7 -- network cut: a readable error, the chat is not frozen
        set_params(anthropic_base_url="http://127.0.0.1:9")
        open_chat(boss)
        answer = ask(boss, "hello", timeout=60000)
        error_text = answer.inner_text()
        free = boss.locator(".lxai textarea").is_enabled()
        check("7", "could not be reached" in error_text and free and answer.locator("button:has-text('Try again')").count() == 1,
              "'%s'; input usable again: %s; retry offered" % (error_text.split("\n")[0][:60], free))
        shot(boss, "06_network_down")
        set_params(anthropic_base_url=FAKE)

        # 8 -- the model's text is shown as text, never as markup
        open_chat(boss)
        answer = ask(boss, "give me markdown")
        html = answer.locator(".lxai-text").inner_html()
        check("8", "<strong>Bold</strong>" in html and "<code>code</code>" in html and "&lt;b&gt;raw&lt;/b&gt;" in html
              and answer.locator(".lxai-text b").count() == 0 and answer.locator(".lxai-text li").count() == 2,
              "bold, code and a list are formatted; '<b>raw</b>' stays visible text")

        # 9 -- a slow answer: the status is shown, the box is locked meanwhile and free after
        open_chat(boss)
        boss.fill(".lxai textarea", "be slow please")
        boss.keyboard.press("Enter")
        boss.wait_for_selector(".lxai-status", timeout=5000)
        locked = boss.locator(".lxai textarea").is_disabled()
        boss.wait_for_selector(".lxai-msg--assistant:last-child:not([data-state=streaming])", timeout=20000)
        check("9", locked and boss.locator(".lxai textarea").is_enabled(), "while answering: status shown, input locked (%s); afterwards it is free" % locked)

        # 10 -- conversations: reopen from the list, archive
        before = boss.locator(".lxai-convs li").count()
        boss.locator(".lxai-conv").nth(1).click()
        boss.wait_for_selector(".lxai-msg--user", timeout=10000)
        reopened = boss.locator(".lxai-msg--user").count() >= 1
        boss.locator(".lxai-convs li").nth(1).locator(".lxai-icon-btn").click()
        boss.wait_for_timeout(600)
        check("10", reopened and boss.locator(".lxai-convs li").count() == before - 1, "a conversation reopens with its messages; archiving removes it from the list (%d -> %d)" % (before, before - 1))

        # 11 -- not set up: the user is told, the administrator gets the way in
        set_params(anthropic_key="")
        open_chat(boss)
        user_note = boss.inner_text(".lxai-empty")
        open_chat(admin)
        admin_has_button = admin.locator(".lxai-empty button:has-text('Open settings')").count() == 1
        check("11", "not set up" in user_note and "Ask your administrator" in user_note and admin_has_button,
              "user: '%s'; administrator sees an 'Open settings' button" % user_note.split("\n")[0])
        set_params(anthropic_key="test-key")

        # 12 -- the daily limit stops the next question with a readable message
        base.odoo_shell(RESET)
        set_params(daily_limit=1)
        limited = session("sotuvchi")
        open_chat(limited)
        ask(limited, "hello")
        limited.fill(".lxai textarea", "one too many")
        limited.keyboard.press("Enter")
        limited.wait_for_selector(".lxai-error--banner", timeout=10000)
        banner = limited.inner_text(".lxai-error--banner")
        check("12", "limit of 1 questions" in banner and limited.locator(".lxai textarea").is_enabled(), "'%s'" % banner[:60])
        set_params(daily_limit=200)

        check("-", not errors, "no JavaScript errors in the console%s" % ("" if not errors else ": " + errors[0]))
        browser.close()
    base.odoo_shell(RESET)
    print("\nscreenshots (not part of the repo):", base.OUT)
    failed = [r for r in base.RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(base.RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
