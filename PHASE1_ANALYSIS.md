# PHASE1_ANALYSIS — `levelix_board` 1-bosqich kodining tahlili

> Sana: 2026-11-05. Tahlil qilingan: `/Users/latibov/Levelix/AI_Dashboard/addons/levelix_board` (v19.0.1.0.0).
> Manba hujjatlar: `AI_DASHBOARD_TZ.md` (qisqa TZ), `AI_DASHBOARD_TEXNIK_TZ.md` (texnik hujjat, quyida "T" + bo'lim raqami), `AI_DASHBOARD_PHASES.md` (ish rejasi).
> Dalil formati: `fayl:qator`. Qator raqamlari 2026-11-05 dagi holatga tegishli.

## 0. Ikki muhim ogohlantirish (avval shuni o'qing)

**1. Bu tahlilni kodni yozgan sun'iy intellektning o'zi qildi.** Ya'ni bu mustaqil tashqi taftish emas. Buni kamaytirish uchun men kodni qayta o'qib chiqdim (har `lib/` va `models/` faylini boshidan oxirigacha), kodda hali kutilmagan holatlarni jonli sinab ko'rdim (3-bo'lim "Jonli sinovlar") va o'zim topgan kamchiliklarni yashirmadim: 5-bo'limda 3 ta jiddiy topilma bor. Lekin o'z kodimni baholayotganimni bilib turing. Muhim joylarni boshqa odam (yoki alohida sub-agent) ham ko'rib chiqsa yaxshi bo'ladi.

**2. "1-bosqich" to'liq tugamagan.** TZ'ning 1-bosqichi uch faza: F1 (spec + ijrochi), F2 (saqlash + huquq + drill serveri), F3 (frontend). Hozir **faqat F1 qurilgan**. So'rovingizdagi quyidagilar kodda umuman **YO'Q**: `levelix.board` va versiya modellari, `lx_load`/`lx_run`/`lx_drill`/`lx_save` kabi RPC metodlar, `security/`, `views/`, `data/`, `static/src/` (frontend: grid, vidjetlar, adapterlar, tema, sahifa), drill-down serveri. Bularni "KODDA YO'Q" deb belgilayman va ixtiro qilmayman. Ayrim so'ralgan narsalar (git log) ham mavjud emas: `AI_Dashboard` papkasi git repozitoriy emas (`git rev-parse` xato qaytardi). Commitlar tarixi yo'q.

---

## 1. Umumiy xulosa

**Nima qilingan.** `levelix_board` modulining "miyasi": JSON tavsif (spec) formatini o'qiydi, haqiqiy Odoo modellariga qarshi tekshiradi, bitta vidjetni Odoo `formatted_read_group` so'roviga aylantiradi, foydalanuvchi huquqi bilan bajaradi va natijani brauzer chizishga tayyor jadval (`Frame`) ko'rinishida qaytaradi. Shuningdek "Men nima qildim" matnini (AI'siz, koddan) tayyorlaydi.

**Analogiya.** Spec — restoranga beriladigan buyurtma varag'i. `Validator` — ofitsiant (mavjud bo'lmagan taomni yozmaydi, "sho'rvani vilka bilan" demaydi). `Planner` — oshpaz uchun aniq retsept. `Runner` — oshxona (faqat siz ruxsat olgan mahsulotlar bilan pishiradi). `FrameBuilder` — likopchaga solish. `ExplainBuilder` — likopcha tagidagi yozuv "bu taom shu mahsulotlardan tayyorlangan". AI keyinroq ofitsiant rolini emas, buyurtma varag'ini yozuvchi mijoz rolini oladi: AI faqat varaq yozadi, qolganini kod qiladi.

**Raqamlar.**

