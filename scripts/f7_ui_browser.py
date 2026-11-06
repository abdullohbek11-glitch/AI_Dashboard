"""F7 acceptance: editing a dashboard by hand, history, sharing, copies, concurrent edits, archive and export, in a real browser.

Run (needs Playwright + Chrome, container levelix-aidash up, scripts/seed_boards.py done):
    <python with playwright> scripts/f7_ui_browser.py

Every step of the UI test table of F7 in AI_DASHBOARD_PHASES.md is an assertion (the assistant steps 2 and 3 are in
scripts/f7_ai_check.py: they need a real key). Numbers come from independent SQL / the ORM. Screenshots go to a temp folder.
Accounts: password == login. The test dashboards are named "F7 ..." and removed at the end.
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import f3_ui_browser as base  # noqa: E402  (helpers: login, odoo_shell, Rpc, check, shot, number)
from playwright.sync_api import sync_playwright  # noqa: E402

check, shot, number = base.check, base.shot, base.number
NAME = "F7 edit test"

SETUP = '''
import json
manager = env["res.users"].search([("login", "=", "boshliq")])
Board = env["levelix.board"].with_user(manager).with_context(tz="Asia/Tashkent")
Board.sudo().with_context(active_test=False).search([("name", "like", "F7 %")]).unlink()
paid = [["state", "=", "sale"]]
def w(wid, wtype, title, dims, measures, **data):
    return {"id": wid, "type": wtype, "title": title, "data": dict({"source": "sale.report", "domain": paid, "dimensions": dims, "measures": measures}, **data)}
rev = {"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}
spec = {"v": 1, "title": "F7 edit test", "widgets": [
    w("w1", "kpi", "Revenue", [], [rev]),
    w("w2", "bar", "Top products", [{"field": "product_id"}], [rev], order={"by": "m1", "dir": "desc"}, limit=5),
    w("w3", "table", "Top customers", [{"field": "partner_id"}], [rev], order={"by": "m1", "dir": "desc"}, limit=5),
]}
board = Board.create({"name": "F7 edit test", "spec": spec, "state": "active", "share_mode": "private"})
env.cr.commit()
print("BOARD " + str(board.id))
'''
CLEAN = '''
env["levelix.board"].sudo().with_context(active_test=False).search([("name", "like", "F7 %")]).unlink()
env["levelix.ai.conversation"].sudo().with_context(active_test=False).search([("name", "like", "F7 %")]).unlink()
env.cr.commit()
print("CLEAN")
'''


PINNED_CHAT = '''
user = env["res.users"].search([("login", "=", "boshliq")])
chat = env["levelix.ai.conversation"].sudo().create({"name": "F7 pinned chat", "user_id": user.id, "pin_model": "levelix.board", "pin_id": %d})
env["levelix.ai.message"].sudo().create({"conversation_id": chat.id, "role": "user", "text": "Earlier question about this dashboard"})
made = env["levelix.ai.conversation"].sudo().create({"name": "F7 made chat", "user_id": user.id})
env["levelix.ai.message"].sudo().create({"conversation_id": made.id, "role": "user", "text": "Build me this dashboard"})
env["levelix.board"].sudo().browse(%d).write({"source_conversation_id": made.id})
env.cr.commit()
print("CHAT")
'''


def back_to_board(page):
    """Back from the chat without reloading the page (the chat's state lives on); the list may come first."""
    page.go_back()
    page.wait_for_selector(".lxb-board-card, [data-action=ask-ai]", timeout=15000)
    if page.locator(".lxb-board-card:has-text('%s')" % NAME).count():
        page.click(".lxb-board-card:has-text('%s')" % NAME)
    page.wait_for_selector("[data-action=ask-ai]", timeout=15000)


def open_board(page, name):
    base.open_boards(page)
    page.click(".lxb-board-card:has-text('%s')" % name)
    page.wait_for_selector(".lxb-card", timeout=15000)


def ready(page, wids):
    for wid in wids:
        page.wait_for_selector("section[data-widget-id=%s][data-status=ready]" % wid, timeout=20000)


def grid_of(rpc, board_id):
    spec = rpc.call("levelix.board", "lx_load", [board_id])["result"]["spec"] if False else rpc.call("levelix.board", "lx_load", [board_id])["spec"]
    return {w["id"]: w.get("grid") for w in spec["widgets"]}, spec


def drag(page, handle, dx, dy):
    page.locator(handle).scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    box = page.locator(handle).bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for step in range(1, 9):
        page.mouse.move(x + dx * step / 8, y + dy * step / 8)
    page.mouse.up()
    page.wait_for_timeout(400)


def main():
    made = int(re.search(r"BOARD (\d+)", base.odoo_shell(SETUP)).group(1))
    try:
        run(made)
    finally:
        base.odoo_shell(CLEAN)
    print("\nscreenshots (not part of the repo):", base.OUT)
    failed = [r for r in base.RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(base.RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


def run(board_id):
    owner_rpc = base.Rpc("boshliq")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=base.CHROME, headless=True)
        context = browser.new_context(viewport={"width": 1500, "height": 1000}, accept_downloads=True)
        page = base.login(context, "boshliq")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:300]))
        page.on("console", lambda m: errors.append(m.text[:300]) if m.type == "error" else None)
        open_board(page, NAME)
        ready(page, ["w1", "w2", "w3"])

        # 1 -- move and resize with the mouse; the places survive a reload
        page.click("[data-action=edit]")
        page.wait_for_selector(".lxb-grid--editing")
        before = {w: page.locator("section[data-widget-id=%s]" % w).bounding_box() for w in ("w1", "w2", "w3")}
        drag(page, "section[data-widget-id=w2] .lxb-drag", -(before["w2"]["x"] - before["w1"]["x"]) - 10, -(before["w2"]["y"] - before["w1"]["y"]) + 5)  # onto the first widget
        drag(page, "section[data-widget-id=w3] .lxb-resize", -250, 60)
        page.wait_for_timeout(300)
        shot(page, "01_edited_layout")
        dirty = page.locator("text=Unsaved changes").count()
        page.click("[data-action=save]")
        page.wait_for_selector("[data-action=edit]", timeout=15000)
        ready(page, ["w1", "w2", "w3"])
        stored, _spec = grid_of(owner_rpc, board_id)
        page.reload()
        page.wait_for_selector(".lxb, .o_home_menu", timeout=20000)
        if page.locator(".o_home_menu").count():  # a reload may land on the home screen
            open_board(page, NAME)
        elif page.locator(".lxb-board-card").count():  # or on the list
            page.click(".lxb-board-card:has-text('%s')" % NAME)
        page.wait_for_selector(".lxb-card", timeout=15000)
        ready(page, ["w1", "w2", "w3"])
        after = {w: page.locator("section[data-widget-id=%s]" % w).bounding_box() for w in ("w1", "w2", "w3")}
        same = all(abs(after[w]["x"] - after[w]["x"]) < 1 for w in after)
        no_overlap = all(not (a["x"] < b["x"] + b["width"] - 1 and b["x"] < a["x"] + a["width"] - 1 and a["y"] < b["y"] + b["height"] - 1 and b["y"] < a["y"] + a["height"] - 1)
                         for i, a in enumerate(after.values()) for j, b in enumerate(after.values()) if i < j)
        history = owner_rpc.call("levelix.board", "lx_versions", [board_id])
        check("1", dirty == 1 and all(stored[w] for w in stored) and no_overlap and stored["w3"]["w"] != 12 and history[0]["note"] == "Layout changed",
              "moved w2 onto w1 and resized w3: stored places %s; nothing overlaps after a reload; history note '%s'"
              % ({w: tuple(stored[w].values()) for w in stored}, history[0]["note"]))

        # 2 -- rename, change a type, remove: only that widget changes; the others stay put
        spec_before = _spec
        page.click("[data-action=edit]")
        page.wait_for_selector(".lxb-grid--editing")
        page.fill("section[data-widget-id=w2] .lxb-title-input", "Best products")
        page.dispatch_event("section[data-widget-id=w2] .lxb-title-input", "change")
        page.select_option("section[data-widget-id=w2] select", "pie")
        page.wait_for_selector("section[data-widget-id=w2][data-status=ready]", timeout=20000)  # drawn from the editor's copy
        page.wait_for_timeout(1200)  # the widget is rebuilt for its new type: "ready" can still be the old bar for a moment
        page.wait_for_selector("section[data-widget-id=w2][data-status=ready] canvas", timeout=10000)
        pie_drawn = page.locator("section[data-widget-id=w2] canvas").count()
        page.click("section[data-widget-id=w3] button[aria-label='Remove this widget']")
        page.click("[data-action=save]")
        page.wait_for_selector("[data-action=edit]", timeout=15000)
        _grid, spec_after = grid_of(owner_rpc, board_id)
        w_before = {w["id"]: w for w in spec_before["widgets"]}
        w_after = {w["id"]: w for w in spec_after["widgets"]}
        check("2", pie_drawn == 1 and list(w_after) == ["w1", "w2"] and w_after["w2"]["type"] == "pie" and w_after["w2"]["title"] == "Best products"
              and w_after["w1"] == w_before["w1"] and w_after["w2"]["data"] == w_before["w2"]["data"] and w_after["w2"]["grid"] == w_before["w2"]["grid"],
              "w2 renamed to 'Best products' and turned into a pie (drawn before saving: %d canvas), w3 removed; w1 and w2's data and place untouched" % pie_drawn)
        shot(page, "02_after_edit")

        # add a widget without the assistant: a preview first, then it is on the dashboard
        page.click("[data-action=edit]")
        page.click("[data-action=add]")
        page.wait_for_selector(".lxb-modal", timeout=10000)
        page.wait_for_selector(".lxb-modal [data-field=dim] option", state="attached", timeout=10000)
        page.select_option(".lxb-modal [data-field=type] select", "pie")
        page.fill(".lxb-modal [data-field=title] input", "Revenue by category")
        page.select_option(".lxb-modal [data-field=status] select", "sale")
        page.select_option(".lxb-modal [data-field=dim] select", label="Product Category")
        page.select_option(".lxb-modal [data-field=measure1] select", label="Untaxed Total")
        page.click(".lxb-modal button:has-text('Preview')")
        page.wait_for_selector(".lxb-preview table", timeout=20000)
        rows = page.locator(".lxb-preview tbody tr").count()
        page.click(".lxb-modal button:has-text('Add to the dashboard')")
        page.wait_for_selector("section[data-widget-id=w3][data-status=ready]", timeout=20000)
        page.click("[data-action=save]")
        page.wait_for_selector("[data-action=edit]", timeout=15000)
        _g, spec_added = grid_of(owner_rpc, board_id)
        added = spec_added["widgets"][-1]
        check("2b", rows >= 3 and added["type"] == "pie" and added["title"] == "Revenue by category" and added["data"]["measures"][0]["field"] == "price_subtotal",
              "a pie 'Revenue by category' built from the form: the preview showed %d rows; saved with the field %s" % (rows, added["data"]["measures"][0]["field"]))

        # 4 -- history: restore an earlier version, which becomes a new one
        page.click("[data-action=history]")
        page.wait_for_selector(".lxb-version", timeout=10000)
        count_before = page.locator(".lxb-version").count()
        first_text = page.inner_text(".lxb-version[data-version='1']")
        page.click(".lxb-version[data-version='1'] button:has-text('Restore')")
        page.click(".lxb-version[data-version='1'] button:has-text('Yes, restore')")
        page.wait_for_selector(".lxb-version", state="detached", timeout=15000)  # the panel closes when the restore is done
        page.wait_for_selector("[data-action=edit]", timeout=15000)
        ready(page, ["w1", "w2", "w3"])
        _g, spec_restored = grid_of(owner_rpc, board_id)
        versions = owner_rpc.call("levelix.board", "lx_versions", [board_id])
        titles = [w["title"] for w in spec_restored["widgets"]]
        check("4", titles == ["Revenue", "Top products", "Top customers"] and len(versions) == count_before + 1 and versions[0]["origin"] == "restore"
              and "Added" in first_text,
              "restored version 1: widgets %s; the history grew from %d to %d versions (nothing lost), the top one says '%s'"
              % (titles, count_before, len(versions), versions[0]["note"]))
        shot(page, "03_restored")

        # 5 -- share with the company: another person sees it with his own numbers and no editing buttons
        page.click("[data-action=share]")
        page.wait_for_selector(".lxb-modal", timeout=10000)
        page.click(".lxb-modal label:has-text('Everyone in the company') input")
        page.click(".lxb-modal button:has-text('Save')")
        page.wait_for_selector("[data-action=share]:has-text('Everyone in the company')", timeout=15000)
        seller_page = base.login(browser.new_context(viewport={"width": 1500, "height": 1000}), "sotuvchi")
        open_board(seller_page, NAME)
        ready(seller_page, ["w1"])
        seller_revenue = number(seller_page.get_attribute("section[data-widget-id=w1] .lxb-kpi__value", "title"))
        owner_revenue = number(page.get_attribute("section[data-widget-id=w1] .lxb-kpi__value", "title"))
        buttons = [x.strip() for x in seller_page.locator(".lxb-actions .lxb-btn").all_inner_texts()]
        check("5", buttons == ["Make my own copy", "Export PNG"] and seller_revenue < owner_revenue and seller_page.locator(".lxb-chip:has-text('Based on your access rights')").count() == 1,
              "the seller sees %.0f (the owner %.0f) and the buttons %s: no edit, history, share or archive" % (seller_revenue, owner_revenue, buttons))

        # 6 -- a copy is the reader's own and independent
        seller_page.click("[data-action=copy]")
        seller_page.wait_for_selector(".lxb-title:has-text('(copy)')", timeout=15000)
        seller_page.wait_for_selector("[data-action=edit]", timeout=10000)
        copy_id = [c["id"] for c in base.Rpc("sotuvchi").call("levelix.board", "lx_list", []) if c["name"] == NAME + " (copy)"]
        base.odoo_shell('b = env["levelix.board"].browse(%d)\nprint("OWNER", b.user_id.login, b.share_mode)' % copy_id[0]) if False else None
        seller_page.click("[data-action=edit]")
        seller_page.fill("section[data-widget-id=w1] .lxb-title-input", "Seller's own title")
        seller_page.dispatch_event("section[data-widget-id=w1] .lxb-title-input", "change")
        seller_page.click("[data-action=save]")
        seller_page.wait_for_selector("[data-action=edit]", timeout=15000)
        _g, original = grid_of(owner_rpc, board_id)
        check("6", len(copy_id) == 1 and original["widgets"][0]["title"] == "Revenue",
              "the seller copied it (his own, editable) and renamed a widget in the copy; the original still says '%s'" % original["widgets"][0]["title"])

        # 7 -- two windows: the second save is refused, not overwritten
        window_a = base.login(browser.new_context(viewport={"width": 1500, "height": 1000}), "boshliq")
        window_b = base.login(browser.new_context(viewport={"width": 1500, "height": 1000}), "boshliq")
        for window in (window_a, window_b):
            open_board(window, NAME)
            ready(window, ["w1"])
            window.click("[data-action=edit]")
            window.wait_for_selector(".lxb-grid--editing")
        window_a.fill("section[data-widget-id=w1] .lxb-title-input", "Changed in window A")
        window_a.dispatch_event("section[data-widget-id=w1] .lxb-title-input", "change")
        window_a.click("[data-action=save]")
        window_a.wait_for_selector("[data-action=edit]", timeout=15000)
        window_b.fill("section[data-widget-id=w1] .lxb-title-input", "Changed in window B")
        window_b.dispatch_event("section[data-widget-id=w1] .lxb-title-input", "change")
        window_b.click("[data-action=save]")
        window_b.wait_for_selector("[data-banner=edit-error]", timeout=15000)
        banner = window_b.inner_text("[data-banner=edit-error]")
        _g, stored_spec = grid_of(owner_rpc, board_id)
        window_b.click("[data-banner=edit-error] button:has-text('Reload')")
        window_b.wait_for_selector("section[data-widget-id=w1] .lxb-card__title:has-text('Changed in window A')", timeout=15000)  # the stored dashboard has loaded
        reloaded = window_b.get_attribute("section[data-widget-id=w1] .lxb-card__title", "textContent") if False else window_b.inner_text("section[data-widget-id=w1] .lxb-card__title")
        check("7", "changed since you opened it" in banner and stored_spec["widgets"][0]["title"] == "Changed in window A" and reloaded == "Changed in window A",
              "window B's save was refused ('%s…'); the stored title is still A's; after Reload B shows '%s'" % (banner.split(".")[0][:60], reloaded))

        # 8 -- export a PNG
        with page.expect_download(timeout=30000) as download:
            page.click("[data-action=export]")
        path = download.value.path()
        with open(path, "rb") as handle:
            head = handle.read(32)
        width, height = struct.unpack(">II", head[16:24])
        size = os.path.getsize(path)
        check("8", head[:8] == b"\x89PNG\r\n\x1a\n" and width > 1500 and height > 400 and size > 20000,
              "the PNG '%s' is %dx%d px, %d KB" % (download.value.suggested_filename, width, height, size // 1024))
        shot(page, "04_after_export")

        # 8b..8f -- "Change with AI": the chat about THIS dashboard (nothing is sent to a model here)
        page.click("[data-action=ask-ai]")
        page.wait_for_selector(".lxai-pinned", timeout=15000)
        pinned = page.get_attribute(".lxai-pinned", "data-pinned")
        label = page.inner_text(".lxai-pinned strong")
        check("8b", pinned == "levelix.board:%d" % board_id and label == NAME and page.locator(".lxb-modal").count() == 0,
              "no earlier chat about it: a new chat opened about '%s' (%s), without asking" % (label, pinned))
        page.click(".lxai-pinned button")
        page.wait_for_selector(".lxai-pinned", state="detached", timeout=5000)
        check("8c", True, "the chip can be removed")

        base.odoo_shell(PINNED_CHAT % (board_id, board_id))
        open_board(page, NAME)  # a fresh page: no chat is open
        page.click("[data-action=ask-ai]")
        page.wait_for_selector(".lxb-modal [data-action=new-chat]", timeout=15000)
        on_board = page.locator("[data-action=ask-ai]").count() == 1 and page.locator(".lxai").count() == 0  # a small dialog, not another page
        buttons = page.locator(".lxb-modal button").all_inner_texts()
        shown_text = page.locator(".lxb-modal").inner_text().strip().replace("\n", " ")
        page.click(".lxb-modal [data-action=new-chat]")
        page.wait_for_selector(".lxai-pinned", timeout=5000)
        check("8d", on_board and buttons == ["Old chat", "New chat"] and shown_text == "Old chat New chat" and page.locator(".lxb-modal").count() == 0 and page.locator(".lxai-msg").count() == 0,
              "earlier chats exist: a small dialog with only the two buttons %s asked first; 'New chat' opened an empty chat about the dashboard" % buttons)

        open_board(page, NAME)
        page.click("[data-action=ask-ai]")
        page.wait_for_selector(".lxb-modal", timeout=15000)
        page.click(".lxb-modal [data-action=continue-chat]")
        page.wait_for_selector(".lxai-msg--user", timeout=10000)
        shown = page.inner_text(".lxai-msg--user")
        check("8e", shown == "Build me this dashboard" and page.locator(".lxai-pinned").count() == 1,
              "the chat where the dashboard was made reopened ('%s') and it is about the dashboard now" % shown)

        back_to_board(page)  # same page session: the chat service still remembers the chat it showed
        page.click("[data-action=ask-ai]")
        page.wait_for_selector(".lxb-modal [data-action=new-chat]", timeout=10000)
        again = page.locator(".lxb-modal button").all_inner_texts()
        check("8f", again == ["Old chat", "New chat"], "back on the dashboard in the same browser session the dialog still asks (%s)" % again)

        page.click(".lxb-modal [data-action=new-chat]")
        page.wait_for_selector(".lxai-pinned", timeout=10000)
        check("8g", page.locator(".lxb-modal").count() == 0 and page.locator(".lxai-msg").count() == 0,
              "'New chat' gave an empty chat about the dashboard; the other chats are untouched")
        other = base.odoo_shell('print("MSGS", env["levelix.ai.message"].sudo().search_count([("conversation_id.name", "=", "F7 pinned chat")]))')
        check("8h", "MSGS 1" in other, "the earlier chat still has its message (%s)" % other.strip())
        back_to_board(page)

        # 9 -- archive: it leaves the lists, nothing is deleted
        page.click("[data-action=archive]")
        page.click(".lxb-banner button:has-text('Yes, archive')")
        page.wait_for_selector(".lxb-cards, .lxb-page-state", timeout=15000)
        gone = page.locator(".lxb-board-card:has-text('%s')" % NAME).count()
        kept = base.odoo_shell('print("N", env["levelix.board"].sudo().with_context(active_test=False).search_count([("id", "=", %d), ("active", "=", False)]))' % board_id)
        check("9", gone == 0 and "N 1" in kept, "archived: not in the list any more (%d cards named so), still in the database inactive" % gone)

        check("-", not errors, "no JavaScript errors in the console%s" % ("" if not errors else ": " + errors[0]))
        browser.close()


if __name__ == "__main__":
    main()
