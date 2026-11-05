import json, sys
from playwright.sync_api import sync_playwright
import tempfile
OUT=tempfile.mkdtemp(prefix="f2_ui_")+"/"  # screenshots stay outside the repo
print("screenshots in", OUT)
spec={"v":1,"title":"T5.1 sample","widgets":[{"id":"w1","type":"area","title":"Daily sales","data":{"source":"sale.report","domain":[["state","=","sale"]],"dimensions":[{"field":"date","granularity":"day"}],"measures":[{"id":"m1","field":"price_subtotal","agg":"sum","label":"Revenue"}],"fill_gaps":True},"interact":{"on_click":{"action":"drill","model":"sale.order","map":{"date":"date_order"},"columns":["name","partner_id","amount_total","state"]}}}]}
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless=True)
    pg=b.new_page(viewport={"width":1400,"height":850})
    pg.goto("http://localhost:8075/web/login?db=aidash")
    pg.fill("input[name=login]","sotuvchi"); pg.fill("input[name=password]","sotuvchi"); pg.click("button[type=submit]")
    pg.wait_for_selector(".o_navbar",timeout=30000)
    pg.goto("http://localhost:8075/odoo"); pg.wait_for_timeout(2500)
    pg.screenshot(path=OUT+"f2_0_apps.png")
    # open the Dashboards app from the app menu
    pg.click(".o_menu_toggle, .o_navbar_apps_menu button"); pg.wait_for_timeout(800)
    pg.screenshot(path=OUT+"f2_1_appmenu.png")
    pg.click(".o-dropdown-item:has-text('Levelix Boards'), a:has-text('Levelix Boards')"); pg.wait_for_selector(".lxb",timeout=20000)
    pg.click(".o_menu_sections a:has-text('Manage'), .o_menu_sections button:has-text('Manage')"); pg.wait_for_selector(".o_list_view", timeout=20000)
    pg.screenshot(path=OUT+"f2_2_list.png")
    pg.click(".o_list_button_add, button.o-kanban-button-new, button:has-text('New')"); pg.wait_for_selector(".o_form_view",timeout=20000); pg.wait_for_timeout(1500)
    pg.fill(".o_field_widget[name=name] input","UI test board")
    pg.screenshot(path=OUT+"f2_3_form_new.png")
    # type the spec into the ace editor
    pg.click(".ace_content"); pg.keyboard.press("Meta+a"); pg.keyboard.press("Delete")
    pg.evaluate("t=>{const e=window.ace.edit(document.querySelector('.ace_editor'));e.setValue(t,-1)}",json.dumps(spec,indent=2))
    pg.wait_for_timeout(500)
    pg.screenshot(path=OUT+"f2_4_form_spec.png")
    pg.click(".o_form_button_save"); pg.wait_for_timeout(2000)
    pg.screenshot(path=OUT+"f2_5_saved.png")
    print("version field after save:", pg.inner_text(".o_field_widget[name=version]"))
    # bad spec
    bad=json.loads(json.dumps(spec)); bad["widgets"][0]["data"]["measures"][0]["field"]="price_subtotl"
    pg.evaluate("t=>{const e=window.ace.edit(document.querySelector('.ace_editor'));e.setValue(t,-1)}",json.dumps(bad,indent=2))
    pg.wait_for_timeout(400); pg.click(".o_form_button_save"); pg.wait_for_timeout(1800)
    pg.screenshot(path=OUT+"f2_6_bad_spec.png")
    print("dialog text:", (pg.inner_text(".modal-body") if pg.query_selector(".modal-body") else (pg.inner_text(".o_notification") if pg.query_selector(".o_notification") else "none"))[:300])
    b.close()