| Ko'rsatkich | Qiymat |
|---|---|
| Ishlab chiqarish kodi (`lib/` + `models/` + manifest) | 1 771 qator (17 fayl) |
| Test kodi | 1 099 qator, 105 ta test |
| Test natijasi (2026-11-05 07:48) | **0 xato, 0 yiqilish, 105 ta** (`scripts/run_tests.sh`) |
| Mustaqil SQL bilan solishtirish (`scripts/f1_compare.py`) | barcha qiymatlar teng (jami, 158 buyurtma, har kun, top-5, "Others", sotuvchilar) |
| `sudo()`, `eval()`, `exec()` biznes ma'lumotga | **yo'q** (grep, 5.3-bo'lim) |

**Nima qolgan** (TZ 1-bosqich mezoniga nisbatan): saqlash va huquq modeli (F2), drill-down serveri (F2), butun frontend (F3), TZ'dagi `compare`, `calc`, global filtrlar (F6), vidjet qayta tuzilishi uchun yo'l ochilgan.

**Eng muhim 3 topilma** (5-bo'lim, "Xavflar"da to'liq):
1. Bitta vidjetdagi **kutilmagan** xato (noto'g'ri turdagi JSON qiymat, masalan `having` ichida ro'yxat) `TypeError` bo'lib **butun `_run_spec`ni qulatadi**. Faqat `BoardError` ushlanadi (`models/engine.py:73`). AI keyin yuboradigan spec'lar uchun bu muhim.
2. "Men nima qildim" matni uchun yozuv nomlarini topishda `AccessError` ushlanmaydi (`lib/explain.py:115-116` → `models/engine.py:92-94`): foydalanuvchi o'qiy olmaydigan modelga bog'langan filtr bo'lsa butun ishga tushirish qulaydi (jonli tasdiqlandi).
3. Validator domain **qiymatlarini** tekshirmaydi. Masalan `["state","in","abc"]` yoki mavjud bo'lmagan holat qiymati xatosiz **0 qator** qaytaradi. TZ'dagi `done` holati Odoo 19'da yo'q, AI shuni yozsa, jimgina 0 chiqadi.

---

## 2. Modul xaritasi

### 2.1. Daraxt (hamma fayl, qator soni)

```
addons/levelix_board/                         (jami 1 771 qator ishlab chiqarish kodi + 1 099 qator test)
├── __manifest__.py              19   depends=["web"], data=[], assets YO'Q, LGPL-3, v19.0.1.0.0
├── __init__.py                   1   models ni import qiladi
├── lib/                              ← toza Python (Odoo env'siz, runner bundan mustasno)
│   ├── __init__.py               6   paket tavsifi
│   ├── errors.py                62   BoardError, SpecInvalid, BoardWarning, ValidationResult
│   ├── i18n.py                  10   t(): matnlar uchun yagona "tarjima eshigi" (hozir matnni o'zini qaytaradi)
│   ├── catalog.py               52   FieldInfo, ModelInfo, Catalog (model/maydon ma'lumotnomasi, Odoo'siz)
│   ├── spec.py                 313   spec dataclass'lari, o'qish/yozish, migrate, vidjet shakllari jadvali
│   ├── domain.py                63   domain'ni daraxtga o'qish (qaysi shartlar har doim bajarilishi shart)
│   ├── filters.py              206   nisbiy sanalar, mahalliy kun semantikasi, davr chegaralari, hafta/oy boshlari
│   ├── validator.py            314   semantik tekshiruv: xato kodlari + ogohlantirishlar
│   ├── planner.py              177   vidjet → Plan (Odoo'ga nima so'raladi)
│   ├── runner.py                83   YAGONA Odoo'ga bog'langan joy: Plan → formatted_read_group
│   ├── frame.py                184   xom guruhlar → Frame (ustunlar, qatorlar, bo'sh kunlarni to'ldirish, "Others")
│   └── explain.py              140   "Men nima qildim" qatorlari (koddan, AI'siz)
├── models/                           ← yupqa Odoo adapteri
│   ├── __init__.py               1
│   ├── env_catalog.py           46   Catalog'ning Odoo versiyasi (foydalanuvchi ko'ra oladigan maydonlar)
│   └── engine.py                94   levelix.board.engine (AbstractModel): _validate_spec, _run_spec
└── tests/                       1 099 qator, 105 test (7 fayl + fixtures + __init__)
```

**Yo'q papkalar** (mavjud emas): `security/`, `views/`, `data/`, `static/`, `controllers/`, `i18n/`. Manifestda `data: []` va `assets` kaliti yo'q (`__manifest__.py:16`).

### 2.2. Bog'liqlik yo'nalishi (kim kimni import qiladi)

```
engine.py ──► validator ──► spec, domain, filters, catalog, errors, i18n
   │            planner ──► spec, filters, catalog
   │            runner  ──► planner, errors, i18n, odoo.exceptions, psycopg2     ← Odoo'ga bog'langan yagona lib fayl
   │            frame   ──► planner, filters, errors, i18n
   │            explain ──► planner, spec, filters, domain, catalog, i18n
   └──► env_catalog ──► catalog
```

Eslatma: `errors.py` va `runner.py` `odoo.exceptions` ni import qiladi (`BoardError` — `UserError` avlodi, `lib/errors.py:3,6`). Shuning uchun `lib/` "Odoo'ni umuman bilmaydi" emas, faqat "ma'lumotlar bazasiga tegmaydi" (runner'dan tashqari). Testlar Odoo ichida ishlaydi (`BaseCase`), alohida `pytest` bilan emas.

### 2.3. `levelix_ai` (eski modul) bilan solishtirish

Eski modul: `/Users/latibov/Levelix/mdom/levelix_ai`. Solishtirish uchun faqat `models/ai_tools.py` `aggregate` vositasini o'qidim. Qolgan qismini (providers, panel, blocks) bu tahlilda o'qimadim.

| Mavzu | Eski `levelix_ai` (`ai_tools.py`) | Yangi `levelix_board` |
|---|---|---|
| Guruhlash/jamlash soni | `groupby ≤ 2`, `aggregates ≤ 4` (`:296-297`) | o'q ≤ 2, o'lchov ≤ 4 (`validator.py:19-20`) |
| Guruhlar limiti | `MAX_GROUPS = 100` (`ai_tools.py:17`, `:298`) | 200 (`planner.py:14`), kesilsa ogohlantirish |
| Jamlama turi tekshiruvi | **yo'q** (`price_unit` ni ham `sum` qilish mumkin) | `NOT_AGGREGATABLE` (`validator.py:216-221`) |
| Sana/vaqt zonasi | yo'q | foydalanuvchi vaqt zonasi (`filters.py`) |
| Bo'sh kunlarni to'ldirish | yo'q | bor (`frame.py:114-161`) |
| Valyuta | doim `env.company.currency_id` (`ai_tools.py:327-328`) | hisobot modelida kompaniya valyutasi, oddiy modelda tekshiruv (`engine.py:76-90`) |
| `sudo()` | faqat sozlama va jurnal uchun (`ai_engine.py:75,375,406`) | biznes ma'lumotga yo'q |
| `statement_timeout` | yo'q (grep topmadi) | 8 s (`runner.py:21,70`) |
| Tushuntirish | `_describe_domain` (`ai_tools.py:165`), AI argumentlaridan | `ExplainBuilder`, haqiqiy rejadan |

---

## 3. To'liq oqim: bitta vidjetning yo'li

TZ'dagi 5-bo'lim misolini (kunlik sotuv `area`) oldim. Zanjirning qaysi bo'g'ini kodda borligi:

```
[lx_load]        KODDA YO'Q   (F2)
[lx_run]         KODDA YO'Q   (F2). Uning o'rnida: levelix.board.engine._run_spec  (private, shell/testlar uchun)
  └ Spec.from_raw → Validator → Filters → Planner → Runner → FrameBuilder → ExplainBuilder      ← BOR
[JSON → brauzer] KODDA YO'Q   (RPC qatlami yo'q)
[frontend reyestr → adapter → grafik]   KODDA YO'Q   (F3)
[nuqta bosish → lx_drill → yon jadval]  KODDA YO'Q   (F2 + F3)
```

### 3.1. Haqiqiy misol (seed ma'lumot, 2026-11-05, Toshkent vaqti)

Kiruvchi vidjet (TZ 5.1 dan, `compare` olib tashlangan, chunki `compare` hali yo'q, 5.4-bo'limga qarang):

```json
{"id":"w1","type":"area","data":{
  "source":"sale.report",
  "domain":[["state","=","sale"],["date",">=","today -29d"],["date","<=","today"]],
  "dimensions":[{"field":"date","granularity":"day"}],
  "measures":[{"id":"m1","field":"price_subtotal","agg":"sum","label":"Revenue"}],
  "order":{"by":"date","dir":"asc"},"fill_gaps":true}}
```

**Qadam 1. `engine._run_spec(raw)`** (`models/engine.py:38-51`). `Spec.from_raw(raw)` (`lib/spec.py:263-275`): `migrate` versiyani tekshiradi (`spec.py:301-313`), keyin har blokni dataclass'ga o'giradi, noma'lum kalitni rad etadi (`_only_keys`, `spec.py:51-54`). Natija: `Spec(widgets=(Widget(id="w1", type="area", data=Data(source="sale.report", ...)),))`. Struktura xato bo'lsa `BoardError` ko'tariladi (bu holatda `_run_spec` butunlay to'xtaydi, docstringda aytilgan: `engine.py:44`).

**Qadam 2. Catalog.** `EnvCatalog(self.env)` (`engine.py:45`). `catalog.model("sale.report")` foydalanuvchi ko'ra oladigan maydonlarni `fields_get` orqali yig'adi va `ModelInfo`ga soladi (`env_catalog.py:21-46`). Model o'qishga yopiq bo'lsa `accessible=False` (`:27-28`).

**Qadam 3. `Validator.validate_widget`** (`validator.py:78-106`). Ketma-ket: model bormi → o'qiy oladimi → domain (`_check_domain`) → o'qlar → o'lchovlar → tartib → limit/others → having → shakl (`area` uchun 1–2 o'q, 1–3 o'lchov, birinchi o'q sana) → ogohlantirishlar. Misolda xato yo'q. `price_subtotal` maydonida Odoo `aggregator="sum"` bor, shuning uchun `sum` ruxsat etilgan (`validator.py:32-47`).

**Qadam 4. Sana almashtirish (`filters.resolve_domain`, `filters.py:129-159`).** Vaqt zonasi `Asia/Tashkent` (UTC+5), "bugun" = 2026-11-05:

| Kirish | Chiqish |
|---|---|
| `["date",">=","today -29d"]` | `["date",">=","2026-10-06 19:00:00"]` (7-oktabr mahalliy yarim tun = 6-oktabr 19:00 UTC) |
| `["date","<=","today"]` | `["date","<","2026-11-05 19:00:00"]` (ya'ni bugunning oxirigacha, bugun ham kiradi) |

**Qadam 5. `Planner.plan`** (`planner.py:92-131`) shu `Plan`ni yasaydi:

```
model="sale.report"   groupby=["date:day"]   aggregates=["price_subtotal:sum"]
order="date:day asc"  query_limit=201 (cap 200 + 1)   fill=FillSpec(day, start=2026-10-07, end_excl=2026-11-06, asc)
```

**Qadam 6. `Runner.run`** (`runner.py:35-46`). `_guard()` (`:63-83`): joriy `statement_timeout` ni eslab qoladi → `cr.savepoint()` ochadi → `set_config('statement_timeout','8000',true)` (xuddi `SET LOCAL`) → `formatted_read_group(...)` → savepoint yopiladi → eski qiymatni tiklaydi. Odoo qaytargan xom guruh (F0 spike natijasi, `notes/F0_natijalar.md`):

```
{'date:day': ('2026-10-06 19:00:00', '07 Oct 2026'), 'price_subtotal:sum': 2232000.0,
 '__extra_domain': ['&', ('date','>=','2026-10-06 19:00:00'), ('date','<','2026-10-07 19:00:00')]}
```

**Qadam 7. `FrameBuilder.build`** (`frame.py:33-63`). Har guruhdan qator: sana kaliti mahalliy sanaga aylanadi (`local_day`, `:178-184`: `'2026-10-06 19:00:00'` → `'2026-10-07'`). `_fill` (`:114-161`) 29 kunlik oraliqda bo'sh kunlarni `0` bilan to'ldiradi, to'ldirilgan kunning kaliti ham haqiqiy kalit ko'rinishida yoziladi (`ref_key`, `:150`). Natija (haqiqiy, `smoke_engine.py` dan):

```json
{"columns":[{"id":"date","label":"Order Date","role":"dimension","type":"datetime","granularity":"day"},
            {"id":"m1","label":"Revenue","role":"measure","type":"monetary"}],
 "rows":[["2026-10-07",2232000.0],["2026-10-08",2979060.0],["2026-10-09",3724720.0], "...", ["2026-11-04",0],["2026-11-05",0]],
 "meta":{"count":30,"truncated":false,"currency":{"symbol":"UZS","position":"after"},
         "warnings":[],"group_refs":[["2026-10-06 19:00:00"],["2026-10-07 19:00:00"], "..."]}}
```

**Qadam 8. Explain** (faqat `explain=True`): `ExplainBuilder.build` (`explain.py:41-49`) beshta qator beradi: "Data source: Sales Analysis Report." / "Measured: Revenue (total), in UZS." / "Grouped by: Order Date (by day)." / "Status is Sales Order." / "Order Date: 2026-10-07 – 2026-11-05."

**Drill-down (nuqta bosish) uchun nima tayyor.** `meta.group_refs[i]` — qatorning xom kaliti (sana uchun UTC kalit, bog'lanish uchun id, tanlov uchun qiymat; `frame.py:95-104`). F0 da tasdiqlangan g'oya: server shu kalit bo'yicha guruhning `__extra_domain`ini qayta olib, `map` bilan `sale.order` maydonlariga o'tkazadi. **Hozir kodda `__extra_domain` hech qayerda ishlatilmaydi** (`grep` natijasi bo'sh). `lx_drill`, `map`, `DRILL_UNMAPPED`: KODDA YO'Q (F2).

### 3.2. Jonli sinovlar (bu hujjat uchun o'tkazildi, hech narsa saqlanmadi: har biri `rollback` bilan)

| # | Sinov | Natija |
|---|---|---|
| A | `widget_ids=["nope"]` (mavjud bo'lmagan id) | `{"widgets": {}}`: **jimgina tashlab ketiladi**, xato yo'q |
| A | `widget_ids=["w1","zzz"]` | faqat `w1` qaytadi |
| A | `widget_ids="w1"` (ro'yxat o'rniga satr) | ishlaydi, lekin **qism-satr** mantig'ida (`"w" in "w1"` ham `True`) |
| B | `having: [[["x"],">",1]]` (id ro'yxat) | `_validate_spec` **`TypeError: unhashable type: 'list'`** bilan qulaydi |
| B | `order: {"by": ["m1"]}` | xuddi shunday `TypeError` |
| B | `domain: [["state","=",{"a":1}]]` | validator `ok=True` beradi, ishga tushirishda `TypeError`, **butun `_run_spec` qulaydi** |
| C | `omborchi` (sotuvga ruxsatsiz) `res.users` ni o'zi o'qiy olmaydigan `log_ids` orqali nuqtali domain bilan so'raydi | `NO_ACCESS` (Odoo sizdirmaydi) |
| E | `Runner(timeout_ms=1)`, `pg_sleep(0.2)` | `TIMEOUT` xatosi; sozlama `0` ga qaytdi, kursor ishlashda davom etdi |
| F | `["state","in","abc"]` | xatosiz **0 qator** (qiymat tekshirilmaydi) |
| F | `["partner_id.nonexistent","=",1]` | `QUERY_FAILED` ("Invalid field res.partner.nonexistent..."): validator ushlamadi, Odoo xatosi ushladi |
| G | `ir.embedded.actions` (omborchi o'qiy oladi) `parent_action_id` ga filtr + `explain=True` | **`AccessError` butun `_run_spec`ni qulatdi** |
| H | TZ 5.1 misoli aynan yozilganidek | `REJECTED: UNSUPPORTED widgets[0].data.compare`. `compare` olib tashlansa ishlaydi: w1 54 qator, w2 10 tovar + "Others" |

---

## 4. Fayllar bo'yicha batafsil tahlil

Har fayl: vazifa; klass/funksiyalar (kirish → chiqish); kim kimga tayanadi; misol; xato/chekka holatlar; TZ'ga mosligi.

### A) `lib/` (toza mantiq)

#### A1. `lib/errors.py` (62 qator)
- **Vazifa.** Xatolar va ogohlantirishlar uchun umumiy turlar. Oddiy tilda: "spec'ning qaysi joyida (`path`), qanday muammo (`code`), nima deyish kerak (`message`)".
- **Asosiy:** `BoardError(code, path, message)` — `UserError` avlodi (`errors.py:6-21`), `.to_dict()` → `{"path","code","message"}`. `SpecInvalid(errors)` — hammasini bitta istisnoda yig'adi (`:24-29`). `BoardWarning(code, path, text)` (`:32-41`). `ValidationResult(errors, warnings)` — `.ok`, `.raise_if_invalid()`, `.to_dict()` (`:44-62`).
- **Kim ishlatadi.** Hamma `lib/` fayl, `engine.py`. **Tayanadi:** `odoo.exceptions.UserError`.
- **Misol.** `BoardError("UNKNOWN_FIELD","widgets[1].data.dimensions[0]","Model 'sale.report' has no field 'order_date'. Did you mean 'date'?").to_dict()` → `{"path":..., "code":"UNKNOWN_FIELD", "message":...}`: aynan TZ 4.4 dagi tuzatish sikli kutgan shakl.
- **Chekka holat.** `BoardError` `UserError` bo'lgani uchun Odoo uni "foydalanuvchi xatosi" deb ko'rsatadi (ish uchun qulay). Lekin Runner'dagi `except UserError` shoxi uni ham ushlaydi, shuning uchun u yerda alohida qayta ko'tariladi (`runner.py:81-82`).
- **TZ bilan mosligi: mos** (T6.8). `SpecInvalid` va `ValidationResult` TZ'da yo'q, qo'shimcha.

#### A2. `lib/i18n.py` (10 qator)
- **Vazifa.** Foydalanuvchi ko'radigan hamma matn `t()` orqali o'tadi. Hozir `t(text)` matnni o'zini qaytaradi (`i18n.py:9-10`). F9 da uz/ru tarjima shu yerga ulanadi, chaqiruvchilarga tegilmaydi.
- **Kim ishlatadi.** validator, runner, frame, explain, engine.
- **Chekka holat.** `t("...") % qiymat` shaklida ishlatilgan: tarjima qilingan matnda `%d` / `%s` tartibi saqlanishi kerak (F9 da diqqat).
- **TZ: TZ'da alohida modul sifatida yo'q**, T11 dagi "har matn `env._()` orqali" qoidasini bajarish uchun "eshik". **Qisman** mos: haqiqiy tarjima hali yo'q.

#### A3. `lib/catalog.py` (52 qator)
- **Vazifa.** Odoo'siz model/maydon ma'lumotnomasi. Validator va planner modelni shu orqali "ko'radi".
- **Klasslar.** `FieldInfo` (`:14-35`: `name, label, type, store, groupable, aggregator, selection, relation` + `is_temporal`, `is_numeric`, `selection_labels`), `ModelInfo` (`:38-47`: `fields`, `is_report`, `accessible`, `.field(name)`), `Catalog` Protocol (`:50-52`).
- **Misol.** `ModelInfo("sale.report","Sales Analysis Report",{...},is_report=True).field("price_subtotal").aggregator == "sum"`.
- **Chekka holat.** `Catalog.model()` yo'q modelda `None` qaytaradi (`UNKNOWN_MODEL` shundan).
- **TZ: mos** (T6, "Odoo'ga bog'lanmagan qism"). Testlarda soxta katalog (`tests/fixtures.py`) shu tufayli ishlaydi.

#### A4. `lib/spec.py` (313 qator)
- **Vazifa.** Spec'ning *tuzilmasi*: turlar, majburiy kalitlar, noma'lum kalit. Model/maydon mavjudligini bilmaydi.
- **Klasslar.** `Dimension` (`:66-93`, `"date:day"` qisqa shakli ham o'qiydi), `Measure` (`:96-128`, `is_count` `:105`), `Data` (`:131-200`), `Widget` (`:203-249`), `Spec` (`:252-294`). Doimiylar: `SPEC_VERSION=1`, `MAX_WIDGETS=30`, `MAX_SPEC_BYTES=256 KB` (`:13-15`), `SHAPES` (13 vidjet turi: min/max o'q va o'lchov, `:26-40`).
- **Funksiyalar.** `Spec.from_raw(dict)` / `.to_raw()`, `migrate(raw)` (`:301-313`, `MIGRATIONS={}` hozir bo'sh, `:298`), `Spec.size_bytes()` (`:293`).
- **Misol.** `{"v":1,"widgets":[{"id":"w1","type":"kpi","data":{...}}]}` → `Spec`; `to_raw()` aynan shu ko'rinishni qaytaradi (`test_round_trip_keeps_content`).
- **Xato/chekka holatlar.** Noma'lum kalit → `UNKNOWN_KEY` (yozuv xatosidan himoya, masalan `domian`); noto'g'ri tur → `BAD_SPEC` yo'li bilan (`widgets[0].data.limit`); `bool` son o'rniga rad etiladi (`_expect`, `:57-58`); `v` yo'q yoki 0 → `BAD_SPEC`; `v>1` → `UNSUPPORTED_VERSION`; vidjet/o'lchov `id` regex `^[a-z][a-z0-9_]{0,31}$` (`:44`). **Cheklov:** `filters`, `uncertain`, `assumptions`, `grid`, `view`, `interact` faqat tur jihatidan tekshiriladi (ro'yxat/lug'at), ichki mazmuni tekshirilmaydi va hech narsa ularni o'qimaydi (`:258-260`, `:209-211`).
- **TZ: mos** (T5, T5.4). `format` kaliti o'lchovda TZ'da yo'q, qo'shimcha (T6.9 ga yozilgan). `compare` kaliti o'qiladi (`:142`), lekin validator uni rad etadi.

#### A5. `lib/domain.py` (63 qator)
- **Vazifa.** Odoo domain'ini (prefiks yozuv: `["|", a, b]`) daraxtga o'qiydi. Faqat **tekshirish** uchun: qaysi maydonlar ishlatilgan, qaysi shartlar har doim bajarilishi shart. Baholamaydi (baholashni Odoo qiladi).
- **Funksiyalar.** `parse(domain)` (`:16-45`), `leaves(nodes)` (`:48`), `always_true_leaves(nodes)` (`:57`: faqat yuqori daraja va `&` ostidagilar, `|` va `!` ostidagilar kirmaydi), `is_leaf` (`:12`).
- **Misol.** `["|", ["a","=",1], ["b","=",2]]` → `[("|", ("a","=",1), ("b","=",2))]`; `always_true_leaves` shu uchun **bo'sh**.
- **Xato.** Tugamagan `["|", x]` → `INVALID_DOMAIN` (`:27`); noma'lum belgi `"%"` → `INVALID_DOMAIN` (`:31`).
- **TZ: TZ'da alohida yo'q** (kodda bor, TZ'da yo'q).

#### A6. `lib/filters.py` (206 qator)
- **Vazifa.** Spec ichidagi sanalarni **aniq** qiymatga aylantirish va "kun" ma'nosini to'g'rilash.
- **Funksiyalar.**
  - `resolve_relative("today =1d -1m", today)` → `date` (`:45-74`). Tokenlar chapdan o'ngga qo'llanadi. `=Nd/=Nm/=Ny` o'rnatadi, `+-Nd/w/m/y` siljitadi. Oy uzunligidan oshsa kesadi (`=31d` fevralda 28).
  - `today_in(tz, now_utc)` (`:77-80`), `local_start_utc(day, tz)` (`:83-87`), `local_date_of(value, field_type, tz)` (`:90-95`).
  - `resolve_domain(domain, field_types, tz, now_utc)` (`:129-159`) — domain'ni yangi ro'yxat qilib qaytaradi (kirishni o'zgartirmaydi).
  - `date_bounds(domain, field, type, tz)` (`:162-186`) → `(birinchi_kun, oxirgi_kundan_keyingi_kun)`.
  - `start_of`, `next_bucket` (`:189-206`): kun/hafta/oy/chorak/yil boshlari.
- **Eng muhim qoida (mahalliy kun).** `datetime` maydonda vaqtsiz qiymat (`"2026-11-05"` yoki `today`) butun **mahalliy kun**. Shuning uchun `<= bugun` → `< ertangi mahalliy yarim tun`; `= bugun` → ikki shartli oraliq (`:110-126`). Aks holda "bugungacha" bugunni yo'qotardi.
- **Misol (Toshkent).** `["date","=","2026-11-05"]` → `["&", ["date",">=","2026-11-04 19:00:00"], ["date","<","2026-11-05 19:00:00"]]`.
- **Xato/chekka holatlar.** Noto'g'ri ifoda → `ValueError` (validator `BAD_DATE` ga aylantiradi, `validator.py:129-133`). Haftaning boshi: `week_start` (1=dushanba) parametr, Odoo `get_lang(env).week_start` dan keladi. DST: `pytz.localize` standart `is_dst=False` bilan ishlaydi (soat o'tkazilgan yarim tunda ham xato bermaydi); `test_dst_zone` Nyu-York uchun tekshiradi.
- **Vaqt aralashishi.** `now_utc` **naive UTC** deb kutiladi, `today_in` ustiga `tzinfo=utc` qo'yadi (`:80`). Aware `datetime` berilsa va UTC bo'lmasa, tzinfo jimgina **ustidan yoziladi** (xato siljish). Hozir faqat `engine.py:63` chaqiradi (naive UTC), shuning uchun amalda xavf yo'q.
- **TZ: mos** (T5.1 nisbiy sanalar: `today`, `-7d`, `=1d`, `=1d -1m`, `=1m =1d`). Kun semantikasi TZ'da yo'q edi, qo'shildi (T6.9).

#### A7. `lib/validator.py` (314 qator)
- **Vazifa.** Spec'ni haqiqiy model va maydonlarga qarshi tekshirish. Xato bloklaydi, ogohlantirish ko'rsatiladi.
- **Kirish/chiqish.** `Validator(catalog).validate_widget(widget, path)` va `.validate_spec(spec)` → `ValidationResult` (`:61-106`).
- **Tekshiruvlar ketma-ketligi** (`validate_widget`, `:78-106`): tur → model → domain → o'qlar → o'lchovlar → tartib → limit/others → having → shakl → `compare` → ogohlantirishlar.
- **Asosiy qoidalar.**
  - `allowed_aggregates(field)` (`:32-47`): maydon `sum` qilinadi faqat Odoo uni `aggregator="sum"` deb e'lon qilgan bo'lsa; `price_unit` (`avg`) uchun faqat `avg/min/max/count_distinct`. Bu eski modulda yo'q edi.
  - O'lchov faqat modelning o'z saqlanadigan maydoni: nuqtali yo'l yoki hisoblanuvchi maydon → `LEVEL_MISMATCH` (`:207-215`). O'q esa maydon yoki **bitta** bog'lanish orqali (`partner_id.country_id`), ikki qadam yo'q (`:135-162`).
  - `others` faqat bitta o'q, `limit` bilan, `having`siz, faqat `sum/count` (`:236-255`).
  - Shakl jadvali `SHAPES` bo'yicha o'q/o'lchov soni, `line/area/kpi` birinchi o'qi sana bo'lishi, `pie` ≤ 8 bo'lak, `gauge` uchun `view.target` (`:271-294`).
  - `fill_gaps` sana o'qi (kun/hafta/oy/chorak/yil) va shu o'q bo'yicha tartibni talab qiladi (`:288-294`).
  - Ogohlantirishlar: `STATE_FILTER_MISSING`, `SUSPICIOUS_DATE` (`:296-310`).
- **Misol.** `{"field":"price_unit","agg":"sum"}` → `NOT_AGGREGATABLE: Field 'price_unit' cannot be summed. Allowed: avg, min, max, count_distinct.` (`widgets[1].data.measures[0]`).
- **Chekka holatlar / kamchiliklar.**
  - Qiymat tekshiruvi **yo'q** (3.2-bo'lim F): selection qiymati (`state` uchun `done`), `in` ga satr, tur mosligi.
  - Domain'dagi nuqtali yo'lning faqat birinchi qismi tekshiriladi (`:119`).
  - `_check_order` (`:232`) va `_check_having` (`:264`) `x in <set>` ishlatadi: ro'yxat/lug'at kelsa `TypeError`.
  - `STATE_FILTER_MISSING` faqat maydon aynan `state` deb nomlangan bo'lsa (`:300`).
  - `SUSPICIOUS_DATE` taklif qilgan "boshqa sana" ixtiyoriy: lug'atdagi birinchi sana maydoni (`:310`), eng mantiqiysi emas.
- **TZ bilan mosligi: qisman.** 6.7-bo'limdagi barcha kodlar bo'yicha jadval 5.4-bo'limda.

#### A8. `lib/planner.py` (177 qator)
- **Vazifa.** Tekshirilgan vidjetni `Plan`ga aylantiradi: Odoo'dan aynan nima so'raladi + natijani o'qish uchun metama'lumot (yorliqlar, turlar).
- **Kirish/chiqish.** `Planner(catalog).plan(widget, model_info, tz, now_utc, week_start)` → `Plan` (`:92-131`).
- **Nima qiladi.**
  - Domain'dagi sanalarni aniqlaydi (`filters.resolve_domain`, `:99`).
  - `groupby` (`"date:day"`), `aggregates` (`"price_subtotal:sum"`, takror bo'lmaydi: `dict.fromkeys`, `:102`).
  - Tartib: aniq berilgan bo'lsa shu; bo'lmasa vaqt o'qi bo'lsa `asc`, aks holda birinchi o'lchov `desc` (`:164-177`).
  - `query_limit`: `limit` berilgan bo'lsa shu, aks holda 201 (cap+1: kesilganini aniqlash uchun, `:106`).
  - Sana o'qi uchun `granularity` berilmasa `month` (`:141-142`).
  - `fill_gaps` bo'lsa `FillSpec` (chegaralar domain'dan, `:108-112`).
  - O'lchov turi: `monetary` maydon yoki `format="currency"`; `percent`; qolgani `number` (`:151-157`).
- **Misol.** Yuqorida 3.1 (Qadam 5).
- **Chekka holat.** Planner **tekshirilgan** vidjetni kutadi (shartnoma): `_dim_meta` (`:139`) `catalog.model(...).field(sub)` ni tekshirmasdan chaqiradi. Validatorni chetlab o'tib chaqirilsa `AttributeError` mumkin. Hozir yagona chaqiruvchi (`engine._run_widget`) validatordan keyin chaqiradi (`engine.py:57-63`).
- **TZ: mos** (T6.1 "Planner"). `compare` uchun ikkinchi reja **yo'q** (F6).

#### A9. `lib/runner.py` (83 qator)
- **Vazifa.** Rejaning ma'lumotlar bazasi bilan **yagona** uchrashuv joyi. Oddiy tilda: "kassir": faqat foydalanuvchining o'z kartasi (huquqi) bilan to'laydi.
- **Funksiyalar.** `Runner(env, timeout_ms=8000).run(plan)` → `RawResult(groups, total)` (`:35-46`); `currency_ids(plan)` (`:48-54`); `_guard()` (`:63-83`).
- **Himoyalar (`_guard`).**
  - `cr.savepoint()` — vidjet muvaffaqiyatsiz bo'lsa faqat shu blok orqaga qaytadi (`:69`).
  - `set_config('statement_timeout', '8000', true)` — `SET LOCAL` ekvivalenti; muvaffaqiyatda eski qiymat tiklanadi (`:66-72`). Xomaki so'rov faqat shu uchtasi, parametrlar bilan.
  - `AccessError` → `BoardError("NO_ACCESS")` (`:73-74`); `QueryCanceled` → `TIMEOUT` (`:75-79`); `UserError/ValueError/KeyError/psycopg2.Error` → `QUERY_FAILED` (`:80-83`).
- **Misol.** Foydalanuvchi sotuvga ruxsatsiz bo'lsa: `formatted_read_group` `AccessError` ko'taradi → `BoardError("NO_ACCESS","data","You are not allowed to see this data.")` → vidjet natijasi `{"error": {...}}`.
- **Chekka holatlar.**
  - **Ushlanmaydigan turlar:** `TypeError`, `AttributeError` va boshqa `Exception` ushlanmaydi (bu "bo'sh `except Exception` yo'q" qoidasining natijasi, lekin amalda 3.2-B jadvalidagi qulashga olib keladi).
  - `TIMEOUT` xabari `timeout_ms // 1000` soniya deydi: 1000 ms dan kichik chegarada "0 seconds" (kosmetik, `:78`).
  - `RawResult.total` faqat `others` uchun (`:42-45`).
  - `currency_ids` alohida savepoint ochadi (ikkinchi guard).
- **TZ bilan mosligi: mos** (T6.2): `sudo` yo'q, `statement_timeout = 8000` ms, vidjet bo'yicha savepoint. **Yo'q:** kesh (T6.2, "2-bosqichdan keyin" deb belgilangan).

#### A10. `lib/frame.py` (184 qator)
- **Vazifa.** Odoo xom guruhlarini brauzer chizadigan jadvalga aylantirish.
- **Kirish/chiqish.** `FrameBuilder().build(plan, groups, total, currency, warnings)` → `Frame(columns, rows, meta)` (`:33-63`); `.to_dict()`.
- **Qoidalar.**
  - Yorliqlar odam tilida: selection → yorliq, many2one → nom, bo'sh → "Not set", boolean → "Yes/No", sana qismi (hafta kuni) → `int` (`_dim_cell`, `:79-93`).
  - Sana o'qi qiymati foydalanuvchi vaqt zonasidagi `YYYY-MM-DD` (`local_day`, `:178-184`).
  - `group_refs` — drill uchun xom kalitlar (`_dim_ref`, `:95-104`).
  - Guruhlar `plan.cap` (200) dan oshsa kesiladi va `TOO_MANY_GROUPS` ogohlantirishi (`:36-40`).
  - **Bo'sh kunlarni to'ldirish** (`_fill`, `:114-161`): chegaralar domain'dan, bo'lmasa mavjud ma'lumot oralig'idan; ikki o'qli holatda har qator (seriya) uchun alohida; `MAX_FILL_BUCKETS=3700` dan ko'p bo'lsa to'ldirilmaydi (`:18`, `:132-133`); sanasiz qator oxirida; tartib `asc/desc`.
  - **"Others"** (`_others_row`, `:165-175`): jami minus ko'rsatilganlar yig'indisi; `count` butun son; hammasi ~0 bo'lsa qator qo'shilmaydi.
- **Misol.** 3.1 (Qadam 7).
- **Chekka holatlar.** Ikki o'qli frame'da bir xil maydon ikki marta bo'lsa (`date:day` va `date:month`) ustun `id`si takrorlanadi (`:71` `d.field`), frontend uchun chalkashlik. `avg` bo'sh kun uchun `None`, jamlama uchun `0` (`planner.py:54-57`).
- **TZ bilan mosligi: qisman.** Frame ko'rinishi T6.3 ga mos. **Yo'q:** `compare_rows` (F6). `meta.currency` ga `mixed` qo'shimcha (T6.6 ga mos).

#### A11. `lib/explain.py` (140 qator)
- **Vazifa.** "Men nima qildim" qatorlarini **koddan** yozish (AI emas), haqiqiy rejaga qarab.
- **Kirish/chiqish.** `ExplainBuilder(resolve_names).build(widget, model, plan, currency, warnings)` → `[{"kind","text","detail"}]` (`:41-49`).
- **Qoidalar.** `kind`: `source`, `measure`, `group`, `filter`, `date`, `cut`, `warning`. "Muhim" (ochiq ko'rinadigan, `detail=False`): pul o'lchov, selection filtri (masalan holat), sana oralig'i, kesish, ogohlantirishlar. Qolgani "batafsil" (`detail=True`). Muhim qatorlar eng ko'pi 5 (`MAX_IMPORTANT`, `:17`, `:132-140`), ogohlantirishlar cheklanmaydi. Texnik nom ko'rsatilmaydi (yorliqlar `ModelInfo`dan). Bog'langan yozuv id'lari nomga aylantiriladi (`resolve_names`, `:115-116`).
- **Misol.** `"Status is one of Sales Order, Cancelled."` (`["state","in",["sale","cancel"]]` uchun).
- **Chekka holat (xato).** `resolve_names` chaqiruvi himoyasiz: `engine._resolve_names` (`engine.py:92-94`) `display_name` ni o'qiydi; foydalanuvchi o'qiy olmaydigan modelga bog'langan filtrda `AccessError` ko'tariladi va `_run_widget` faqat `BoardError` ushlaydi. Jonli tasdiqlangan (3.2-G).
- **Boshqa kamchilik.** `warning.text if hasattr(warning,"text") else warning["text"]` (`:48`): ikki xil tur qabul qilinadi (kod hidi). `_filters(self, widget, ...)` da `widget` ishlatilmaydi.
- **TZ bilan mosligi: qisman** (T7.4). AI dan keladigan `uncertain[]` qismi hali yo'q (F5). Matnlar ingliz tilida, tarjima F9.

### B) `models/`

#### B1. `models/env_catalog.py` (46 qator)
- **Vazifa.** `Catalog`ning Odoo versiyasi: model va maydonlarni **joriy foydalanuvchi ko'rishi mumkin bo'lgan** ko'rinishda beradi.
- **Qanday.** `name in env` (model bormi, `:22`) → `has_access("read")` (`:27`) → `fields_get(attributes=[type,string,store,groupable,aggregator,selection,relation])` (`:30`). `fields_get` maydon guruhlari (`groups=`) bo'yicha allaqachon filtrlaydi, shuning uchun o'qiy olmagan maydon "noma'lum" bo'ladi.
- **Misol.** `catalog.model("sale.report")` → `ModelInfo(is_report=True, fields={"date": FieldInfo(type="datetime"), ...})`. `omborchi` uchun `accessible=False, fields={}`.
- **Chekka holatlar.** Keshlanadi (`_cache`), lekin faqat shu `EnvCatalog` obyekti ichida (har `_run_spec` chaqiruvida yangi). `groupable` yo'q bo'lsa `True` deb olinadi (`:39`).
- **TZ: mos** (T10 "foydalanuvchi huquqi").

#### B2. `models/engine.py` (94 qator)
- **Vazifa.** Toza qismlarni Odoo muhitiga ulaydigan **yupqa yelim**. `levelix.board.engine` — `AbstractModel` (jadvali yo'q).
- **Metodlar.**
  - `_validate_spec(raw)` → `{"ok","errors","warnings"}` (`:29-36`). Struktura xatosini `BoardError` sifatida ushlaydi va `ok=False` qaytaradi.
  - `_run_spec(raw, widget_ids=None, explain=False)` → `{"widgets": {id: {"frame":...,"explain":...} | {"error":...}}}` (`:38-51`).
  - `_run_widget` (`:55-74`): validatsiya → `tz` (kontekst yoki foydalanuvchi) → `week_start` → `Planner` → `Runner` → `_currency_meta` → `FrameBuilder` → (ixtiyoriy) `ExplainBuilder`.
  - `_currency_meta` (`:76-90`): pul o'lchov bo'lmasa `None`. Hisobot modelida kompaniya valyutasi. Oddiy modelda `currency_id` bo'yicha qo'shimcha so'rov: >1 valyuta → `MIXED_CURRENCY` ogohlantirishi va `{"mixed": True}`.
- **Nega metodlar `_` bilan boshlanadi.** Odoo RPC (`call_kw`) `_` bilan boshlangan metodni tashqaridan chaqirtirmaydi. Haqiqiy ochiq `lx_*` metodlari F2 da keladi va har birida huquq tekshiriladi (`engine.py:3-5`).
- **Misol.** 3.1.
- **Chekka holatlar.**
  - Faqat `BoardError` ushlanadi (`:73`); boshqa istisno **butun `_run_spec`ni** to'xtatadi.
  - `datetime.utcnow()` (`:63`): Python 3.12 da eskirgan (deprecated) va naive. Konteynerda Python 3.12.3.
  - `widget_ids` mavjud bo'lmagan id'ni jimgina tashlaydi (`:48`).
  - `_resolve_names` himoyasiz (yuqoridagi A11).
- **TZ bilan mosligi: qisman.** `lx_*` metodlar yo'q (T9). `_run_spec`ning vidjet bo'yicha izolyatsiyasi `BoardError` doirasida ishlaydi.

### C) `security/`, `views/`, `data/`, `ir.model.access`, record rule'lar
**KODDA YO'Q.** Sababi: hozirgi faqat `AbstractModel` bor (`engine.py:23-25`), unga `ir.model.access` kerak emas. Saqlanadigan modellar (`levelix.board`, `levelix.board.version`) F2 da keladi, huquqlar o'sha vaqtda yoziladi (T3.1, T10). Huquq xavfsizligi hozir faqat "Odoo o'zi" orqali: `with_user(...)` env + `has_access` + record rule'lar (jonli test: `tests/test_engine.py:129-152`).

### D) Frontend (`static/src`: core, grid, widgets, charts, theme, page)
**KODDA YO'Q.** Hech qanday `.js`, `.xml`, `.scss`, `.css` fayl yo'q; manifestda `assets` yo'q. Bu F3 ishi (reja: `AI_DASHBOARD_PHASES.md`, F3 bo'limi). Backend frontend uchun tayyorlab qo'ygan narsa: `Frame` shakli (`frame.py:22-29`), `meta.currency`, `meta.warnings`, `meta.group_refs`, `explain` qatorlari.

### E) `tests/` (1 099 qator, 105 ta)

Men test fayllarini bu tahlil uchun qayta satrma-satr o'qimadim: ularni shu sessiyada o'zim yozganman va hozir test nomlarini qator raqamlari bilan ro'yxatladim hamda to'liq to'plamni ishga tushirdim (0 xato). Quyida nima sinalgani:

| Fayl | Testlar | Sinalgan |
|---|---|---|
| `test_spec.py` | 11 | aylanma saqlash (round-trip), qisqa o'q shakli, noma'lum kalit va yo'l, noto'g'ri turlar, bool≠son, o'lchov majburiy maydonlari, versiya, `migrate` kirishni o'zgartirmasligi, o'lcham |
| `test_filters.py` | 18 | nisbiy ifodalar, oy oxiriga kesish, xato ifodalar, vaqt zonasi kuni, DST (Nyu-York), kun/hafta/oy/chorak/yil boshlari, datetime kun semantikasi (`<=`, `>`, `=`, `!=`), sana maydoni, aniq vaqt tegilmasligi, ro'yxat va mantiqiy operatorlar, `date_bounds` (oraliq, ochiq, `|`, `&`) |
| `test_validator.py` | 20 | namunaviy spec to'g'ri; `UNKNOWN_MODEL`, `NO_ACCESS`, `UNKNOWN_FIELD` + tavsiya, `NOT_AGGREGATABLE`, `LEVEL_MISMATCH`, bitta bog'lanish, `BAD_GRANULARITY`, domain (`BAD_OPERATOR`, `INVALID_DOMAIN`, `BAD_DATE`), `BAD_ORDER`, `others` qoidalari + `NON_ADDITIVE_OTHERS`, `having`, shakllar, `fill_gaps`, `UNSUPPORTED`, ikkala ogohlantirish, dublikat id, 30 vidjet chegarasi, xato yo'li |
| `test_planner.py` | 13 | vaqt qatori, top-N, standart granularity, sana hal qilinishi, `fill` chegaralari, tartib, o'lchov kalitlari, `format`, `having`, bog'langan o'q, selection yorliqlari |
| `test_frame.py` | 19 | mahalliy kun, ustun/qator, `group_refs`, yorliqlar ("Not set", Yes/No), sana qismi, bo'sh jamlama, `TOO_MANY_GROUPS`, bo'shliqlar (kun, oy, hafta, ikki o'q, kamayish tartibi, sanasiz qator, juda katta oraliq), "Others" |
| `test_explain.py` | 9 | oddiy so'zlar, muhim/batafsil bo'linishi, kesish, texnik nom yo'qligi, selection yorliqlari, yozuv nomlari, ogohlantirishlar, 5 qator chegarasi, aralash valyuta |
| `test_engine.py` | 15 (post-install) | **haqiqiy ORM**: jami (valyuta kursi bilan, mustaqil hisob), kun vaqt zonasida, bo'shliqlar, hafta/oy qutilari Odoo bilan mos, "Others" yig'indisi, `group_refs`, sotuvga ruxsatsiz foydalanuvchi + boshqa vidjetlar ishlashda davom etishi, ikkinchi kompaniya, `statement_timeout` tiklanishi, aralash/yagona valyuta, xato yo'li, `_validate_spec` qulamasligi, tushuntirish, nisbiy sana |

**Sinalmagan** (5.5-bo'lim ham):
- `TIMEOUT` yo'li (faqat shu hujjat uchun qo'lda sinaldi, testda yo'q).
- `QUERY_FAILED` va `UNKNOWN_MODEL` (runner darajasida) yo'li.
- `explain` paytida `AccessError` (xato borligi shu hujjatda topildi).
- `widget_ids` (mavjud bo'lmagan id, noto'g'ri tur).
- Noto'g'ri tuzilgan JSON qiymatlar (ro'yxat/lug'at kutilmagan joyda).
- Ikki o'qli `fill_gaps` Odoo'ning haqiqiy natijasi bilan (faqat soxta ma'lumotda sinalgan).
- Bir nechta kompaniya, har xil `tz` bilan, `week` guruhlash `week_start=7` (Yakshanba) da Odoo bilan solishtirish.
- Katta ma'lumotda tezlik (F9 ga qoldirilgan).

---

## 5. Maxsus tekshiruvlar: aniq javoblar

### 5.1. Xavfsizlik va chidamlilik savollari

| Savol | Javob | Dalil |
|---|---|---|
| Runner `AccessError`ni qanday ushlaydi? | `BoardError("NO_ACCESS")` ga aylantiradi | `runner.py:73-74` |
| Bitta vidjetda `AccessError` butun `_run_spec`ni qulatadimi? | **Runner ichida bo'lsa: yo'q.** `_run_widget` `BoardError`ni ushlab `{"error":...}` qaytaradi, qolgan vidjetlar ishlaydi (test: `test_engine.py:129`; jonli: omborchi `NO_ACCESS`). **Lekin `explain` paytidagi `AccessError` qulatadi** (Runner'dan tashqarida) | `engine.py:73`, `explain.py:115-116`, jonli G |
| Har vidjet `cr.savepoint()` ichidami? | Ha: `_guard()` har Runner chaqiruvida (`run` va `currency_ids`) alohida savepoint ochadi | `runner.py:69` |
| `SET LOCAL statement_timeout` bormi, qiymati? | Ha: `set_config('statement_timeout','8000',true)` (= `SET LOCAL`), **8000 ms**, so'ng eski qiymat tiklanadi. `statement_timeout` har *so'rov* uchun (vidjet jami emas) | `runner.py:21,70,72` |
| Biznes ma'lumotga `sudo()` bormi? | **Yo'q** | grep `sudo` → faqat `runner.py:3` izohi |
| Xom SQL, `eval` bormi? | `eval/exec` yo'q. Xom SQL: faqat 3 ta `cr.execute` (timeout o'qish/o'rnatish/tiklash), parametrlangan | `runner.py:66,70,72`; grep |
| `lx_drill` klientdan domain oladimi? | **`lx_drill` KODDA YO'Q** (F2). Mo'ljal: klient faqat `group_ref` (qator kaliti) beradi, domain'ni server `__extra_domain` dan qayta hosil qiladi (T2.3, T7.1). Hozir `group_refs` tayyor, `__extra_domain` kodda ishlatilmaydi | grep `__extra_domain` bo'sh; `frame.py:95-104` |
| `__extra_domain` qanday ishlatiladi (TZ: "tekshirilmagan" ro'yxati)? | F0 da **tasdiqlangan** (`notes/F0_natijalar.md`, spike 2): sana uchun `['&',('date','>=',...),('date','<',...)]` (UTC, tz hisobga olingan); sana qismi uchun `('date.day_of_week','=',0.0)`. `map` bilan `sale.order`ga o'tkazilganda 28 kun, 7 hafta kuni, 10 soat bo'yicha 0 farq. Lekin bu faqat skriptda, **`levelix_board` kodida yo'q** | `scripts/spike_read_group.py` |
| `datetime.utcnow()` va naive/aware aralashuvi | Faqat bitta chaqiruv: `engine.py:63`, naive UTC; `filters.today_in` unga `tzinfo=utc` qo'yadi (`filters.py:80`). Hozircha mos, lekin (a) `utcnow` Python 3.12 da eskirgan, (b) aware UTC bo'lmagan qiymat berilsa jimgina noto'g'ri bo'ladi. Boshqa joyda aware/naive aralashmaydi: DB sanalari matn (`"%Y-%m-%d %H:%M:%S"`), faqat `local_date_of` aware yasaydi | `filters.py:80,94` |
| `widget_ids`da mavjud bo'lmagan id kelsa? | Jimgina tashlanadi, xato yo'q (`{"widgets": {}}`). Satr berilsa qism-satr bo'yicha mos keladi | jonli A; `engine.py:48` |
| `fill_gaps` (`fill_temporal`) qanday? | Odoo'ning `fill_temporal`i **ishlatilmaydi** (tz bilan qulaydi, F0 da aniqlangan). O'zimizning `_fill`: kun/hafta/oy/chorak/yil, ikki o'qli seriya, chegaralar domain'dan, kamayish tartibi, 3700 dan ko'p oraliq to'ldirilmaydi. **Ishlaydi** (test_frame 8 ta + test_engine 3 ta) | `frame.py:114-161` |
| `compare` qanday? | **Amalga oshirilmagan.** Spec o'qiydi (`spec.py:142`), validator `UNSUPPORTED` bilan rad etadi, planner'da ikkinchi reja yo'q, Frame'da `compare_rows` yo'q. F6 ga rejalangan | `validator.py:102-103` |
| `others` / `NON_ADDITIVE_OTHERS` | Amalga oshirilgan va sinalgan: `avg/min/max/count_distinct` bilan rad etiladi; `having`, ko'p o'q, `limit`siz ham rad | `validator.py:236-255`; `test_validator.py:107` |
| `calc` parseri, `eval` yo'qligi | **Parser yo'q.** `calc` validator'da `UNSUPPORTED` (`validator.py:201-203`). `eval` umuman yo'q (grep). F6 da `report_constructor/models/formula.py` (204 qator, `ast` oq ro'yxat, `eval`siz) ni olish rejalangan | F0 notes |
| `MIXED_CURRENCY` | Amalga oshirilgan: `sale.order` kabi oddiy modelda `currency_id` bo'yicha qo'shimcha so'rov, >1 valyuta → ogohlantirish + `meta.currency={"mixed":true}`. Hisobot modellarida (`_auto=False`) tekshirilmaydi (ular kompaniya valyutasiga o'tkazadi, F0 da `sale.report` uchun tasdiqlangan) | `engine.py:76-90`; `test_engine.py:163-178` |
| `SPEC_TOO_LARGE`, guruhlar limiti | 30 vidjet va 256 KB (`validator.py:63-66`); guruhlar 200 (kesilsa `TOO_MANY_GROUPS`), `limit` ≤ 500 (`BAD_LIMIT`) | `planner.py:14`, `frame.py:36-40` |

### 5.2. Jonli sinovlarning xulosasi
3.2-bo'limda. Eng muhimlari: `TypeError`, `AccessError` qulashi, qiymat tekshiruvi yo'qligi, TZ misolining `compare` sababli rad etilishi.

### 5.3. `grep` natijasi (ishlab chiqarish kodida)
`sudo|eval(|exec(|.execute(|utcnow|datetime.now|subprocess`:
`lib/runner.py:3` (izoh), `:66,70,72` (3 ta `cr.execute`), `models/engine.py:63` (`utcnow`). Boshqa hech narsa.

### 5.4. Himoya kodlari jadvali (T6.7 va qo'shimchalar)

| Kod | TZ'da | Kodda | Qayerda | Test |
|---|---|---|---|---|
| `UNKNOWN_MODEL` | ha | ✅ | `validator.py:88`, `runner.py:60` | validator |
| `UNKNOWN_FIELD` | ha | ✅ (+ "Did you mean") | `validator.py:121-124,141,156,211` | ha |
| `NO_ACCESS` | ha | ✅ | `validator.py:91`, `runner.py:74` | validator + engine |
| `NOT_AGGREGATABLE` | ha | ✅ | `validator.py:198-221` | ha |
| `BAD_GRANULARITY` | ha | ✅ | `validator.py:175-183` | ha |
| `BAD_SHAPE` | ha | ✅ (13 tur jadvali) | `validator.py:271-294` | ha |
| `NON_ADDITIVE_OTHERS` | ha | ✅ | `validator.py:248-255` | ha |
| `LEVEL_MISMATCH` | ha | ✅ (o'lchov: nuqtali/hisoblanuvchi; o'q: ≤1 bog'lanish) | `validator.py:143-152,207-215` | ha |
| `TOO_MANY_GROUPS` | ha (kesiladi + ogohlantirish) | ✅ | `frame.py:36-40` | ha |
| `MIXED_CURRENCY` | ha | ✅ (faqat oddiy modelda) | `engine.py:84-87` | ha |
| `STATE_FILTER_MISSING` | ha | ✅ | `validator.py:300-304` | ha |
| `SUSPICIOUS_DATE` | ha | ✅ | `validator.py:305-310` | ha |
| `SPEC_TOO_LARGE` | ha | ✅ | `validator.py:63-66` | ha |
| `DRILL_UNMAPPED` | ha (T7.1) | ❌ drill yo'q | F2 | yo'q |
| `UNKNOWN_KEY`, `BAD_SPEC`, `UNSUPPORTED_VERSION`, `UNKNOWN_TYPE`, `DUPLICATE_ID`, `BAD_OPERATOR`, `BAD_DATE`, `INVALID_DOMAIN`, `NOT_GROUPABLE`, `BAD_ORDER`, `BAD_LIMIT`, `BAD_HAVING`, `UNKNOWN_MEASURE`, `BAD_FORMAT`, `UNSUPPORTED` | yo'q (T6.9 ga keyin yozilgan) | ✅ | validator/spec | ha |
| `TIMEOUT`, `QUERY_FAILED` | yo'q | ✅ | `runner.py:75-83` | ❌ test yo'q |
| **Domain qiymat tekshiruvi** (selection qiymati, tur) | yo'q (lekin kerak) | ❌ | — | — |

---

## 6. 1-bosqich tugash mezonlari (T13, 1-qator)

TZ: "`levelix_board`: spec, validator, ijrochi, frame, 4 vidjet (kpi, area, bar, table), drill-down, saqlash. Qo'lda yozilgan spec." Tugadi, agar: "5.1 dagi misol ishlaydi; to'lqinda kunni bosganda o'sha kun buyurtmalari ochiladi; jami `sale.report` bilan mos; huquq testi o'tadi."

| Band | Holat | Dalil / izoh |
|---|---|---|
| Spec formati | **TAYYOR** | `lib/spec.py`, 11 test |
| Validator | **TAYYOR** (kamchiliklar bilan, 7-bo'lim) | `lib/validator.py`, 20 test |
| Ijrochi (filters, planner, runner) | **TAYYOR** | `lib/filters.py`, `planner.py`, `runner.py` |
| Frame | **TAYYOR** (`compare_rows` F6 da) | `lib/frame.py`, 19 test |
| "Men nima qildim" bloki (kodda) | **TAYYOR** (TZ'da 2-bosqichda edi, oldinroq qurildi) | `lib/explain.py`, 9 test |
| 5.1 misoli ishlaydi | **QISMAN** | TZ misoli aynan yozilganidek `UNSUPPORTED compare` bilan **rad etiladi**; `compare`siz ishlaydi (w1: 54 qator, w2: 10 tovar + "Others") |
| 4 vidjet: kpi, area, bar, table (ko'rinishi) | **YO'Q** | frontend yo'q (F3). Backend bu 4 tur uchun to'g'ri ma'lumot beradi (`scripts/f1_compare.py`, `smoke_engine.py`) |
| Drill-down: to'lqinda kunni bosish → o'sha kun buyurtmalari | **YO'Q** (QISMAN tayyorgarlik) | `group_refs` bor (`frame.py:95-104`); drill serveri va yon jadval yo'q; F0 da g'oya tasdiqlangan |
| Jami `sale.report` bilan mos | **TAYYOR** | `test_engine.py:70-76` (buyurtmalarning o'z `currency_rate`i bilan mustaqil hisob), `scripts/f1_compare.py` (SQL), Odoo'ning tayyor dashboard'idagi sonlar |
| Huquq testi | **TAYYOR** | `test_engine.py:129-143` (ruxsatsiz foydalanuvchi, boshqa vidjetlar ishlaydi), `:144-152` (boshqa kompaniya) |
| Saqlash (`levelix.board`, versiyalar) | **YO'Q** | model yo'q (F2) |
| Qo'lda yozilgan spec | **QISMAN** | spec'ni kiritish uchun forma/ekran yo'q, faqat Python/shell orqali |

**Testlar.** `scripts/run_tests.sh` ishga tushirildi (2026-11-05 07:48): `0 failed, 0 error(s) of 105 tests`. Buyruq: `docker exec levelix-aidash odoo -d aidash -u levelix_board --test-tags /levelix_board --test-enable --http-port=8099 --stop-after-init`.

**Umumiy baho (TZ 1-bosqich = F1+F2+F3):** F1 **tayyor** (kamchiliklar bilan), F2 va F3 **boshlanmagan**. Ya'ni 1-bosqichning backend "miya" qismi bajarilgan, foydalanuvchi ko'radigan va saqlaydigan qismi hali yo'q.

---

## 7. Bo'shliqlar, xavflar, 2-bosqichga tayyorlik

### 7.1. TZ'da bor, kodda yo'q

| Nima | Qayerda kerak | Faza |
|---|---|---|
| `levelix.board`, `levelix.board.version` modellari, `share_mode` | T3.1 | F2 |
| `lx_list/load/run/drill/save/restore/explain/share/apply_patch` | T9 | F2, F7 |
| Drill-down serveri, `map`, `DRILL_UNMAPPED`, saqlashda drill dry-run | T7.1 | F2 |
| Huquqlar (`ir.model.access`, record rule'lar, board-manager guruhi), ko'ruvchi "o'z huquqi bilan" | T3.1, T10 | F2 |
| Frontend: dizayn tokenlari, grid, vidjet reyestri, adapter, sahifa | T8 | F3 |
| `compare` (`previous_period/year`), `calc`, global filtrlar (`filters`/`applies_to`), cross-filter | T5.1, T5.3 | F6 |
| `update_dashboard` va JSON Patch qo'llash (`uncertain[].patch`) | T7.2 | F5/F7 |
| Kesh (TTL 60 s, kalit: xesh+user+kompaniyalar) | T6.2 | F9 yoki keyin |
| `levelix.ai.hint` reyestri | T7.3 | F5 |
| `interact.on_click` tekshiruvi | T7.1 | F2 |
| Eski `levelix_ai` dashboard elementlarini migratsiya | T1.1 | F9 |

### 7.2. Kodda bor, TZ'da yo'q (yoki keyin qo'shilgan)

`lib/errors.py` (`SpecInvalid`, `ValidationResult`), `lib/i18n.py` (tarjima eshigi), `lib/catalog.py` (`FieldInfo/ModelInfo/Catalog` abstraksiyasi), `lib/domain.py` (domain o'quvchi), 15 ta qo'shimcha xato kodi, o'lchovdagi `format`, kun semantikasi, `UNKNOWN_KEY` himoyasi (yozuv xatosidan), "Did you mean" tavsiyasi, `TIMEOUT/QUERY_FAILED`, tushuntirishning 5 qatorli "muhim/batafsil" bo'linishi. Hammasi T6.9 ga yozib qo'yilgan.

`TODO/FIXME/XXX/HACK` izohlari: **yo'q** (grep).

### 7.3. Texnik qarz va xavfli joylar (muhimlik tartibida)

| # | Daraja | Muammo | Dalil | Tavsiya |
|---|---|---|---|---|
| 1 | **Yuqori** | Kutilmagan JSON qiymat (`having`/`order.by` da ro'yxat, domain qiymati lug'at) `TypeError` bilan **butun `_validate_spec`/`_run_spec`ni** qulatadi. AI chiqishi oldindan noma'lum bo'lgani uchun bu F5 da muqarrar uchraydi | `validator.py:232,264`; `engine.py:73`; jonli B | (a) `_run_widget` da `Exception` ni (faqat `BoardError` emas) vidjet xatosiga aylantirish va jurnalga yozish; (b) `_check_order/_check_having` da turni tekshirish (`isinstance(x, str)`) |
| 2 | **Yuqori** | `explain` paytidagi `AccessError` butun ishga tushirishni qulatadi | `explain.py:115-116`, `engine.py:92-94`; jonli G | `_resolve_names` ni `try/except AccessError` ga olish (yozuv nomi o'rniga "kompaniya yozuvi" deb ko'rsatish) yoki `_guard` ichiga olish; test qo'shish |
| 3 | **Yuqori** | Domain **qiymati** tekshirilmaydi: mavjud bo'lmagan holat (masalan `done`), `in` ga satr. Xatosiz 0 qator. Odoo 19 da `state=done` yo'q, TZ misollari avval shunday yozilgan edi | jonli F; `validator.py:110-133` | selection qiymatini `FieldInfo.selection` bo'yicha tekshirish (`UNKNOWN_VALUE`), `in/not in` uchun ro'yxat talabi, many2one uchun son/ro'yxat. AI aniqligi uchun eng foydali yagona qo'shimcha |
| 4 | O'rta | TZ 5.1 misoli aynan yozilganidek ishlamaydi (`compare`) | jonli H | F6 gacha TZ'dagi misolni `compare`siz ko'rsatish yoki testda shu misol uchun alohida aniq kutuv |
| 5 | O'rta | Nuqtali domain yo'lida faqat birinchi qism tekshiriladi, qolgani `QUERY_FAILED` ("Invalid field res.partner...") bo'ladi, AI uchun ravshan emas | `validator.py:119`; jonli F | yo'lni `catalog` orqali oxirigacha yurish |
| 6 | O'rta | `widget_ids`: yo'q id jimgina tashlanadi; satr berilsa qism-satr mantig'i | `engine.py:48` | `list/tuple/set` talab qilish, yo'q id uchun `{"error": UNKNOWN_WIDGET}` qaytarish |
| 7 | O'rta | `TIMEOUT`, `QUERY_FAILED`, `UNKNOWN_MODEL` (runner) uchun avtomatik test yo'q | `runner.py:60,75-83` | test qo'shish (kichik chegara va `pg_sleep` bilan) |
| 8 | Past | `datetime.utcnow()` eskirgan; `today_in` aware qiymatni jimgina buzishi mumkin | `engine.py:63`; `filters.py:80` | `datetime.now(timezone.utc)` ishlatib, `today_in` da aware qiymatni to'g'ri qabul qilish |
| 9 | Past | Frame ustun `id`lari takrorlanishi mumkin (bir maydon ikki granularity bilan) | `frame.py:71` | `id` sifatida `d.key` ishlatish |
| 10 | Past | `TIMEOUT` xabarida "0 seconds" (chegara <1 s) | `runner.py:78` | `max(1, ...)` yoki millisekund |
| 11 | Past | `explain` da `warning.text if hasattr...` (ikki tur) va ishlatilmaydigan `widget` parametri | `explain.py:48,74` | bir turga keltirish |
| 12 | Past | `spec.py` (313) va `validator.py` (314) qatori 300 dan oshgan (T11 qoidasi model fayllari uchun, `lib/` uchun qat'iy emas) | — | F6 da `validator`ni `domain`/`measures`/`shape` fayllarga bo'lish |
| 13 | Past | Domain operatorlari ro'yxati (`any`, `not any` yo'q) AI ba'zan ishlatishi mumkin bo'lgan imkoniyatni rad etadi | `validator.py:22-25` | F5 oltin to'plami ko'rsatganda qo'shish |
| 14 | Past | Odoo yangi versiyasiga bog'liqlik nuqtalari: `formatted_read_group` imzosi (`runner.py:38-41`), `fields_get` `groupable/aggregator` kalitlari (`env_catalog.py:6`), `get_lang` (`engine.py:10`) | — | T14 da qayd etilgan: Odoo'ga bog'liq joy kam |

### 7.4. 2-bosqichda AI ulanganda: nima to'g'ridan-to'g'ri ishlatiladi, nima o'zgaradi

**To'g'ridan-to'g'ri ishlatiladi** (`levelix_ai_board` shu metodlarni chaqiradi):
- `levelix.board.engine._validate_spec(spec)` → `build_dashboard` vositasining tekshiruvi. Qaytgan `errors[]` ning `{path, code, message}` shakli TZ 4.4 dagi tuzatish sikli kutgan shaklga aynan mos (`BoardError.to_dict`, `errors.py:20-21`).
- `levelix.board.engine._run_spec(spec, widget_ids=[id], explain=True)` → `preview_widget` (dry-run) va qoralama uchun.
- `ExplainBuilder` → "Men nima qildim" bloki tayyor. AI faqat `uncertain[]` ni yozadi.
- `Validator.warnings` → blokdagi ogohlantirishlar.
- `EnvCatalog` → `describe_model`/`find_models` vositalari uchun asos bo'la oladi (model/maydonni foydalanuvchi huquqi bo'yicha beradi).

**O'zgarishi/qo'shilishi kerak:**
1. **Chidamlilik (yuqoridagi #1, #2, #3)** AI yuborgan beqaror chiqish bilan to'qnashishdan oldin tuzatilishi shart. Aks holda "AI xato yubordi → butun suhbat tushunarsiz xato bilan qulaydi".
2. **Maxfiylik rejimi (`aggregates`/`schema`).** `_run_spec` to'liq `rows` qaytaradi. AI ga faqat shakl ("12 guruh, 1 ustun") yuborish uchun `to_ai(result, mode)` qatlami kerak (T4.5), hozir yo'q. `Frame.rows` ni to'g'ridan-to'g'ri AI ga bermaslik kerak.
3. **`preview_widget` namunasi:** aggregat rejimida ~10 qator kesish; hozir `limit` spec orqali.
4. **`update_dashboard` va patch** (`uncertain[].patch`): JSON Patch qo'llash va keyin butun spec'ni qayta tekshirish kodi yo'q (T7.2, F7).
5. **`levelix.ai.hint`**: model tanlash maslahatlari (T7.3) yo'q; `done` kabi xato qiymatlarni oldini olish uchun validator tomonidan qiymat tekshiruvi (#3) ham kerak.
6. **`levelix.board`**ga `source_conversation_id` (`_inherit`), qoralama `state` va saqlash: F2 dan keyin.
7. **Bog'liqlik yo'nalishi saqlansin:** `levelix_board` `levelix_ai_*` ni import qilmaydi (hozir toza: `levelix_board` hech qaysi `levelix_ai*` ni import qilmaydi).
8. **Tarjima:** `lib/i18n.t` ni haqiqiy tarjimaga ulash (F9). AI ga yuboriladigan xato matnlari ingliz tilida qolishi foydali (model ingliz tilidagi `message`ni yaxshi tushunadi), foydalanuvchiga ko'rinadigan matn esa tarjima qilinadi: bu ikki yo'lni ajratish kerak bo'ladi.

---

## 8. Men o'qimagan yoki yuzaki ko'rgan narsalar

- **Test fayllari** (`tests/test_*.py`, `fixtures.py`): shu hujjat uchun qayta satrma-satr o'qilmadi; test nomlari va qatorlari ro'yxatlandi, to'plam ishga tushirildi (0 xato). Mazmuni men yozganim uchun xotiramdan keltirilgan.
- `lib/i18n.py`, `__init__.py` fayllari (jami 18 qator): to'liq ko'rdim, lekin ular juda qisqa.
- `scripts/` (seed, spike, compare, smoke, build_pdf, start_dev.sh) va `notes/`: faqat havola sifatida ishlatildi, tahlil qilinmadi.
- Eski `levelix_ai`: faqat `ai_tools.py:280-345` (aggregate) va `grep` natijalari. `providers.py` (F0 da o'qilgan), `ai_engine.py`, `panel.js`, `blocks.js` va boshqalar bu tahlilda o'qilmadi.
- Odoo yadrosining `formatted_read_group` va `fill_temporal` manbasi F0 da o'qilgan, bu tahlilda qayta o'qilmadi.
- **TEKSHIRILMAGAN:**
  - Nuqtali domain yo'li orqali o'qilmaydigan **maydon** (modelga emas, maydon guruhiga) filtr qo'yib ma'lumotni taxmin qilish mumkinmi. Faqat model darajasidagi ruxsat jonli sinalgan (3.2-C, `NO_ACCESS`). Tekshirish: o'qishga yopiq `groups=` li maydon bo'yicha domain bilan sinash.
  - Haqiqiy katta bazadagi tezlik (M-Dom nusxasi lokalda yo'q).
  - Brauzer tomoni: umuman yozilmagan.
  - Git tarixi: repozitoriy yo'q, shuning uchun "commitlar ketma-ketligi" so'rovi bajarilmadi. Ish tartibi `notes/F0_natijalar.md`, `notes/F1_natijalar.md` va `AI_DASHBOARD_PHASES.md` da yozilgan.
