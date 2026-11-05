# PHASES_1_3_ANALYSIS — `levelix_board` F1 + F2 + F3 kodining tahlili

> Sana: 2026-11-05. Tahlil qilingan: `/Users/latibov/Levelix/AI_Dashboard/addons/levelix_board` (v19.0.1.0.0) + `tools/echarts` + `scripts/`.
> Bu hujjat `PHASE1_ANALYSIS.md` (faqat F1) ning davomi: endi **F1, F2 va F3** (ya'ni TZ'ning butun 1-bosqichi) qamrab olingan. `PHASE1_ANALYSIS.md` dagi qator raqamlari F2/F3 da o'zgargan fayllar uchun eskirgan, joriy raqamlar shu hujjatda.
> Manba hujjatlar: `AI_DASHBOARD_TZ.md` (qisqa TZ), `AI_DASHBOARD_TEXNIK_TZ.md` (quyida "T" + bo'lim raqami), `AI_DASHBOARD_PHASES.md` (reja).
> Dalil formati: `fayl:qator` (qator raqamlari 2026-11-05 dagi holatga tegishli, `addons/levelix_board/` dan boshlab). Tekshirilmagan narsa **TEKSHIRILMAGAN** deb belgilangan.

## 0. Uch muhim ogohlantirish (avval shuni o'qing)

**1. Bu tahlilni kodni yozgan sun'iy intellektning o'zi qildi.** Mustaqil tashqi taftish emas. Buni kamaytirish uchun: (a) hamma fayl qatorlarini grep bilan qayta oldim va hujjatdagi raqamlar shu natijadan; (b) kodni **jonli** sinadim (3.3-bo'lim: Odoo shell'da 18 ta sinov, haqiqiy brauzerda 11 ta qo'shimcha sinov, shuningdek 13 tekshiruvli qabul testi); (c) o'zim topgan kamchiliklarni yashirmadim (7-bo'lim). Baribir o'z ishimni baholayapman: muhim joylarni (huquqlar, drill) boshqa odam yoki alohida sub-agent ham ko'rib chiqsa yaxshi bo'ladi.

**2. Bu hujjat tahlil, tuzatish emas.** Kodga hech narsa o'zgartirilmadi. Jonli sinovlar vaqtinchalik yozuvlar yaratdi va ularni o'chirdi (Odoo sinovlari `rollback`, brauzer sinovi o'zi yaratgan "F3 gallery" dashboard'ini o'chirdi). Dev bazada faqat `scripts/seed_boards.py` ning "Sales overview" dashboard'i va `boshliq` sinov foydalanuvchisi qoldi.

**3. "Ishlaydi" degani nimani anglatadi.** Brauzer testlarim **headless Chrome** (Playwright) da, **faqat inglizcha interfeys**, **faqat `boshliq`, `sotuvchi` hisoblari**, **182 buyurtmalik seed ma'lumot** bilan o'tkazilgan. O'zbek/rus tili, katta ma'lumot, boshqa brauzerlar, ko'p kompaniyada ishlash, haqiqiy telefon, ekran o'qigich: **TEKSHIRILMAGAN** (8-bo'lim).

---

## 1. Umumiy xulosa

**Nima qilingan.** `levelix_board` endi to'liq ishlaydigan, AI'siz dashboard moduli:
- **F1, "miya".** JSON tavsif (spec) → tekshiruv → so'rov rejasi → foydalanuvchi huquqi bilan bajarish → brauzer chizadigan jadval (`Frame`) + "Men nima qildim" matni.
- **F2, "xotira va eshik".** Dashboard'ni saqlash (`levelix.board`, versiyalar), kim ko'rishi/o'zgartirishi (guruh, yozuv qoidalari), ochiq RPC (`lx_*`), **drill** serveri (nuqtani bossangiz shu guruhning yozuvlari), vaqtinchalik JSON forma.
- **F3, "yuz".** Brauzer sahifasi: dizayn tizimi, 4 turdagi vidjet (`kpi`, `line`/`area`, `bar`, `table`), ikki grafik kutubxonasi (Chart.js + o'zimiz yig'gan ECharts) bitta interfeys orqasida, drill yon paneli, "Qanday hisoblangan", yorug'/qorong'i rejim, mobil.

**Analogiya (PHASE1 dagisining davomi).** F1 oshxona edi. F2 qo'shdi: **buyurtmalar daftari** (spec saqlanadi, har o'zgarish yozib boriladi), **eshikdagi qorovul** (kim qaysi daftarni ko'rishi), **"shu raqam qayerdan?" oynasi** (drill: raqamni bossangiz, uni tashkil qilgan cheklar chiqadi; qorovul klientdan "qaysi cheklar" deb so'ramaydi, faqat "qaysi qator" deb so'raydi va cheklarni o'zi topadi). F3 qo'shdi: **zal**: stol, yorug'lik, likopchalar (vidjetlar), menyu (sahifa).

**Raqamlar.**

| Ko'rsatkich | Qiymat |
|---|---|
| Python ishlab chiqarish kodi (`lib/` + `models/` + manifest) | 2 367 qator (21 fayl); F1 oxirida 1 771 edi |
| XML/CSV (view, xavfsizlik, menyu) | 183 qator (5 fayl) |
| Frontend (`static/src`: JS + OWL XML + SCSS) | 1 716 qator (28 fayl) |
| ECharts bundle (yig'ilgan, kod emas) | 679 004 bayt (663 KB), `static/lib/echarts/` |
| Test kodi | Python 1 675 qator, **159 test**; JS 279 qator, **28 test** |
| Test natijasi (2026-11-05 10:29) | Python **0 xato, 0 yiqilish, 159 ta** (`scripts/run_tests.sh`); JS **28/28** (`scripts/run_js_tests.sh`) |
| Brauzer testi (`scripts/f3_ui_browser.py`) | **13/13** tekshiruv; qo'shimcha jonli "gallery" sinovi 11 ta tekshiruv (3.3-bo'lim) |
| Biznes ma'lumotga `sudo()`, `eval()`, `exec()` | **yo'q** (5.3-bo'lim grep) |
| Frontendda `innerHTML`, `t-raw`, `t-out`, `eval` | **yo'q** (grep: 0 ta) |
| TZ 1-bosqich qabul mezoni (kunni bosish → o'sha kun buyurtmalari) | **bajarildi**: 2026-10-20 → panelda 8 ta, ORM'da 8 ta |

**Eng muhim topilmalar** (7-bo'limda to'liq):
1. **`lx_save` noto'g'ri tuzilgan spec'da `TypeError` bilan yiqiladi** (F1 dagi #1 topilma qisman ochiq qolgan: `lx_run` himoyalandi, `_validate_spec`/`lx_save` yo'li himoyalanmagan). Endi bu ochiq RPC bo'lgani uchun foydalanuvchi "Internal Server Error" oladi (jonli L1, L8).
2. **Domain qiymatlari hali tekshirilmaydi** (`state = done` jimgina 0 qaytaradi). F1 dagi #3 topilma o'zgarishsiz (jonli L3).
3. **Oddiy foydalanuvchi o'z dashboard'ining `version`, `user_id`, `company_id` maydonlarini va versiya yozuvlarini ORM orqali o'zgartira/soxtalashtira oladi** (jonli L6, M1, M2). Spec'ga ta'sir qilmaydi, lekin F7 ("versiyaga qaytish") shu yozuvlarga tayanadi.

**F1 topilmalarining holati** (PHASE1_ANALYSIS 7.3):

| # | F1 dagi topilma | Hozir |
|---|---|---|
| 1 | Kutilmagan xato butun `_run_spec`ni qulatadi | **Tuzatilgan** `lx_run` yo'lida (`models/engine.py:100`, jonli L2: `INTERNAL`). **Ochiq** `_validate_spec`/`lx_save` yo'lida (L1, L8) |
| 2 | `explain` da `AccessError` qulatadi | **Tuzatilgan** (`models/engine.py:121-127`, jonli L5: `['#1']`) |
| 3 | Domain qiymati tekshirilmaydi | **Ochiq** (L3, L3b) |
| 6 | `widget_ids` yo'q id'ni jimgina tashlaydi | **Tuzatilgan** (`models/engine.py:65-68`, `UNKNOWN_WIDGET`) |
| 4 | TZ 5.1 misoli `compare` sababli rad etiladi | Ochiq (F6) |
| 5, 7–14 | qolganlari | 7.1-bo'limdagi jadvalda |

---

## 2. Modul xaritasi

### 2.1. Daraxt (hamma fayl, qator soni)

```
addons/levelix_board/
├── __manifest__.py              30   depends=["web"], data (4 fayl), assets: static/src/**/*, LGPL-3
├── __init__.py                   1
├── lib/                              ← toza Python (runner/drill/errors Odoo'ning istisnolariga tayanadi)
│   ├── (F1) errors 62 · i18n 10 · catalog 52 · spec 313 · domain 63 · filters 206 · validator 316
│   │        planner 179 · runner 91 · frame 198 · explain 140
│   └── drill.py                236   F2: drill sozlamasini tekshirish, maydon nomlarini almashtirish, guruhni topish
├── models/                           ← yupqa Odoo adapteri
│   ├── engine.py               173   F1+F2: _validate_spec, _normalise_spec, _run_spec, _run_widget, _drill_spec
│   ├── env_catalog.py           46   (F1) foydalanuvchi ko'ra oladigan maydonlar
│   ├── board.py                 97   F2: levelix.board (maydonlar, create/write, versiya yozish, action_open_board)
│   ├── board_version.py         20   F2: levelix.board.version
│   └── board_rpc.py            124   F2: ochiq lx_* metodlar (levelix.board ga _inherit)
├── security/   security.xml 21 · rules.xml 55 · ir.model.access.csv 5            F2
├── views/      board_views.xml 90 (ro'yxat/forma/qidiruv/action) · board_page.xml 12 (client action + menyu)   F2/F3
├── static/
│   ├── lib/echarts/            echarts.min.js 663 KB + LICENSE + NOTICE            F3 (tools/echarts da yig'iladi)
│   └── src/                                                                     F3, 1 716 qator
│       ├── lib/     batcher 41 · chart_options 132 · format 99 · frame_model 130 · grid 63 · theme 43     ← toza JS (node bilan sinaladi)
│       ├── core/    board_data 56 · board_theme 29 · error_dialogs 15           ← xizmatlar
│       ├── charts/  chart_adapter 111                                           ← ChartAdapter, ChartJsAdapter, EChartsAdapter
│       ├── widgets/ widget_registry 18 · shell/board_widget 149+34 · common/chart_body 81+21
│       │            kpi 88+13 · line 8 · bar 5 · table 57+32
│       ├── drill/   drill_panel 46+40       explain/ explain_panel 20+23
│       ├── page/    board_page 81+68        scss/ board.scss 213
└── tests/   Python 13 fayl 1 675 qator (159 test) · tests/js/lib.test.mjs 279 qator (28 test)

tools/echarts/   package.json, entry.js, build.mjs (npm run build → static/lib/echarts)
scripts/         run_tests.sh, run_js_tests.sh, f3_ui_browser.py (13 tekshiruv), seed_boards.py, + F0/F1 skriptlari
```

**Yo'q papkalar:** `controllers/` (kerak emas: hamma narsa ORM RPC orqali), `data/`, `i18n/` (F9), `demo/`.

### 2.2. Bog'liqlik yo'nalishlari

```
Brauzer                                            Server
BoardPage ─► BoardWidget ─► board_data (xizmat) ──► levelix.board.lx_*  (board_rpc.py)
   │            │ ▲                                      │
   │            ▼ │ widget_registry                      ▼
   │         kpi/line/bar/table ─► chart_body ─► adapter     levelix.board.engine  (engine.py)
   │                       │   (lib/chart_options, frame_model)    │
   └► DrillPanel           └─ ChartJsAdapter / EChartsAdapter      ├─► Validator ─► drill.check
                                                                   ├─► Planner ─► Runner ─► FrameBuilder ─► ExplainBuilder
                                                                   └─► drill.find_group / translate_domain ─► Runner.fetch
```

Qoidalar bo'yicha holat (T11):
- **Bir tomonlama bog'liqlik**: `levelix_board` hech qaysi `levelix_ai*` ni import qilmaydi (modul `depends=["web"]`, `__manifest__.py:15`). ✅
- **`lib/` toza**: `lib/` ichida `env`, `self.env`, `models.` yo'q (grep). `runner.py` yagona DB'ga tegadigan joy (`cr.execute` faqat `runner.py:74,78,80`). ✅
- **Model fayllari ≤ 300 qator**: eng kattasi `engine.py` 173. ✅ (`lib/spec.py` 313, `lib/validator.py` 316 qat'iy qoida doirasida emas, lekin chegaradan oshgan.)
- **Frontendda hisob-kitob yo'q**: hamma raqam serverdan. Istisno yo'q, lekin eslatma: KPI kartasi "oxirgi qator" qiymatini va trend uchun barcha qatorlarni ko'rsatadi (`lib/frame_model.js:90-101`), bu tanlov, hisob emas.

### 2.3. F2 va F3 da F1 kodiga kiritilgan o'zgarishlar

| Fayl | O'zgarish | Nega |
|---|---|---|
| `lib/frame.py:18,55,166` | `OTHERS_REF="__others__"`, `meta.totals`, `dim_ref` ommaviy | "Others" qatorini "Belgilanmagan"dan ajratish; jadval jami qatori |
| `lib/planner.py:83,129` | `Plan.totals` | `table` uchun jami |
| `lib/runner.py:43,56` | jami so'rovi; `fetch()` | jadval jami; drill yozuvlarini o'qish |
| `lib/validator.py:105` | `drill.check` chaqiriladi | saqlashda drill dry-run |
| `models/engine.py` | `_normalise_spec`, `_drill_spec`, `except Exception`, `widget_ids` tekshiruvi, `_resolve_names` himoyasi | F2 + F1 topilmalarini tuzatish |

---

## 3. To'liq oqim

### 3.1. Bitta vidjetning yo'li: brauzerdan serverga va qaytib (haqiqiy misol)

Dashboard "Sales overview" (`scripts/seed_boards.py`), vidjet `daily` (silliq `area`, ECharts), foydalanuvchi `boshliq`, vaqt zonasi Toshkent (UTC+5).

**1. Menyu → sahifa.** `views/board_page.xml:4-7`: `ir.actions.client` (`tag="levelix_board.board_page"`), ildiz menyu "Levelix Boards" shu action'ga ulangan (`:9`), ostida "Dashboards" (`:10`) va "Manage" (`:11`, vaqtincha JSON muharriri). `page/board_page.js:81` action'ni `registry.category("actions")` ga yozadi.

**2. Sahifa ro'yxatni oladi.** `BoardPage.onWillStart` (`page/board_page.js:23-34`) → `showList()` → `BoardData.list()` → `lx_list` (`core/board_data.js:20`). Server: `board_rpc.py:71-73` `search([], limit=500)`, har yozuvga `_lx_card` (`:53-68`). Yozuv qoidalari tufayli foydalanuvchi faqat o'zinikini va ulashilganini oladi (4.C bo'limi).

**3. Dashboard ochiladi.** Karta bosiladi → `open(id)` → `lx_load` (`board_rpc.py:76-85`) → `spec` + `own_rights` (egasi emas bo'lsa `true`) qaytadi. Brauzer `cells` ni hisoblaydi (`page/board_page.js:64-70` → `lib/grid.js:25-54` `placeWidgets`, `:56-58` `mobileOrder`). Grid o'rni CSS o'zgaruvchilari bilan beriladi (`lib/grid.js` `gridStyle`), tor ekranda `board.scss:196-204` ularni e'tiborsiz qoldiradi.

**4. Vidjet ko'rinadigan bo'lganda yuklanadi.** `BoardWidget` `IntersectionObserver` (`widgets/shell/board_widget.js:32`, `rootMargin: 200px`) bilan kutadi, keyin `load()` (`:93-123`). `BoardData.runWidget` (`core/board_data.js:28-36`) so'rovni `createBatcher` ga beradi (`lib/batcher.js`, 25 ms oyna): bir vaqtda ko'ringan vidjetlar **bitta** `lx_run` ga birlashadi.

**5. Server: `lx_run`** (`board_rpc.py:87-95`).
   - `_lx_board(id)` (`:39-51`): `id` butun son va `bool` emas; `browse().exists()`; `check_access("read")` (yozuv qoidalari ishlaydi); ko'rinmasa **"topilmadi"** (mavjudligi ham sirli, `NOT_FOUND` `:48`).
   - `_check_widget_ids` (`:22-27`): ro'yxat, ≤30, hammasi satr. `_check_no_filters` (`:30-32`): global filtr berilsa `UNSUPPORTED` (F6 gacha jimgina e'tiborsiz qoldirmaslik uchun).
   - `engine._run_spec(board.spec, ids, explain)` (`models/engine.py:58-75`): yo'q `widget_id` → `UNKNOWN_WIDGET` (`:65-68`); har vidjet `_run_widget` (`:83-103`).

**6. `_run_widget`** (`models/engine.py:83-103`): `Validator.validate_widget` (F1 + **drill dry-run** `validator.py:105`) → `_plan` (`:77-81`: tz, hafta boshi, `Planner`) → `Runner.run` (savepoint + 8 s timeout, `runner.py:72-91`) → `_currency_meta` → `FrameBuilder.build` → natija. `BoardError` → `{"error":...}` (`:98-99`), **boshqa har qanday istisno** → log + `INTERNAL` xatosi shu vidjetga (`:100-103`).

   Real natija (`daily`, 2026-10-20 qatori): `["2026-10-20", 5882000.0]`, `group_refs[i] = ["2026-10-19 19:00:00"]` (UTC kalit: Toshkent 20-oktabr yarim tuni).

**7. Brauzer: chizish.** `board_widget.js:100-103` kadrni `state.frame` ga qo'yadi; `isEmptyFrame` bo'sh bo'lsa "No data for this period". Aks holda `definition.component` (`widgets/line/line_widget.js`: `area` → `ChartBody`, `adapter(widget)` → `view.smooth` bo'lgani uchun `"echarts"`). `ChartBody.render` (`widgets/common/chart_body.js:48-80`): `seriesModel(frame)` (`lib/frame_model.js:23-75`) → `theme.tokens(root)` (CSS o'zgaruvchilaridan) → adapter `mount`. `EChartsAdapter.mount` (`charts/chart_adapter.js:61-66`) ECharts'ni **birinchi marta kerak bo'lganda** yuklaydi (`loadJS`, `:62`), `buildECharts` (`lib/chart_options.js:90`) sozlamani yasaydi.

**8. Nuqtani bosish.** ECharts `zr` hodisasi (`chart_adapter.js:64,73-98`): bosilgan piksel → kategoriya indeksi (eng yaqin ustun) → ko'p qatorli grafikda vertikal bo'yicha eng yaqin qator → `onPointClick({seriesIndex, pointIndex})`. `ChartBody` buni `rowIndex` ga aylantiradi (`series.rowIndex[pointIndex]`, `widgets/common/chart_body.js:64-66`), `BoardWidget.drill(rowIndex)` (`board_widget.js:124-135`): `isDrillableRow` ("Others" bosilmaydi) → sahifa `openDrill` (`board_page.js:73`) → `DrillPanel`.

**9. Server: `lx_drill`** (`board_rpc.py:103-111` → `models/engine.py:131-173`):
   1. Spec'ni o'qiydi, vidjetni topadi (`UNKNOWN_WIDGET`), **qayta tekshiradi** (foydalanuvchining o'z huquqi bilan).
   2. `drill.parse(widget.interact)` yo'q → `DRILL_NOT_CONFIGURED`. `group_ref` da `__others__` → `DRILL_OTHERS`.
   3. Vidjetni qayta ishga tushiradi (`others/totals/fill` o'chirilgan, `:149`), kelgan **haqiqiy guruhlar** orasidan `group_ref` ga mosini topadi (`drill.find_group`, `lib/drill.py:193-205`). Topilmasa `DRILL_BAD_REF`; faqat `fill_gaps` qo'shgan bo'sh kun bo'lsa bo'sh natija (`engine.py:152-157`). **Klient hech qachon domain yubormaydi**.
   4. Domain = `plan.domain + group["__extra_domain"]`, maydon nomlari `map` bo'yicha almashtiriladi (`translate_domain`, `lib/drill.py:178-190`). Mos juft yo'q → `DRILL_UNMAPPED`.
   5. `Runner.fetch` (`runner.py:56-62`): `search_count` + `search(limit=80).read(ustunlar)` **foydalanuvchi huquqi bilan**, savepoint va timeout ichida.
   6. Qiymatlar odam ko'radigan ko'rinishga (`format_cell`, `lib/drill.py:208-222`), `act_window` domain bilan qaytadi.

   Real natija (2026-10-20): `total=8`, ustunlar `[name, partner_id, date_order, amount_total, state]`, birinchi qator `['S00893', "Chorsu do'koni", '2026-10-20 23:42', 27000.0, 'Sales Order']`. Action domain:
   ```json
   [["state","=","sale"], ["date_order",">=","2026-08-06 19:00:00"],
    "&", ["date_order",">=","2026-10-19 19:00:00"], ["date_order","<","2026-10-20 19:00:00"]]
   ```
   (`date` → `date_order` almashgan; oxirgi ikki shart Odoo'ning o'zi hosil qilgan `__extra_domain`.)

**10. Panel.** `DrillPanel` (`drill/drill_panel.js`): `onWillStart` da `lx_drill`, raqamlar `formatFull` bilan guruhlanadi, "Open in Odoo" `action.doAction(result.action)`. `Esc` yopadi.

**Qo'shimcha yo'llar.** `lx_explain` (`board_rpc.py:97-101`) = `lx_run(explain=True)` ning faqat tushuntirish qismi. `lx_save` (`:114-124`): argumentlar → `_normalise_spec` (hajm, tuzilma, **saqlovchining huquqi bilan** to'liq tekshiruv) → `write({"spec"})` → yangi versiya (`models/board.py:71-83`).

### 3.2. Saqlash va versiyalar oqimi

`board.py:58-69` `create`: `spec_text` bo'lsa JSON'ga o'giriladi (`:62-63`), `_normalise_spec` (`:64`), `version=1` (`:65`), `super().create`, so'ng versiya yozuvi (`:68`). `write` (`:71-83`): spec o'zgarmasa (`board.spec == spec`, `:78`) versiya **o'smaydi**; o'zgarsa `version+1` va yangi `levelix.board.version` yozuvi (`:81-82`). Formadagi JSON matn (`spec_text`, `:28`) `compute` + `inverse` (`:47-55`): noto'g'ri JSON → `BoardError BAD_SPEC` (`:12-16`). `note`/`origin` kontekst kalitlari (`lx_note`, `lx_origin`, `:68,76`) orqali o'tadi.

### 3.3. Jonli sinovlar (bu hujjat uchun o'tkazildi)

**Odoo shell, rollback bilan** (skript: `/tmp/live_checks.py`, `/tmp/live2.py`, vaqtincha, repoga saqlanmagan):

| # | Sinov | Natija |
|---|---|---|
| L1 | `_validate_spec`, `having=[[["x"],">",1]]` | **`TypeError: unhashable type: 'list'`** (validator.py:266) |
| L1b | `order={"by":["m1"]}` | **`TypeError`** (validator.py:234) |
| L2 | `_run_spec`, domain qiymati lug'at `{"a":1}` | endi **qulamaydi**: shu vidjetda `INTERNAL` xatosi (F1 da butun chaqiruv qulagan edi) |
| L3 | `["state","=","done"]` (Odoo 19 da bunday holat yo'q) | xatosiz `[[0]]` (jimgina 0) |
| L3b | `["state","in","abc"]` (ro'yxat o'rniga satr) | xatosiz `frame`, `rows=[[0]]` |
| L3c | `["partner_id.nonexistent","=",1]` | `QUERY_FAILED` ("Invalid field res.partner.nonexistent...") |
| L5 | `_resolve_names("ir.config_parameter",[1])` huquqsiz foydalanuvchi bilan | `['#1']` (F1 da `AccessError` qulatgan) |
| L6 | egasi `user_id` ni boshqa foydalanuvchiga yozadi | **ruxsat etildi**; eski egasi endi ko'rolmaydi |
| L6c | egasi `company_id` ni o'zi a'zo bo'lmagan kompaniyaga yozadi | **ruxsat etildi** |
| L7 | `lx_list`, 31 ta dashboard | 9 ta so'rov, 8 ms |
| L8 | `lx_save` (egasi), `having` ro'yxat | **`TypeError`** (RPC'da "Internal Server Error" bo'ladi) |
| M1 | egasi ORM bilan `version=99` yozadi | **ruxsat etildi** (`b.version == 99`) |
| M2 | egasi `levelix.board.version` yozuvini o'zi yaratadi (`spec={"anything":"goes"}`, `origin="ai"`) | **ruxsat etildi**, tarixda ko'rinadi (`[1, 5]`) |
| M4 | egasi tarix yozuvini tahrirlaydi | `AccessError` (to'g'ri: yozish huquqi yo'q) |
| M5 | egasi dashboard'ni o'chiradi | o'chdi, tarix cascade bilan ketdi |

**Haqiqiy brauzer** (headless Chrome; `scripts/f3_ui_browser.py` = 13 tekshiruv, undan tashqari "gallery" sinovi, skript vaqtincha: `scratchpad/gallery.py`, repoga saqlanmagan):

| # | Sinov | Natija |
|---|---|---|
| B1–B12 | `f3_ui_browser.py`: skeleton, raqamlar SQL bilan teng, kun drill'i, tovar drill'i, "Open in Odoo", tushuntirish, tema, mobil, buzuq vidjet, bo'sh/ruxsatsiz/noma'lum tur, `sotuvchi` | **hammasi o'tdi** (13/13) |
| G1 | 6 xil vidjet bir sahifada (sparkline'li KPI, 3 o'lchovli KPI, oddiy chiziq, ustma-ust ustun 2 o'qli, silliq 2 o'qli, 2 o'qli jadval) | hammasi `ready` |
| G3 | KPI trendi: 2 o'lchovga 2 ta sparkline | ✅ |
| G4/G5 | 2 o'qli ustma-ust ustun (`stacked=true`) va ECharts 2 seriya | ✅. **Seriya tartibi har xil**: ustunda `[Administrator, Sotuvchi]`, ECharts'da `[Sotuvchi, Administrator]` |
| G6 | 2 o'qli jadval | sarlavha `SALESPERSON, STATUS, REVENUE, ORDERS`, 2 qator, jami qatori bor |
| G7 | jadval qatoriga fokus + `Enter` | panel ochildi, fokus "Close" tugmasiga o'tdi |
| G8 | Chart.js chiziq nuqtasini bosish | panel: 2026-09-27, 12 yozuv |
| G9 | tema 3 marta tez almashtirildi | kanvaslar soni o'zgarmadi (takror yo'q), konsolda ogohlantirish yo'q |
| G10 | oyna toraytirildi | ECharts kengligi 376, karta ichki kengligi 412−36=376: mos |
| G11 | `lx_run` butunlay uzildi (`route.abort`) | 6 karta xatoda; bitta "Try again" faqat shu kartani tiklaydi (5 ta qoladi). Xabarda ichki URL ko'rinadi |

---

## 4. Fayllar bo'yicha batafsil tahlil

PHASE1_ANALYSIS.md da F1 fayllari (`errors`, `i18n`, `catalog`, `spec`, `domain`, `filters`, `validator`, `planner`, `runner`, `frame`, `explain`, `env_catalog`) batafsil yozilgan; **bu yerda faqat o'zgargan va yangi fayllar**. F1 fayllarining qolgan qismi o'zgarmagan (qator raqamlari 2.3 jadvalida).

### A) `lib/` (yangi va o'zgargan)

#### A1. `lib/drill.py` (236 qator): yangi
- **Vazifa.** "Nuqta bosilganda nima ochiladi": sozlamani tekshirish, domain'dagi maydon nomlarini ochiladigan modelga moslash, bosilgan guruhni topish, qatorlarni ko'rsatish shakliga keltirish. Toza (DB'siz).
- **Funksiyalar.**
  - `parse(interact)` → `DrillConfig` yoki `None` (`:43-52`). `DrillConfig(model, map, columns, open_as)` (`:34`).
  - `check(widget, source, catalog, path)` (`:60-96`): `interact` faqat `on_click` kalitini qabul qiladi (`UNKNOWN_KEY`); `action` ∈ `drill/filter/open_record/none`; `filter` va `open_record` **nomi bilan taniladi, lekin `UNSUPPORTED`** (`:24,80`); `drill` uchun `_target_model` (`:98`: model bor va o'qiladimi), `_check_columns` (`:113`: ≤12, takror yo'q, maydon bor, x2many/binary/html/json emas → `DRILL_BAD_COLUMN`), `_check_map` (`:130`: ikki tomonda maydon bor), `_dry_run` (`:145`: **o'q va domain'dagi har maydonning juftligi bor** → aks holda `DRILL_UNMAPPED`).
  - `translate_name` (`:159-168`): `map` da bor → o'sha; nuqtali bo'lsa (`date.day_of_week`) birinchi qismi almashadi va qolgani saqlanadi; ochiladigan modelda xuddi shu nom bo'lsa → o'zi; aks holda `None`. `translate_domain` (`:178-190`) mantiqiy belgilarni (`&`, `|`, `!`) saqlab maydonlarni almashtiradi.
  - `find_group(groups, dims, group_ref, dim_ref)` (`:193-205`): `group_ref` ro'yxat, uzunligi o'qlar soniga teng, ichida ro'yxat/lug'at yo'q; haqiqiy guruhlardan `dim_ref` ro'yxati teng kelganini qaytaradi, aks holda `DRILL_BAD_REF`.
  - `format_cell`, `columns_meta`, `empty_result` (`:208-236`).
- **Misol.** `map={"date":"date_order"}`, `__extra_domain` `[('date','>=',...),('date','<',...)]` → `[["date_order",">=",...],["date_order","<",...]]` (3.1 oqim 9-qadam).
- **Xato/chekka holatlar.** Soxta `group_ref` (`[["id",">",0]]`, uzunligi boshqa, satr) → `DRILL_BAD_REF` (test `test_drill_engine.py`: `test_a_made_up_group_is_refused`, `test_the_client_cannot_slip_a_domain_in`). `group_ref` ichida `True` va `1` teng sanaladi (Python `True == 1`), amalda zararsiz.
- **Cheklov.** `format_cell` `datetime` qiymatni foydalanuvchi vaqt zonasida "YYYY-MM-DD HH:MM" qiladi (`:216-217`); `date` maydon ISO. `UNSHOWN_TYPES` (`:30`) ro'yxati qat'iy; `MAX_DRILL_ROWS=80` (`:26`), `MAX_COLUMNS=12` (`:27`).
- **TZ bilan mosligi: mos** (T7.1): `map`, `DRILL_UNMAPPED`, saqlashda dry-run, 80 qator + jami + act_window. `open_as` qiymati (`side_table/dialog/odoo_list`) tekshiriladi, lekin **frontend faqat `side_table` ko'rinishini biladi**: `dialog`/`odoo_list` tanlansa ham yon panel ochiladi (`drill_panel.js` `open_as` ni o'qimaydi, grep).

#### A2. `lib/frame.py` (198 qator): o'zgargan
- `OTHERS_REF="__others__"` (`:18`); "Others" qatorining `group_refs` kaliti `["__others__"]` (`:55`). Avval `[None]` edi va "Belgilanmagan" bilan aralashardi. `dim_ref` ommaviy (`:97`).
- `_totals` (`:166-177`): `table` uchun `meta.totals = {o'lchov_id: qiymat}`, faqat `sum`/`count`, `count` butunlanadi. `plan.totals` yoki umumiy so'rov yo'q bo'lsa `None`.
- **Chekka holat.** Jami butun to'plamniki, `limit` bilan kesilgan qatorlar yig'indisiga teng bo'lmasligi mumkin (test: `test_engine.py` `test_a_table_carries_the_grand_total_even_when_cut`). `having` bor jadvalda jami yo'q (`planner.py:129`).

#### A3. `lib/planner.py`, `lib/runner.py`, `lib/validator.py`: kichik o'zgarish
`Plan.totals` (`planner.py:83,129`), `Runner.fetch` (`runner.py:56-62`), `drill.check` chaqiruvi (`validator.py:105`). `_check_order` (`:226`) va `_check_having` (`:259`) o'zgarmagan: **ro'yxat kelsa `TypeError`** (`:234`, `:266`, jonli L1).

### B) `models/`

#### B1. `models/engine.py` (173 qator)
- **Vazifa.** Toza qismlarni Odoo muhitiga ulaydi; ochiq `lx_*` metodlar shuni chaqiradi.
- **Metodlar.** `_validate_spec` (`:37-44`, qulamaydi, lekin L1 holati bundan mustasno), `_normalise_spec` (`:46-56`: hajm 2×256 KB oldindan, `Spec.from_raw`, `Validator`, `raise_if_invalid`, `(spec, warnings)` qaytaradi), `_run_spec` (`:58-75`), `_plan` (`:77-81`), `_run_widget` (`:83-103`), `_currency_meta` (`:105-119`), `_resolve_names` (`:121-127`), `_drill_spec` (`:131-173`).
- **Muhim qaror.** `except Exception` (`:100`) **ataylab** keng: yagona joy; logga `exception` bilan yoziladi (`:101`), brauzerga faqat "internal error" va `INTERNAL` kodi ketadi (ichki matn sizmaydi; test `test_an_unexpected_bug_stays_inside_its_widget`: `"boom" not in out`). T11 ("bo'sh `except Exception` yo'q") bilan zid emas: bo'sh emas, sabab izohda yozilgan, lekin qoidaning **istisnosi**.
- **Chekka holatlar.** `datetime.utcnow()` hali bor (`:81`, Python 3.12 da eskirgan). `_normalise_spec` `json.dumps(..., default=str)` bilan kirishni to'liq o'giradi (`:48`): juda katta kirishda xotira ishlatadi, lekin `_check` baribir undan keyin. Drill har bosishda vidjetni **to'liq qayta ishga tushiradi** (`:149`), keshlanmaydi.
- **TZ bilan mosligi: mos** (T9: argumentlar tekshiriladi, `sudo` yo'q).

#### B2. `models/board.py` (97 qator)
- **Maydonlar** (`:19-37`): `name`, `user_id` (egasi, `ondelete="restrict"`), `company_id`, `spec` (`fields.Json`), `spec_text` (hisoblanadigan), `version` (`readonly=True`, **faqat UI uchun**), `state` (`draft/active`), `share_mode` (`private/groups/company`), `group_ids` (m2m), `active`, `version_ids`.
- **`_check_share_groups`** (`:38-43`): `groups` rejimida kamida bitta guruh.
- **Eslatma (L6, M1).** `version`, `user_id`, `company_id` yozilishi ORM darajasida cheklanmagan: `readonly=True` faqat ko'rinish. Foydalanuvchi o'z dashboard'ini boshqaga berishi (`user_id`), boshqa kompaniyaga ko'chirishi (`company_id`, **u a'zo bo'lmagan kompaniyaga ham**) yoki `version` ni o'zgartirishi mumkin. Spec ga bu ta'sir qilmaydi (spec har doim tekshiriladi), lekin `UNIQUE(board_id, version)` (`board_version.py:17`) bilan to'qnashuv va noto'g'ri tarix mumkin.
- **TZ: qisman mos** (T3.1). TZ'dagi `levelix.board.alert/schedule` F8 da.

#### B3. `models/board_version.py` (20 qator)
- `spec` (Json), `origin` (`manual/ai/restore`), `note`, `author_id`, `UNIQUE(board_id, version)` (`:17`), `ondelete="cascade"`.
- **Eslatma (M2).** Egasi `create` huquqiga ega (`ir.model.access.csv:4`) va qoida bunga to'sqinlik qilmaydi, shuning uchun u **o'zi xohlagan spec va `origin="ai"` bilan versiya yozuvi yarata oladi**. Yozuv spec'ning o'ziga ta'sir qilmaydi, lekin F7 dagi "orqaga qaytarish" shu yozuvdan spec oladi: qaytarishda spec **qayta tekshirilishi shart** (hozir `lx_restore` yo'q).

#### B4. `models/board_rpc.py` (124 qator): ochiq API
- **Metodlar** (`levelix.board` ga `_inherit`): `lx_list` (`:71`), `lx_load` (`:76`), `lx_run` (`:87`), `lx_explain` (`:97`), `lx_drill` (`:103`), `lx_save` (`:114`). Yordamchilar `_lx_board` (`:39`), `_lx_card` (`:53`), argument tekshiruvlari (`:18-32`).
- **Qoidalar.** Hamma metodda argument turi tekshiriladi (`BAD_ARGUMENT`), `bool` id rad etiladi (`:40`), ko'rinmas va arxivlangan dashboard `NOT_FOUND` (`:41-48`), yozish uchun `has_access("write")` (`:49`) → `NO_ACCESS`. `sudo` yo'q.
- **Chekka holatlar.** `lx_list` `limit=500`, sahifalash yo'q (`:14,73`). `lx_save` ikki marta tekshiradi (avval `_normalise_spec`, so'ng `write` ichida yana, `:121` va `board.py:72`): ortiqcha ish, lekin xavfsiz. `lx_save` `TypeError` bilan yiqiladi (L8).
- **Qolgan T9 metodlari yo'q:** `lx_restore`, `lx_share`, `lx_apply_patch` (F7).

### C) `security/`, `views/`

#### C1. `security/security.xml` (21 qator)
Kategoriya "Dashboards" → `res.groups.privilege` "Levelix Board" → guruh **`group_board_manager`** ("Board manager", `base.group_user` ni qamrab oladi). Odoo 19 usuli (`privilege_id`). **Eslatma:** TZ "board-manager" guruhi deydi; qo'shimcha guruh yo'q (hamma ichki foydalanuvchi o'z dashboard'ini yaratadi).

#### C2. `security/ir.model.access.csv` (5 qator)
| Model | Guruh | R | W | C | D |
|---|---|---|---|---|---|
| `levelix.board` | `base.group_user` | 1 | 1 | 1 | 1 |
| `levelix.board` | `group_board_manager` | 1 | 1 | 1 | 1 |
| `levelix.board.version` | `base.group_user` / manager | 1 | 0 | 1 | 0 |

#### C3. `security/rules.xml` (55 qator): yozuv qoidalari
| Qoida | Kim | Amal | Shart | Qator |
|---|---|---|---|---|
| `rule_board_company` | **global** (hamma) | hamma | `company_id` bo'sh yoki `company_ids` ichida | `:4-8` |
| `rule_board_read` | `base.group_user` | faqat o'qish | egasi **yoki** (`active` va `company`) **yoki** (`active` va `groups` va foydalanuvchi guruhi ro'yxatda, `user.all_group_ids`) | `:11-23` |
| `rule_board_owner_write` | `base.group_user` | yozish/yaratish/o'chirish | `user_id = user.id` | `:26-31` |
| `rule_board_manager` | manager | hamma | `(1,'=',1)` | `:34-38` |
| `rule_board_version_owner` | `base.group_user` | hamma | `board_id.user_id = user.id` | `:42-46` |
| `rule_board_version_manager` | manager | hamma | `(1,'=',1)` | `:49-53` |

- **Ishlaydi** (testlar): ko'rinmas dashboard topilmaydi, ulashilgani ko'rinadi, ko'ruvchi o'zgartira olmaydi (`AccessError`), manager hammasini ko'radi, tarix faqat egasiga, boshqa kompaniya ko'rinmaydi, ko'ruvchi **o'z huquqi bilan** raqam oladi (admin 3, sotuvchi 1; brauzerda 84 348 935 va 38 022 819).
- **Bo'shliqlar.** `levelix.board.version` da kompaniya qoidasi yo'q (faqat egasiga cheklangan). Owner-write qoidasi **yozishdan oldingi** holatni tekshiradi: `user_id`/`company_id` ni o'zgartirish to'sqinliksiz (L6).

#### C4. `views/board_views.xml` (90), `views/board_page.xml` (12)
Ro'yxat, forma (statusbar, `ace` JSON muharriri `mode: json`, "History" sahifasi, **"Open dashboard"** tugmasi `invisible="not id"`), qidiruv, action. `board_page.xml`: client action va menyu: ildiz **"Levelix Boards"** (`action_board_page` ga ulangan), ostida "Dashboards" va "Manage". **Tarixiy nuqta:** F2 da menyu nomi "Dashboards" edi va Odoo'ning o'z spreadsheet "Dashboards" ilovasi bilan chalkashdi; brauzer testi aniqladi.

### D) Frontend (`static/src`)

#### D1. `lib/` (toza JS, `node --test` bilan: 28 test)
- **`format.js` (99)**: `formatNumber` (`:34`): `<1000` to'liq, `≥1000` qisqa (K/M/B/T; `uz`: K/M/**mlrd**/trln, `ru`: тыс./млн/млрд/трлн; `:4-9`), yaxlitlash `999 960 → 1M` (1000K chiqmaydi). `formatFull` (guruhlangan), `formatDateLabel` (`:76`, UTC hisob: kun siljimaydi), `escapeHtml` (`:97`), valyuta `before/after`, `mixed` bo'lsa belgisiz. O'nlik ajratgich locale'ga bog'liq (`uz`: vergul).
- **`frame_model.js` (130)**: `seriesModel` (`:23`; 1 o'q: seriya = o'lchov; 2 o'q: seriya = ikkinchi o'q qiymati; `rowIndex` nuqtani qatorga bog'laydi; `muted` "Others" uchun), `deltaInfo` (`:77`), `kpiModel` (`:90`: **oxirgi qator = qiymat**), `tableModel` (`:103`: server jami), `isDrillableRow` (`:118`), `numberOptionsFor`.
- **`chart_options.js` (132)**: `buildChartJs` (`:23`; `sparkline` rejimi `:53`), `buildECharts` (`:90`). Ikkalasi bir xil `theme`, bir xil formatlovchilar. ECharts tooltip qo'lda `escapeHtml` bilan (`:105,108`), Chart.js tooltip matn. O'q yozuvlari `maxTicksLimit: 6` (`:46`), guruh nomlari tashlab ketilmaydi (`autoSkip:false`).
- **`grid.js` (63)**: 24 ustun, `clampCell`, `placeWidgets` (`:25`: `grid` bor joyida, qolgani oqim bilan), `mobileOrder`, `gridStyle` (CSS o'zgaruvchilari).
- **`theme.js` (43)**: tokenlar → `{text, grid, palette[8], ...}`, `withAlpha`. **`batcher.js` (41)**: 25 ms oynada so'rovlar birlashadi.

#### D2. `core/`
- **`board_data.js` (56)**: yagona RPC eshigi (`lx_list/load/run/drill/explain`), `runWidget` batcher orqali (`:28-36`). **Eslatma:** `batchers` Map'i har dashboard uchun o'sadi va tozalanmaydi (`:30`); amalda ahamiyatsiz.
- **`board_theme.js` (29)**: `data-theme` holati, `localStorage` (`levelix_board.theme`, `:11,18`), `tokens(el)` CSS o'zgaruvchilardan o'qiydi: ikki kutubxona bir xil rangda.
- **`error_dialogs.js` (15)**: `BoardError`/`SpecInvalid` ni Odoo "Invalid Operation" ogohlantirish oynasiga ulaydi (web klient oynani sinf nomi bo'yicha tanlaydi; brauzer testi bu xatoni topgan).

#### D3. `charts/chart_adapter.js` (111)
`ChartAdapter` interfeysi (`mount/update/onPointClick/resize/dispose`, `:13-21`). `ChartJsAdapter` (`:23-58`): `loadBundle("web.chartjs_lib")` (Odoo ichidagi Chart.js 4.4.5), bosish `getElementsAtEventForMode("nearest", intersect:false)` (`:37`): ustun/nuqta aniq bosilmasa ham eng yaqini. `EChartsAdapter` (`:60-107`): `loadJS` (lazy, `:62`), bosish pikselni kategoriyaga o'giradi (`:73-98`). Ro'yxat `registry.category("levelix_board_charts")` (`:109`).

#### D4. `widgets/`
- **`widget_registry.js`**: `levelix_board_widgets` reyestri; yangi tur = yangi papka + bitta `add` (T8.2). Hozir: `kpi`, `line`, `area`, `bar`, `table`. **Boshqa 8 tur (`pie`, `heatmap`, `funnel`, `treemap`, `gauge`, `waterfall`, `scatter`, `combo`) serverda tekshiruvdan o'tadi, lekin frontendda yo'q**: "cannot be shown yet" xatosi (brauzer testi 11).
- **`shell/board_widget.js` (149)**: karta: holatlar (`idle/loading/ready/error`), `requestId` bilan eskirgan javobni tashlash (`:29,99,104,116`), `canRetry` (`:89`: `NO_ACCESS` va `UNKNOWN_TYPE` da qayta urinish yo'q), drill (`:124-135`), tushuntirish (`:137`). `IntersectionObserver` (`:32`).
- **`common/chart_body.js` (81)**: `generation` hisoblagichi bilan poyga (`:24,49,70`), `ResizeObserver` (`:75`), `prefers-reduced-motion` (`:58`), ekran o'qigich uchun yashirin jadval (`chart_body.xml:6`).
- **`kpi/kpi_widget.js` (88)**: kartalar, ▲▼ (**`compare_rows` bo'lsa**: server hozir `compare` ni rad etadi, shuning uchun amalda hech qachon chizilmaydi), trend chizig'i (`drawSparklines` `:62-80`).
- **`table/table_widget.js` (57)**: jadval, jami qatori, `Enter`/`Space` bilan ochish (`onKey`, `table_widget.xml:17`), `tabindex`.

#### D5. `explain/`, `drill/`, `page/`, `scss/`
`ExplainPanel` (muhim qatorlar + "Details"), `DrillPanel` (yon panel, `Esc`, fokus yopish tugmasiga), `BoardPage` (ro'yxat + dashboard, `reloadKey` bilan yangilash, tema tugmasi, "Based on your access rights" belgisi), `board.scss` (213): `.lxb` tokenlari (rang, shrift, bo'shliq, soya, burchak, harakat), yorug'/qorong'i (`[data-theme="dark"]`), 8 rangli Okabe-Ito palitra, mobil (`:196`), `prefers-reduced-motion` (`:206`). **libsass cheklovi:** `clamp()`, `min()`, `calc()` `#{"..."}` ichida yozilgan (`:142-143,176,184`), aks holda butun bazada "Style error" bo'ladi (brauzer testi buni topgan).

### E) `tests/`

| Fayl | Testlar | Sinalgan (F2/F3 dagi yangilari qalin) |
|---|---|---|
| `test_spec.py` | 11 | (F1) |
| `test_filters.py` | 18 | (F1) |
| `test_validator.py` | 20 | (F1) |
| `test_planner.py` | 13 | (F1) |
| `test_frame.py` | 21 | F1 + **jadval jami (qo'shiladigan o'lchovlar)**, boshqa vidjetda jami yo'q |
| `test_explain.py` | 9 | (F1) |
| `test_engine.py` | 16 | F1 + **kesilgan jadvalda butun jami** |
| **`test_board.py`** | **24** | **yozuv (versiya, o'zgarmagan spec, noto'g'ri spec, JSON matn, katta spec, guruh), ko'rinish (xususiy/kompaniya/guruh/draft), ko'ruvchi o'zgartira olmaydi, manager, tarix egasiga, boshqa kompaniya, huquqqa qarab raqam farqi, huquqsiz vidjet boshqalarni buzmaydi, RPC argumentlari, arxiv, kutilmagan xato `INTERNAL`, forma tugmasi** |
| **`test_drill.py`** | **14** | **sozlama (kalitlar, harakatlar, model, ustunlar, map, `DRILL_UNMAPPED`), nom almashtirish, guruhni topish, soxta ref** |
| **`test_drill_engine.py`** | **13** | **haqiqiy ORM: har kun/mijoz ochgan yozuvlar soni = guruh qiymati; kpi; act_window; `sale.report`→`sale.order`; huquq; kesish (80); soxta ref; domain yuborib bo'lmasligi; Others; bo'sh kun; `DRILL_UNMAPPED`** |
| `tests/js/lib.test.mjs` | **28** | **format, sana yorlig'i, escape, grid, frame modeli, kpi/delta, jadval jami, drill-ref, tema, Chart.js/ECharts sozlamalari, sparkline, "Others" xira, batcher** |
| `scripts/f3_ui_browser.py` | 13 tekshiruv | brauzer: TZ'dagi 12 qadam (3.3-bo'lim) |

**Sinalmagan** (8-bo'limga ham qarang):
- OWL komponentlarining o'zi uchun birlik testi yo'q: ular faqat brauzer skripti orqali tekshiriladi (`f3_ui_browser.py`), u **CI'da emas**, Chrome yo'li (`/Applications/Google Chrome.app/...`, `f3_ui_browser.py:CHROME`) va `localhost:8075` qattiq yozilgan.
- `lx_save` ga noto'g'ri tuzilgan JSON (L8) uchun test yo'q (shuning uchun xato ushlanmagan).
- `user_id`/`company_id`/`version` ni ORM orqali o'zgartirish, versiya yozuvini soxtalashtirish uchun testlar yo'q (bu holatlar hozir *ruxsat etilgan*).
- `open_as` `dialog`/`odoo_list` frontendda.
- uz/ru tilida brauzer; ko'p kompaniya brauzerda; `lx_list` 500+ dashboard.

---

## 5. Maxsus tekshiruvlar: aniq javoblar

### 5.1. Xavfsizlik va chidamlilik

| Savol | Javob | Dalil |
|---|---|---|
| `lx_drill` klientdan domain oladimi? | **Yo'q.** Klient faqat `group_ref` (qator kaliti) beradi; server vidjetni qayta ishga tushirib, haqiqiy guruhlar orasidan topadi va domain'ni o'zi quradi. Soxta kalit `DRILL_BAD_REF` | `board_rpc.py:103`; `drill.py:193-205`; `engine.py:149-157`; testlar |
| Drill foydalanuvchi huquqi bilan o'qiydimi? | Ha: `Runner.fetch` `self.env` (egasi emas, so'ragan foydalanuvchi) bilan; vidjet va drill sozlamasi har chaqiruvda **o'sha foydalanuvchi huquqi bilan qayta tekshiriladi** | `engine.py:131-173` (`self.env` = so'ragan foydalanuvchi); test `test_the_reader_sees_only_the_records_he_may_read` |
| `sudo()` bormi? | **Yo'q** | grep: faqat izohlar (`runner.py:3`, `board_rpc.py:4`) |
| Xom SQL? | Faqat 3 ta `cr.execute` (timeout o'qish/o'rnatish/tiklash), parametrlangan | `runner.py:74,78,80` |
| `eval`/`exec`? | Yo'q | grep |
| XSS: foydalanuvchi matnlari qayerda HTML bo'ladi? | Hech qayerda: shablonlarda faqat `t-esc`; `t-raw`/`t-out`/`innerHTML` **yo'q** (grep: 0). ECharts tooltip HTML'ini o'zim `escapeHtml` bilan yig'aman (test: `<script>` chiqmaydi). `t-att-style` faqat butun sonlardan yig'ilgan satr | `lib/chart_options.js:105,108`; `lib/grid.js` `gridStyle`; test |
| Dashboard'ni ko'rish huquqi qanday tekshiriladi? | `check_access("read")` + yozuv qoidalari; ko'rinmasa "topilmadi" (mavjudligi sirli) | `board_rpc.py:44-48` |
| Ulashilgan dashboard kimning ma'lumotini ko'rsatadi? | **Ko'ruvchiniki**, egasiniki emas (brauzer: admin 84 348 935 / sotuvchi 38 022 819; SQL bilan teng) | brauzer test 9 |
| Egasi bo'lmagan foydalanuvchi o'zgartira oladimi? | Yo'q (`AccessError`), `lx_save` → `NO_ACCESS` | `rules.xml:26-31`; test |
| Saqlashda spec kim huquqi bilan tekshiriladi? | **Saqlovchining**. Natija: sotuvni o'qiy olmaydigan manager sotuv spec'ini saqlay olmaydi (`NO_ACCESS`) | `engine.py:46-56`; test `test_a_manager_sees_and_changes_everything` |
| Katta spec? | 256 KB / 30 vidjet: validator; oldindan 512 KB dan katta kirish rad | `engine.py:48`; `validator.py:63-66` |
| Kutilmagan xato brauzerga ichki matn sizdiradimi? | `lx_run` yo'lida **yo'q** (`INTERNAL`, faqat umumiy matn). Lekin `lx_save`'da `TypeError` Odoo'ning umumiy "Internal Server Error" xabariga aylanadi (tafsilot faqat jurnalda) | L2, L8 |
| Brauzerda xato ichki URL ko'rsatadimi? | Ha: tarmoq uzilganda `"/web/dataset/call_kw/levelix.board/lx_run" couldn't be established` kartada ko'rinadi (sir emas, lekin chiroyli emas) | G11 |
| Ikkinchi kompaniya | Yozuv qoidasi ishlaydi (test). **Bundan tashqari** egasi `company_id` ni a'zo bo'lmagan kompaniyaga ko'chira oladi | `rules.xml:4-8`; L6c |
| `fill_gaps` bo'sh kunini bosish | Bo'sh natija (xato emas); soxta kun esa `DRILL_BAD_REF` | `engine.py:152-157`; test |
| Drill natijasi cheklangan | 80 qator + `total` + `truncated` | `drill.py:26`; test |
| Cross-site / CSRF | Odoo JSON-RPC'ning standart himoyasi; modulda o'zimizning HTTP route yo'q (`controllers/` yo'q) | grep |

### 5.2. Jonli sinovlarning xulosasi
3.3-bo'limda. Yangi muhim narsalar: `TypeError` hali `lx_save`'da (L1, L8), qiymat tekshiruvi yo'q (L3), egasi `user_id/company_id/version`ni o'zgartira oladi (L6, M1), versiya yozuvi soxtalashtiriladi (M2).

### 5.3. `grep` natijasi (ishlab chiqarish kodida)
`sudo|eval(|exec(|.execute(|utcnow|datetime.now|subprocess|except Exception|TODO|FIXME|HACK` (`lib/` + `models/`):
`runner.py:3` (izoh), `runner.py:74,78,80` (3 ta `cr.execute`), `engine.py:81` (`utcnow`), `engine.py:100` (`except Exception`, ataylab), `board_rpc.py:4` (izoh). Boshqa hech narsa. `TODO/FIXME/HACK` yo'q.
Frontend (`static/src`): `innerHTML|t-raw|t-out|markup(|eval(|new Function|document.write` → **0 ta**; `localStorage` 2 ta (`board_theme.js:11,18`, faqat tema nomi).

### 5.4. Xato kodlari (F2/F3 da qo'shilganlar)

| Kod | Qayerda | Test |
|---|---|---|
| `NOT_FOUND`, `BAD_ARGUMENT`, `NO_ACCESS` (yozish) | `board_rpc.py:40-51` | ✅ |
| `UNKNOWN_WIDGET` | `engine.py:65-68`, `:136` | ✅ |
| `UNSUPPORTED` (`filter_values`; drill `filter/open_record`) | `board_rpc.py:32`; `drill.py:80` | ✅ |
| `INTERNAL` | `engine.py:100-103` | ✅ |
| `DRILL_NOT_CONFIGURED`, `DRILL_OTHERS`, `DRILL_BAD_REF`, `DRILL_UNMAPPED`, `DRILL_BAD_COLUMN`, `BAD_ACTION` | `drill.py`, `engine.py` | ✅ |
| `BAD_SPEC` (JSON matn) | `board.py:12-16` | ✅ |
| **Domain qiymat tekshiruvi** | — | ❌ yo'q (L3) |

---

## 6. Tugash mezonlari

### 6.1. Faza bo'yicha (reja: `AI_DASHBOARD_PHASES.md`)

| Faza | Holat | Dalil |
|---|---|---|
| F1 | **TAYYOR** (kamchiliklar bilan, 7-bo'lim) | 105 test (F1 oxirida); `scripts/f1_compare.py` |
| F2 | **TAYYOR** | 54 yangi test; UI 1–2 brauzerda, 3–4 RPC orqali |
| F3 | **TAYYOR** | 28 JS test, brauzer 13/13, gallery 11/11 |
| Foydalanuvchi qabuli | F1: kutilmoqda; F2: so'ralmagan, F3 boshlashga ruxsat berildi; F3: kutilmoqda | `AI_DASHBOARD_PHASES.md` holat jadvali |

### 6.2. TZ 1-bosqich (T13, 1-qator): "spec, validator, ijrochi, frame, 4 vidjet (kpi, area, bar, table), drill-down, saqlash. Qo'lda yozilgan spec"

| Band | Holat | Dalil / izoh |
|---|---|---|
| Spec, validator, ijrochi, frame | **TAYYOR** | F1 |
| 4 vidjet (kpi, area, bar, table) | **TAYYOR** | brauzer testi 1–11; `line` ham bor |
| Drill-down: kunni bosish → o'sha kun buyurtmalari | **TAYYOR** | brauzer testi 3: 2026-10-20 → 8 = 8; test 4: tovar 34 = 34; test 5: "Open in Odoo" 34 yozuv |
| Saqlash (`levelix.board`, versiyalar) | **TAYYOR** | `board.py`; testlar |
| Qo'lda yozilgan spec | **TAYYOR** | forma (`ace` JSON muharriri); brauzerda spec kiritish va noto'g'ri spec rad etilishi tekshirilgan (F2 UI testi) |
| "5.1 dagi misol ishlaydi" | **QISMAN** | TZ misoli aynan yozilganidek `compare` sababli rad etiladi; `compare`siz ishlaydi (F6) |
| "Jami `sale.report` bilan mos" | **TAYYOR** | brauzer test 2: 84 348 935.00 = SQL; yig'indi ikkala grafikda teng |
| "Huquq testi o'tadi" | **TAYYOR** | `test_board.py`, brauzer test 9 |
| Dizayn "Odoo'ga o'xshab qolmagan" (UI 12) | **Subyektiv**: skrinshotlarga qarab baholadim; foydalanuvchi ko'rib tasdiqlashi kerak | — |

**Umumiy baho.** TZ'ning 1-bosqichi texnik jihatdan bajarilgan va avtomatik hamda brauzer testlaridan o'tgan. Qabul qilish foydalanuvchi qo'lida. Eng katta texnik qarz: 7.3-jadvaldagi #1–#3.

---

## 7. Bo'shliqlar, xavflar, F4 ga tayyorlik

### 7.1. TZ'da bor, kodda yo'q

| Nima | TZ | Faza |
|---|---|---|
| `lx_restore`, `lx_share`, `lx_apply_patch` | T9 | F7 |
| `compare`, `calc`, global filtrlar, cross-filter, `filter`/`open_record` harakatlari | T5.1, T5.3, T7.1 | F6 |
| Vidjet turlari: `pie`, `heatmap`, `funnel`, `treemap`, `gauge`, `waterfall`, `scatter`, `combo` (serverda tekshiruv bor, frontendda yo'q) | T5.2, T8.2 | F6 |
| Grid'da surish va o'lcham o'zgartirish | T8.6 | F7 |
| `levelix.board.alert/schedule`, TV rejimi | T3.1, T8.4 | F8 |
| `levelix_ai_core`, `levelix_ai_board`, chat, `levelix.ai.hint` | T3.2–T3.3, T4 | F4–F5 |
| Kesh (TTL 60 s) | T6.2 | F9 yoki keyin |
| Tarjima (`i18n/*.po`), uz/ru brauzer sinovi | T11 | F9 |
| Eski `levelix_ai` dashboard elementlarini ko'chirish | T1.1 | F9 |

### 7.2. Kodda bor, TZ'da yo'q (yoki keyin yozilgan)

`lib/drill.py` ichidagi `UNSHOWN_TYPES`, `MAX_COLUMNS=12`, `empty_result`; `__others__` belgisi; `meta.totals`; `INTERNAL` kodi; `levelix_board.data/theme` xizmatlari; `error_dialogs.js`; `batcher.js`; `scripts/f3_ui_browser.py`, `seed_boards.py`, `run_js_tests.sh`; `tools/echarts`. Hammasi `AI_DASHBOARD_TEXNIK_TZ.md` 6.10 va 8.7 ga yozilgan.

### 7.3. Texnik qarz va xavfli joylar (muhimlik tartibida)

| # | Daraja | Muammo | Dalil | Tavsiya |
|---|---|---|---|---|
| 1 | ~~Yuqori~~ **TUZATILGAN (9-bo'lim)** | `_validate_spec`/`lx_save`/forma noto'g'ri tuzilgan qiymatda (`having`/`order.by` da ro'yxat) `TypeError` bilan yiqiladi; foydalanuvchi "Internal Server Error" oladi. AI (F5) shunday spec yuborishi mumkin | `validator.py:234,266`; jonli L1, L1b, L8 | `_check_order`/`_check_having` da `isinstance(x, str)`; `_normalise_spec` da `TypeError`→`BAD_SPEC`; test |
| 2 | ~~Yuqori~~ **TUZATILGAN (9-bo'lim)** | Domain **qiymati** tekshirilmaydi (`state=done`, `in` ga satr): jimgina 0 qator | jonli L3, L3b | selection qiymatini `FieldInfo.selection` bo'yicha (`UNKNOWN_VALUE`), `in/not in` ro'yxat talab. F5 aniqligi uchun eng foydali yagona qo'shimcha |
| 3 | ~~O'rta-yuqori~~ **TUZATILGAN (9-bo'lim)** | Egasi `user_id`, `company_id`, `version` ni ORM orqali o'zgartira oladi; `company_id` ni a'zo bo'lmagan kompaniyaga ham | jonli L6, L6c, M1; `board.py:19-37` | `write` da bu maydonlarni faqat manager o'zgartirsin; `version` ni `create/write` dan olib tashlash |
| 4 | ~~O'rta~~ **TUZATILGAN (9-bo'lim)** | Egasi versiya yozuvini o'zi yarata oladi (har qanday `spec`, `origin="ai"`). F7 da "qaytarish" shundan spec oladi | jonli M2; `ir.model.access.csv:4` | `levelix.board.version` ga `create` huquqini olib tashlab, yozuvni faqat `_record_version` (kontrolli yo'l) yaratsin; qaytarishda spec qayta tekshirilsin |
| 5 | O'rta | Drill har bosishda vidjetni to'liq qayta ishga tushiradi (+ jami + 80 qatorli o'qish), kesh yo'q. Katta bazada tezlik o'lchanmagan | `engine.py:149` | **TEKSHIRILMAGAN**: M-Dom nusxasida o'lchash; kerak bo'lsa guruhlarni qisqa muddat keshlash |
| 6 | O'rta | `open_as` (`dialog`, `odoo_list`) tekshiriladi, lekin frontend faqat yon panelni biladi | `drill.py:25`; `drill_panel.js` | hozircha `side_table` ni yagona qiymat qilish yoki F6 da qo'llash |
| 7 | O'rta | TZ 5.1 misoli `compare` sababli rad etiladi; KPI ▲▼ hech qachon chizilmaydi (ma'lumot yo'q) | `validator.py:102-103`; `kpi_widget.js` | F6 |
| 8 | O'rta | Nuqtali domain yo'lida faqat birinchi qism tekshiriladi (`QUERY_FAILED` bo'ladi) | `validator.py:119`; jonli L3c | yo'lni oxirigacha tekshirish |
| 9 | Past | KPI qiymati = oxirgi korzina; hafta/oy bo'yicha bo'lsa **tugallanmagan davr** bo'lishi mumkin | `frame_model.js:90-101`; G3 | KPI uchun "oxirgi to'liq davr" yoki aniq belgi (F6, `compare` bilan birga) |
| 10 | Past | Bir xil kategoriya turli grafikda turli rangda bo'lishi mumkin (seriya tartibi har xil) | G4/G5 | rangni kategoriya nomiga bog'lash |
| 11 | Past | Tarmoq uzilganda kartada ichki URL ko'rinadi | G11 | `rpcMessage` da transport xatosini umumiy matn bilan almashtirish |
| 12 | Past | `lx_list` sahifalamaydi (500), 9 ta so'rov/31 ta karta | `board_rpc.py:14,73`; L7 | kerak bo'lganda |
| 13 | Past | `board_data.batchers` tozalanmaydi | `board_data.js:30` | ahamiyatsiz |
| 14 | Past | Kod poygasi nazariy xavfi: `kpi_widget.js:62-80` sparkline'lar, `chart_body.js:48-80` (G9 da takror chiqmadi) | G9 | **TEKSHIRILMAGAN** haqiqiy poyga holatida; kerak bo'lsa `generation` ni KPI ga ham qo'shish |
| 15 | Past | F1 dan qolganlar: `datetime.utcnow()` (`engine.py:81`), `today_in` aware qiymat, ustun `id` takrori, `TIMEOUT` xabari "0 seconds", `explain` ikki tur, `spec.py`/`validator.py` >300 qator, `any` operatori yo'q, `TIMEOUT/QUERY_FAILED` testi yo'q | PHASE1_ANALYSIS 7.3 #4–#14 | o'zgarmagan |
| 16 | Past | `view` va `interact` ichki kalitlari bir qismi tekshirilmaydi: `view` ixtiyoriy lug'at (xato yozilgan `"smoth"` jimgina e'tiborsiz) | `spec.py:234` | F6 da `view` sxemasi |
| 17 | Past | Brauzer testi CI'da emas, Chrome yo'li va port qattiq yozilgan; seed ma'lumotga va "bugun" ga bog'liq | `f3_ui_browser.py` | F9 da CI |

### 7.4. F4 (`levelix_ai_core`) ga tayyorlik

**To'g'ridan-to'g'ri ishlatiladi:**
- `engine._normalise_spec(spec)` yoki `_validate_spec` → `build_dashboard` vositasi tekshiruvi; xato shakli `{path, code, message}` (`BoardError.to_dict`, `errors.py:20-21`) TZ 4.4 tuzatish sikliga mos.
- `engine._run_spec(spec, [id], explain=True)` → `preview_widget` (dry-run); vidjet bo'yicha izolyatsiya va `INTERNAL` himoyasi endi bor.
- `EnvCatalog` → `describe_model`/`find_models` vositalari uchun asos.
- `levelix.board` (`spec`, `state=draft`, `lx_origin="ai"` konteksti) → AI qoralamasi uchun tayyor; `_inherit` bilan `source_conversation_id` qo'shish mumkin (T3.3). `levelix_board` AI'ni bilmaydi: bog'liqlik yo'nalishi buzilmagan.

**Oldin tuzatilishi kerak:** 7.3 dagi **#1, #2** (AI beqaror chiqish yuboradi), **#3, #4** ("origin=ai" soxtalashtirilishi mumkin; AI audit yo'li ishonchli bo'lishi uchun).

**Yangi kerak bo'ladi:** maxfiylik rejimi qatlami `to_ai(result, mode)` (T4.5: AI'ga `Frame.rows` bermaslik), `update_dashboard`/patch, `levelix.ai.hint`, provayder qatlami. Hech biri hozir yo'q.

---

## 8. Men o'qimagan, yuzaki ko'rgan yoki tekshirmagan narsalar

- **O'qilgan:** F2/F3 ning hamma yangi fayllarini yozish vaqtida to'liq ko'rganman; bu hujjat uchun qator raqamlarini `grep -n` bilan qayta oldim va asosiy funksiyalarni qayta o'qidim. **Hamma faylni bu hujjat uchun boshidan oxirigacha qayta o'qimadim**: `board.scss` (213 qator), `explain_panel.*`, `drill_panel.xml`, `board_page.xml` ni faqat tanlab ko'rdim.
- **F1 fayllari** (`spec.py`, `filters.py`, `validator.py` asosiy qismi, `explain.py`, `catalog.py`, `domain.py`, `errors.py`, `i18n.py`): PHASE1_ANALYSIS dagi tahlilga tayandim; shu hujjat uchun qayta o'qilmadi (faqat o'zgargan qatorlar).
- **Test fayllari:** nomlari/soni `grep -c` bilan, mazmuni yozish vaqtidagi xotiradan; qayta satrma-satr o'qilmadi. To'plam to'liq ishga tushirildi (0 xato).
- **`scripts/`**: `f1_compare.py`, `seed_*.py`, `spike_*.py`, `smoke_engine.py`, `build_pdf.py` faqat havola sifatida.
- **ECharts bundle** (663 KB minified): ichi o'qilmadi; manbasi `tools/echarts/entry.js` va npm paketi (`echarts@5.6.0`), litsenziya/NOTICE nusxalangan. Bundlening xavfsizligi (ta'minot zanjiri) alohida tekshirilmagan: `npm install` natijasi (`package-lock.json`) repoda.
- **TEKSHIRILMAGAN:**
  - **Til:** `user.lang` = `uz_UZ` / `ru_RU` bilan brauzerda raqam va sana formati (faqat node birlik testi: `en` va yorliq qismlari). Odoo'ning `uz` tili o'rnatilganmi ham tekshirilmagan.
  - **Katta ma'lumot:** 182 buyurtmadan ortiq tezlik (M-Dom nusxasi lokalda yo'q); drill va `lx_run` ning real vaqti.
  - **Ko'p kompaniya brauzerda:** kompaniya almashtirgichi (`allowed_company_ids`) bilan.
  - **Boshqa brauzerlar, haqiqiy telefon, sensorli ekran:** faqat Chrome headless va viewport 390 px.
  - **Ekran o'qigich:** yashirin jadval va `aria` yozuvlari bor, lekin haqiqiy o'qigich bilan eshitilmagan. Faqat `Enter` bilan jadval qatorini ochish sinalgan (G7); grafik nuqtalarini klaviatura bilan bosish **yo'q** (grafik kanvas).
  - **Bir vaqtda ikki saqlash** (`UNIQUE(board_id, version)` to'qnashuvi): simulyatsiya qilinmagan.
  - **`lx_drill` da ko'ruvchining ochiladigan modelga huquqi yo'q holati** (saqlovchida bor, ko'ruvchida yo'q): kod `NO_ACCESS`/`UNKNOWN_FIELD` berishi kerak, lekin sinalmagan.
  - **Maydon darajasidagi ruxsat** (`groups=` li maydon bo'yicha filtr bilan ma'lumotni taxmin qilish): PHASE1 dagi savol hali ochiq.
  - **ECharts tooltip** haqiqiy brauzerda ko'rinishi (skrinshotda ko'rindi, matn escape qilingani birlik testida); Chart.js tooltip matni.
  - **Eski brauzer/`prefers-reduced-motion`**: kod bor (`chart_body.js:58`), sinalmagan.
  - Git tarixi: repoda commit bor, lekin "commitlar ketma-ketligi" so'ralmadi va o'qilmadi.

---

## 9. Qo'shimcha (2026-11-05, keyinroq): 7.3 dagi #1–#4 tuzatildi

Foydalanuvchi tasdig'i bilan tuzatildi. Yuqoridagi 1–8 bo'limlar tuzatishdan **oldingi** holatni tasvirlaydi (ular tarixiy dalil sifatida o'zgartirilmadi); qator raqamlari `lib/validator.py`, `models/engine.py`, `models/board.py` da siljigan. Joriy holat:

| # | Tuzatish | Qayerda | Dalil |
|---|---|---|---|
| 1 | `order.by` va `having` elementlari turi tekshiriladi (`BAD_ORDER`/`BAD_HAVING`); kutilmagan shakl `BAD_SPEC` ga aylanadi, `_validate_spec`, `_normalise_spec` (`lx_save`, forma) endi `TypeError` bermaydi | `lib/validator.py` (`_check_order`, `_check_having`), `models/engine.py` (`_SHAPE_ERRORS`, `_odd_shape`) | jonli: L1, L1b, L8 → `BAD_HAVING`/`BAD_ORDER`/`SpecInvalid`; test `test_a_wrongly_typed_spec_is_a_clear_error_not_a_server_error`, `test_order_and_having_with_wrong_types_...` |
| 2 | Domain qiymatlari: `BAD_VALUE`, `UNKNOWN_VALUE` (`state = done` → xabarda "sale (Sales Order)" kabi variantlar) | `lib/validator.py` (`_check_value`) | jonli: L3, L3b, L2; 5 ta yangi validator testi |
| 3 | `version` qo'lda yozilmaydi; `user_id`/`company_id` ni faqat manager | `models/board.py` (`_check_protected_fields`) | jonli: L6, L6c, M1; `TestBoardProtection` |
| 4 | `levelix.board.version` ga `create` huquqi olib tashlandi; yozuvni server yaratadi (`sudo`, `author_id` = haqiqiy foydalanuvchi) | `security/ir.model.access.csv:4-5`, `models/board.py` (`_record_version`) | jonli: M2 → `AccessError`; tarixda muallif `sotuvchi`; test `test_a_version_row_cannot_be_forged_but_saving_still_writes_one` |

**Natijalar.** Python **170 test, 0 xato** (oldin 159); JS 28/28; brauzer `f3_ui_browser.py` 13/13; forma orqali saqlash (`f2_ui_browser.py`) qayta o'tdi.

**Yangi eslatmalar.**
- Bu modulning **yagona `sudo()`** i paydo bo'ldi (`board.py`, versiya qatori). 5.1-bo'limdagi "`sudo` yo'q" javobi endi: *biznes ma'lumotga yo'q; faqat tarix qatorini yozishda bor*. `AI_DASHBOARD_TEXNIK_TZ.md` 6.11 ga yozilgan.
- Domain qiymat tekshiruvi **faqat nuqtasiz** maydonlar uchun; nuqtali yo'l (`partner_id.country_id`) qiymati va `like/ilike`, `child_of/parent_of` tekshirilmaydi. 7.3 #8 (nuqtali yo'lni oxirigacha tekshirish) ochiq.
- Selection qiymati dinamik (`selection` metod) bo'lsa va `fields_get` ro'yxat bermasa, tekshiruv o'tkazib yuboriladi (`field.selection` bo'sh). **TEKSHIRILMAGAN** haqiqiy dinamik selection maydon bilan.
- `UNKNOWN_VALUE` selection `state`ni Odoo versiyasiga bog'laydi: yangi Odoo yangi holat qo'shsa, `fields_get` uni o'zi beradi, qo'lda ro'yxat yo'q.
- Ochiq qolganlar: #5–#17 (7.3).
