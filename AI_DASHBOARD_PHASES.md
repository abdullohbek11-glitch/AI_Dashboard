# AI Dashboard — Ish rejasi (fazalar)

> Holat: **reja v0.1**, 2026-11-05. Hamma ish shu papkada bajariladi: `/Users/latibov/Levelix/AI_Dashboard/`
> Asos: `AI_DASHBOARD_TZ.md` (qisqa TZ) va `AI_DASHBOARD_TEXNIK_TZ.md` (texnik hujjat). Bo'lim raqamlari (masalan «T6.7») texnik hujjatga ishora qiladi.

---

## 0. Ishlash tartibi

Har faza bir xil yo'ldan o'tadi:

```
1. Ishlar bajariladi
2. Avtomatik testlar yoziladi va yashil bo'ladi
3. UI testi (brauzerda, qadam-baqadam ro'yxat bo'yicha) o'tkaziladi
4. Siz qabul qilasiz ("faza yopildi")
5. Faqat shundan keyin keyingi faza boshlanadi
```

Qoidalar:

- **Faza yopilmaguncha keyingisiga o'tilmaydi.** Test o'tmasa, shu fazada tuzatiladi.
- Fazada yo'q ish qilinmaydi. Yangi g'oya chiqsa, "Keyinga" ro'yxatiga yoziladi (shu hujjat oxirida).
- Noaniq joyda kod yozishdan oldin sizdan so'raladi. Har fazaning boshida "Qaror kerak" bo'limi bor.
- Kod manbasi **ingliz tilida**. O'zbekcha va ruscha tarjima faqat oxirgi fazada (`i18n/*.po`).
- Har faza oxirida shu hujjatdagi **Holat jadvali** yangilanadi.

### Test turlari

| Belgi | Nima | Kim/qanday |
|---|---|---|
| **[A]** | Avtomatik: Python birlik va integratsiya testlari | `odoo --test-enable --http-port=8099` (band portga urilmaslik uchun) |
| **[U]** | UI testi: brauzerda ochib, bosib ko'rish | Men brauzer orqali o'tkazaman va skrinshot beraman. Siz ham o'zingiz ko'rasiz |
| **[T]** | Tour: avtomatik brauzer testi (Odoo `start_tour`) | Faqat muhim yo'llar uchun, agar muhitda headless Chrome bo'lsa |
| **[G]** | Oltin to'plam: haqiqiy AI bilan aniqlik o'lchovi | Alohida buyruq, pullik (T12) |

---

## 1. Holat jadvali

| Faza | Nomi | Hajmi | Holat |
|---|---|---|---|
| F0 | Tayyorgarlik va prototip tekshiruvi | S | ✅ yopildi 2026-11-05 (`notes/F0_natijalar.md`) |
| F1 | Spec va so'rov ijrochisi (faqat backend) | L | 🟦 qabul kutilmoqda (`notes/F1_natijalar.md`) |
| F2 | Dashboard modeli, saqlash, huquq, drill (backend) | M | 🟦 qabul kutilmoqda (`notes/F2_natijalar.md`) |
| F3 | Frontend: dizayn, 4 vidjet, drill jadvali | L | 🟦 qabul kutilmoqda (`notes/F3_natijalar.md`) |
| F4 | `levelix_ai_core`: AI poydevori va chat | L | ⬜ |
| F5 | `levelix_ai_board`: chatdan dashboard | L | ⬜ |
| F6 | Qolgan grafik turlari, filtrlar, taqqoslash | L | ⬜ |
| F7 | Tahrirlash, versiyalar, ulashish | M | ⬜ |
| F8 | Qo'shimcha funksiyalar (ogohlantirish, yuborish, TV …) | L | ⬜ |
| F9 | Yakun: tarjima, migratsiya, ishlash tezligi, image | M | ⬜ |

Hajmi: S = kichik, M = o'rta, L = katta. Muddat bahosi berilmagan: F0 natijasidan keyin aniqroq aytiladi.

Belgilar: ⬜ boshlanmagan · 🟨 jarayonda · 🟦 test kutilmoqda · ✅ yopildi

TZ dagi 5 bosqich bilan moslik: TZ 1-bosqich = **F1 + F2 + F3**, 2-bosqich = **F4 + F5**, 3-bosqich = **F6**, 4-bosqich = **F7**, 5-bosqich = **F8**.

---

## 2. Papka tuzilmasi

```
AI_Dashboard/
├── AI_DASHBOARD_TZ.md / .pdf              qisqa TZ
├── AI_DASHBOARD_TEXNIK_TZ.md / .pdf       texnik hujjat
├── AI_DASHBOARD_PHASES.md                 shu reja
├── addons/                                Odoo modullari (kod shu yerda)
│   ├── levelix_board/                     F1–F3, F6–F8
│   ├── levelix_ai_core/                   F4
│   └── levelix_ai_board/                  F5
├── golden/                                oltin to'plam (savollar + to'g'ri raqamlar) — F5 dan
├── scripts/                               test bazasini yaratish, sinash buyruqlari
└── notes/                                 F0 natijalari, qarorlar
```

Modul nomlari ishchi nom (T1). Yakuniy prefiks F0 da hal bo'ladi.

---

## F0. Tayyorgarlik va prototip tekshiruvi

**Maqsad:** ishni boshlashdan oldin texnik hujjatdagi "tekshirilmagan" masalalarni (T15) aniqlash va sinov muhitini tayyorlash. Bu fazada ishlab chiqarish kodi yozilmaydi.

### Qarorlar (qabul qilingan 2026-11-05)

1. Prefiks `levelix_`, litsenziya **LGPL-3**.
2. Sinov bazasi: yangi alohida baza `aidash`.
3. Sinov konteyneri: alohida `levelix-aidash`, `AI_Dashboard/addons` to'g'ridan-to'g'ri mount (http://localhost:8075).

### Ishlar

- [x] Sinov muhitini yig'ish (`scripts/start_dev.sh`, `scripts/odoo.conf`).
- [x] Sinov ma'lumotlari skripti (`scripts/seed_test_data.py`), takrorlanadigan: 230 buyurtma, UZS+USD, ikkinchi kompaniya, `sotuvchi` va `omborchi`.
- [x] Spike 1: `fill_temporal` ishlamaydi (tz bilan qulaydi) → bo'shliqlarni o'zimiz to'ldiramiz.
- [x] Spike 2: `__extra_domain` shakli aniqlandi, `map` bilan drill qatorlari soni hisobotga to'liq mos.
- [x] Spike 3: ECharts maxsus yig'ma 783 KB (gzip 275 KB).
- [x] Spike 4: grid qarori F3 (o'z CSS grid) va F7 (surish) ga bo'lindi.
- [x] `providers.py` o'qildi; `panel.js` F4 da o'qiladi.
- [x] Tezlik: ~59 000 qatorda 40–120 ms (haqiqiy M-Dom nusxasi lokalda yo'q, F9 da qayta o'lchanadi).
- [x] Formula parseri (`report_constructor/models/formula.py`) qayta ishlatishga yaroqli.
- [x] Aniqlangan xato: Odoo 19 da `state = done` yo'q. Hujjatlar tuzatildi.

### Test

- **[A]** Seed skripti ikki marta ishga tushsa ham baza buzilmaydi (takrorlanadigan).
- **[U]** Odoo'ga kirib, Sotuv → Hisobotlar da seed ma'lumotlari ko'rinadi; `sotuvchi` bilan kirganda faqat o'z buyurtmalari.

### Tugadi, agar

- `notes/F0_natijalar.md` yozilgan: har spike uchun "ishladi / ishlamadi / nima o'zgaradi". ✅
- Texnik hujjatdagi (T15) tekshirilmagan ro'yxat yopilgan yoki sabab bilan qoldirilgan. ✅
- Uchta qaror qabul qilingan. ✅
- Siz brauzerda sinov muhitini ko'rib, F0 ni qabul qildingiz. ✅

---

## F1. Spec va so'rov ijrochisi (faqat backend)

**Maqsad:** qo'lda yozilgan JSON spec'dan to'g'ri raqamlar olish. UI yo'q, AI yo'q.
**Modul:** `levelix_board` (birinchi qism). Mazmun: T5, T6.

### Ishlar

- [x] Modul skeleti, `lib/` papkasi (toza, `env` ga bog'lanmagan qismlar alohida).
- [x] `lib/spec.py`: dataclass'lar (`Spec`, `Widget`, `Data`, `Measure`, `Dimension`), o'qish/yozish, `migrate()` (T5.4).
- [x] `BoardError(code, path, message)` (T6.8).
- [x] `lib/validator.py`: sxema + semantik tekshiruv. Xato kodlari: `UNKNOWN_MODEL`, `UNKNOWN_FIELD`, `NO_ACCESS`, `NOT_AGGREGATABLE`, `BAD_GRANULARITY`, `BAD_SHAPE`, `NON_ADDITIVE_OTHERS`, `LEVEL_MISMATCH`, `SPEC_TOO_LARGE` (T6.7).
- [x] `lib/filters.py`: nisbiy sanalar (`today`, `today =1d`, `today -7d` …) → aniq sana, foydalanuvchi vaqt zonasida (T5.1).
- [x] `lib/planner.py`: vidjet → Plan.
- [x] `lib/runner.py`: Plan → `formatted_read_group`. `sudo` yo'q, `statement_timeout`, vidjet bo'yicha `savepoint` (T6.2).
- [x] `lib/frame.py`: natija → Frame (yorliqlar, "Belgilanmagan", `group_refs`) (T6.3).
- [x] Top-N va "Boshqalar" (T6.4). Valyuta tekshiruvi `MIXED_CURRENCY` (T6.6). Ogohlantirishlar: `STATE_FILTER_MISSING`, `SUSPICIOUS_DATE`, `TOO_MANY_GROUPS`.
- [x] `lib/explain.py`: spec → "Men nima qildim" qatorlari (T7.4). AI ga bog'liq emas, kod yozadi.
- [x] Kirish nuqtasi: `levelix.board.engine._run_spec(spec)` va `_validate_spec(spec)` (private, testlar va `odoo shell` uchun; ochiq RPC F2 da).

### Avtomatik test **[A]**

- `validator`: har xato kodi uchun kamida bitta yomon spec va bitta yaxshi spec (jadval asosida).
- `filters`: nisbiy sanalar, oy chegarasi, vaqt zonasi siljishi (5 soatlik tuzoq).
- `planner`, `frame` (soxta qatorlar bilan), `explain` (kutilgan matn).
- Integratsiya, haqiqiy ORM:
  - **Raqam to'g'riligi:** ijrochi jami == `sale.report` ning o'z natijasi (ikki valyutada ham).
  - **Huquq:** `omborchi` → `AccessError` → vidjet xatosi, boshqa vidjetlar ishlaydi.
  - **Kompaniya:** ikkinchi kompaniya buyurtmalari boshqa kompaniya foydalanuvchisiga ko'rinmaydi.
  - `others` bilan `avg` → `NON_ADDITIVE_OTHERS`.

### UI testi

Bu fazada UI yo'q. Qo'lda tekshiruv `odoo shell` orqali: T5.1 dagi spec'ni `run_spec` ga berib, natija jadvalini ekranga chiqarish va Odoo'ning Sotuv hisoboti bilan yonma-yon solishtirish. Men natijani sizga jadval ko'rinishida ko'rsataman.

### Natija (2026-11-05)

- **[A]** 105 ta test yashil (90 birlik + 15 integratsiya): `scripts/run_tests.sh`.
- Mustaqil SQL solishtirish `scripts/f1_compare.py`: hamma qiymat teng (jami, buyurtmalar, har kun, top-5, "Others", sotuvchilar). Odoo'ning tayyor Sales dashboard'idagi sonlar bilan ham mos.
- Batafsil: `notes/F1_natijalar.md`.

### Tugadi, agar

- Barcha **[A]** testlar yashil. ✅
- T5.1 dagi `area` va `bar` vidjetlari seed ma'lumotda to'g'ri Frame qaytaradi, jami `sale.report` bilan mos. ✅
- Frame ichida drill uchun `group_refs` bor. ✅
- Siz natijani ko'rib F1 ni qabul qildingiz. ⬜

---

## F2. Dashboard modeli, saqlash, huquq, drill (backend)

**Maqsad:** spec'ni saqlash, ro'yxat, huquqlar, drill-down serveri va RPC API.
**Modul:** `levelix_board` (ikkinchi qism). Mazmun: T3.1, T7.1, T9, T10.

### Ishlar

- [x] `levelix.board`, `levelix.board.version` (T3.1). Hajm chegarasi 256 KB / 30 vidjet.
- [x] Xavfsizlik: `ir.model.access`, yozuv qoidalari (egasi to'liq, boshqalar `share_mode` bo'yicha o'qiydi), guruh `board-manager`.
- [x] RPC: `lx_list`, `lx_load`, `lx_run`, `lx_save`, `lx_explain` (T9). Har birida argument va `has_access` tekshiruvi, `sudo` yo'q.
- [x] **Drill:** `lx_drill` (T2.3, T7.1): client domain yubormaydi, server `group_ref` dan qayta hosil qiladi; `map`; `DRILL_UNMAPPED`; `search_read` ≤ 80 qator + jami son + "Odoo'da ochish" uchun `act_window`.
- [x] Saqlashda dry-run: `on_click` ning `map` va ustunlari ham tekshiriladi.
- [x] Oddiy Odoo tomonidagi vaqtinchalik forma: `Dashboard` ro'yxati va formasi, `spec` ni JSON matn sifatida qo'lda kiritish (F3 gacha spec yozish uchun).
- [x] Har saqlashda yangi `levelix.board.version` qatori.

### Avtomatik test **[A]**

- Drill: bosilgan guruh qatorlari soni == `__count` (kun bo'yicha ham, mijoz bo'yicha ham).
- `map` noto'g'ri → `DRILL_UNMAPPED`. Xaritada yo'q maydon drill modelida ham yo'q → xato.
- Client yuborgan `group_ref` soxta bo'lsa rad etiladi.
- Huquq: egasi bo'lmagan va ulashilmagan dashboard'ni boshqa foydalanuvchi ocholmaydi; ulashilgan bo'lsa **o'z huquqi bilan** raqam ko'radi (`sotuvchi` va `admin` raqamlari farq qiladi).
- `lx_save` noto'g'ri spec'ni rad etadi, versiya hisoblagichi o'sadi.
- Kalitlar/argumentlar bo'sh yoki katta bo'lsa tushunarli xato.

### Natija (2026-11-05)

- **[A]** 155 ta test yashil (F1 dan 105 + F2 dan 50): `scripts/run_tests.sh`.
- **[U]** 1–2 qadamlar haqiqiy brauzerda (headless Chrome, `scripts/f2_ui_browser.py`): spec saqlandi, noto'g'ri spec "Invalid Operation" oynasida tushunarli xabar bilan rad etildi. 3–4 qadamlar JSON-RPC orqali (ikki foydalanuvchi). Menyu nomi "Levelix Boards".
- Batafsil: `notes/F2_natijalar.md`.

### UI testi **[U]** (Odoo oddiy interfeysida)

1. Yangi Dashboard yaratish, spec'ga T5.1 misolini kiritish → saqlanadi.
2. Noto'g'ri spec (mavjud bo'lmagan maydon) kiritish → saqlashda tushunarli xato xabari.
3. `sotuvchi` bilan kirish: egasi bo'lmagan dashboard ko'rinmaydi.
4. Ulashgandan keyin ko'rinadi.

### Tugadi, agar

- **[A]** yashil; drill qatorlari soni mos.
- UI testi 1–4 o'tdi (1–2 brauzerda, 3–4 RPC orqali) ✅.

---

## F3. Frontend: dizayn, 4 vidjet, drill jadvali

**Maqsad:** foydalanuvchi ko'radigan dashboard sahifasi. **TZ 1-bosqich qabul mezoni shu yerda tekshiriladi.**
**Modul:** `levelix_board` (frontend). Mazmun: T8, T5.2.

### Ishlar

- [x] Dizayn tizimi: `.lxb`, `--lxb-*` tokenlar (ranglar, shrift, bo'shliq, soya, burchak, harakat), yorug'/qorong'i rejim (T8.4).
- [x] `BoardPage`: to'liq ekranli client action, menyu, dashboard ro'yxati kartalari.
- [x] `core/`: `board_data` xizmati (`lx_load` → `lx_run`), `board_theme` xizmati.
- [x] `charts/`: `ChartAdapter` interfeysi, `ChartJsAdapter`, `EChartsAdapter` (lazy), registry (T8.3).
- [x] `widgets/`: vidjet reyestri + `kpi`, `area`/`line` (to'lqin), `bar`, `table` (jami qator) (T8.2). KPI ning ▲▼ ko'rsatkichi yozilgan va birlik-test qilingan, lekin `compare` ma'lumoti F6 da keladi (hozir server `compare` ni rad etadi).
- [x] Grid: 24 ustun, F0 dagi qaror bo'yicha (faqat joylashtirish; surish F7 da).
- [x] Holatlar: skeleton, bo'sh, xato (qayta urinish tugmasi), ruxsat yo'q. Bitta vidjet xatosi sahifani buzmaydi.
- [x] Ko'rinmaydigan vidjetlar `IntersectionObserver` bilan keyin yuklanadi (T2.2).
- [x] **Drill:** grafik nuqtasini bosish → yon panelda jadval (`side_table`), "Odoo'da ochish" tugmasi.
- [x] "Men nima qildim" komponenti (`explain/`), "Qanday hisoblangan" tugmasi.
- [x] Raqam formati `Intl.NumberFormat` (K / M / mlrd), valyuta `meta.currency` dan.
- [x] Mobil: grid bitta ustunga tushadi. Klaviatura bilan fokus.

### Avtomatik test

- **[A]** F2 dagi barcha testlar yashil qoladi.
- **[A]** JS birlik: adapter (frame → chart option), vidjet reyestri, grid hisobi.
- **[T]** Tour: "to'lqinda kunni bosish → yon jadval ochiladi" (agar muhitda mumkin bo'lsa).

### Natija (2026-11-05)

- **[A]** Python 159 ta test yashil (`scripts/run_tests.sh`), JS birlik 28 ta yashil (`scripts/run_js_tests.sh`).
- **[U]** 1–11 qadamlar haqiqiy brauzerda (headless Chrome), `scripts/f3_ui_browser.py`: 13 tekshiruv, hammasi o'tdi. Kutilgan raqamlar mustaqil SQL/ORM'dan. 12-qadam (dizayn) skrinshotlarni ko'rib baholandi.
- Skrinshotlar repoga saqlanmadi (siz PNG'larni o'chirishni so'ragansiz); skript ularni vaqtinchalik papkaga yozadi.
- **[T]** Odoo tour o'rniga Playwright ishlatildi (konteynerda Chrome yo'q).
- Batafsil: `notes/F3_natijalar.md`.

### UI testi **[U]**

| # | Qadam | Kutilgan natija |
|---|---|---|
| 1 | Menyudan Dashboard sahifasini ochish | to'liq ekran, skeleton keyin grafiklar |
| 2 | T5.1 misoli: to'lqinli sotuv + top 10 tovar | ikkala grafik chiziladi, jami raqam Sotuv hisobotiga teng |
| 3 | To'lqinda bitta kun nuqtasini bosish | **o'sha kunning sale order'lari** yon jadvalda; qatorlar soni nuqta qiymatiga mos |
| 4 | Ustun grafikda tovarni bosish | o'sha tovar sotilgan buyurtmalar |
| 5 | Yon paneldagi "Odoo'da ochish" | Sotuv buyurtmalari ro'yxati shu filtr bilan ochiladi |
| 6 | "Qanday hisoblangan" | oddiy tilda tushuntirish, texnik nom yo'q |
| 7 | Qorong'i/yorug' rejim almashtirish | ikkala kutubxona grafiklari ranglari bir xil temada |
| 8 | Brauzer oynasini toraytirish (mobil) | grid bir ustunga tushadi, o'qiladi |
| 9 | `sotuvchi` bilan kirish | raqamlar admin'nikidan farq qiladi, "Sizning huquqingiz bo'yicha" belgisi |
| 10 | Bitta vidjetning spec'ini buzish (mavjud bo'lmagan model) | faqat shu vidjetda xato, qolganlari ishlaydi |
| 11 | Ma'lumot yo'q davr tanlash | "Bu davrda ma'lumot yo'q" |
| 12 | Odoo yadro ranglari/shrift bilan solishtirish | dizayn Odoo'ga o'xshab qolmagan, o'z uslubimiz |

### Tugadi, agar

- UI testi 1–12 o'tdi ✅ (skrinshotlar saqlanmaydi).
- **TZ 1-bosqich qabul mezoni:** to'lqin grafigida kunni bosganda o'sha kunning sale order'lari ochiladi ✅ (2026-10-20: panelda 8 ta, ORM'da 8 ta).
- 5.1 dagi spec bilan jami `sale.report` ga teng ✅.

---

## F4. `levelix_ai_core`: AI poydevori va chat

**Maqsad:** dashboard'dan mustaqil, qayta ishlatiladigan AI qatlami. Bu fazada dashboard yaratilmaydi, faqat AI bilan suhbat va umumiy vositalar.
**Modul:** `levelix_ai_core`. Mazmun: T1.1, T3.2, T4.

### Qaror kerak

- API kalit: qaysi provayder bilan boshlaymiz (Anthropic / OpenAI / Gemini) va sinov uchun kalitni kim beradi. Kalit hech qayerda faylga yozilmaydi, faqat Odoo sozlamasida.

### Ishlar

- [ ] `levelix_ai` dan tanlab ko'chirish (T1.1 jadvali): `providers`, vositalar sikli, suhbat va jurnal modellari. Ovoz va `propose_change` ko'chirilmaydi.
- [ ] Provayder interfeysi `stream(system, messages, tools)`; uch amalga oshirish; timeout, tarmoq xatosida qayta urinish, tushunarli xato matnlari (T4.1).
- [ ] Vositalar reyestri: `_tool_defs()` / `_run()` `_inherit` orqali kengayadi (T4.2).
- [ ] Umumiy vositalar: `find_models` (hisobot modellari birinchi), `describe_model`, `search_records`, `aggregate`. Cheklovlari (T1.1 oxiri) yangi ijrochi bilan tuzatiladi.
- [ ] Maxfiylik rejimlari `aggregates` / `schema`: har vositada `to_ai(result, mode)` (T4.5).
- [ ] Modellar: `levelix.ai.conversation`, `levelix.ai.message`, `levelix.ai.tool.call` (T3.2). Kalit va maxfiy maydonlar jurnalga yozilmaydi.
- [ ] Sozlamalar sahifasi: provayder, kalit, model, timeout, maxfiylik, kunlik limit, **"Ulanishni tekshirish"** tugmasi. Faqat `base.group_system`.
- [ ] Tizim prompti bo'laklardan yig'iladi (core qoidalari + modul bo'laklari) (T4.6).
- [ ] Foydalanuvchi bo'yicha kunlik limit (T4.7).
- [ ] `AiChat` komponenti: oqim bilan javob (`bus`), blok turlari reyestri `levelix_ai_blocks` (T8.5).

### Avtomatik test **[A]**

- **Soxta provayder:** oldindan yozilgan vosita chaqiruvlari bilan sikl, `MAX_STEPS` chegarasi, xatoda to'xtash.
- `to_ai()`: `schema` rejimida natijada qiymatlar yo'q, `aggregates` rejimida jamlanma bor, `search_records` o'chgan.
- Kalit hech qanday jurnal yozuvida va klientga qaytadigan javobda yo'q (qidiruv testi).
- Limit oshganda tushunarli xabar.
- Oddiy foydalanuvchi sozlamalarni ocholmaydi.

### UI testi **[U]**

| # | Qadam | Kutilgan natija |
|---|---|---|
| 1 | Sozlamalarda kalitni kiritib "Ulanishni tekshirish" | muvaffaqiyat xabari; noto'g'ri kalitda tushunarli xato |
| 2 | Chat panelini ochib "Ushbu oy nechta sotuv buyurtmasi bor?" | javob oqim bilan, to'g'ri son (Odoo ro'yxati bilan solishtiriladi) |
| 3 | "Eng ko'p sotib olgan 5 mijoz" | jadval/ro'yxat, raqamlar to'g'ri |
| 4 | `omborchi` bilan kirib sotuvni so'rash | ruxsat yo'qligi aytiladi, boshqa foydalanuvchi ma'lumoti sizmaydi |
| 5 | Maxfiylikni `schema` ga o'tkazib 3-qadamni takrorlash | AI mijoz ismlarini ko'rmaydi; ism filtri uchun tanlash tugmasi chiqadi |
| 6 | Vosita chaqiruvlari jurnali | har chaqiruv ko'rinadi, kalit yo'q |
| 7 | Tarmoqni uzib so'rov yuborish | tushunarli xato, chat qotib qolmaydi |

### Tugadi, agar

- **[A]** yashil; UI testi 1–7 o'tdi.
- `levelix_ai_core` hech qayerda `levelix_board` ni import qilmaydi (bog'liqlik bir tomonga, T11).

---

## F5. `levelix_ai_board`: chatdan dashboard

**Maqsad:** savol yoziladi, tayyor dashboard qoralamasi chiqadi, xatoni AI o'zi tuzatadi, "Men nima qildim" bloki ko'rinadi.
**Modul:** `levelix_ai_board`. Mazmun: T2.1, T4.3, T4.4, T7.3, T7.4.

### Qaror kerak

- **20–30 ta real savol** (rahbar, omborchi, buxgalter, sotuvchi nimani so'raydi). Ularsiz oltin to'plam bo'sh qoladi. Tez boshlash uchun men dastlabki 30 tasini taklif qilaman, siz tuzatasiz.

### Ishlar

- [ ] Vositalar: `get_hints`, `preview_widget`, `build_dashboard`, `ask_user` (T4.3).
- [ ] Tuzatish sikli: strukturaviy xato `[{path, code, message}]` AI ga qaytadi, ko'pi bilan 3 urinish, keyin halol xabar (T4.4).
- [ ] Hint reyestri `levelix.ai.hint` + dastlabki yozuvlar: sotuv, xarid, faktura, kassa (T7.3). Ombor/qarzdorlik/CRM hint'lari faqat **tekshirilib** yoziladi.
- [ ] Prompt qoidalari: hisobot modeli afzal, `assumptions[]`, `uncertain[]` + tayyor patch, nisbiy sanalar, texnik nom ko'rsatilmaydi (T4.6).
- [ ] Chatda bloklar: `board_draft` (qoralama) va `board_explain` ("Men nima qildim"), tugmalar [Saqlash] [O'zgartir] (T8.5).
- [ ] `uncertain[]` tugmalari: bosilganda patch AI siz qo'llanadi.
- [ ] **"Noto'g'ri" tugmasi:** holat jurnalga yoziladi, keyin oltin to'plamga qo'shiladi.
- [ ] `golden/`: savollar + kutilgan model/o'lchov/filtr + **Odoo standart hisobotidan olingan to'g'ri raqam**. Ishga tushirish buyrug'i (T12).
- [ ] `levelix.board` ga `source_conversation_id` (`_inherit`).

### Avtomatik test **[A]**

- Soxta provayder: noto'g'ri spec → xato → tuzatilgan spec → qoralama (sikl ishlaydi); 3 urinishdan keyin halol xabar.
- `build_dashboard` biznes ma'lumotni o'zgartirmaydi (faqat o'z dashboard'ini yaratadi).
- Prompt injection: yozuv nomida "boshqa ko'rsatma" bo'lganda xatti-harakat o'zgarmaydi.
- `ExplainBuilder`: spec uchun kutilgan matn; texnik nom chiqmaydi; ≤ 5 qator + "Batafsil".

### Oltin to'plam **[G]**

- Birinchi o'lchov: aniqlik foizi, kategoriya bo'yicha (sotuv, ombor, qarz …). Natija `notes/F5_golden_v1.md` ga.
- Maqsad raqami hozir qo'yilmaydi: birinchi o'lchovdan keyin birga belgilaymiz.

### UI testi **[U]**

| # | Qadam | Kutilgan natija |
|---|---|---|
| 1 | Chatga: "Shu oy sotuvni kunlar bo'yicha va top 10 tovarni ko'rsat" | qoralama dashboard chatda ko'rinadi |
| 2 | "Men nima qildim" bloki | oddiy tilda: nimani sanadi, qaysi sana, qaysi holatlar; texnik nom yo'q |
| 3 | [Saqlash] | dashboard ro'yxatda paydo bo'ladi, ochilganda AI ishlamaydi (tez) |
| 4 | Saqlangan dashboard'da to'lqinda kunni bosish | o'sha kunning buyurtmalari (F3 funksiyasi AI yaratganda ham ishlaydi) |
| 5 | Bekor qilingan buyurtmalarni ham sanaydigan savol berib, ogohlantirishni kuzatish | `STATE_FILTER_MISSING` ogohlantirishi blokda ko'rinadi |
| 6 | "ishonchim past" tugmasini bosish (masalan "yetkazilgan bo'yicha") | dashboard o'zgaradi, raqamlar o'zgaradi |
| 7 | Mavjud bo'lmagan narsani so'rash ("kayfiyat bo'yicha sotuv") | AI halol aytadi, o'ylab topilgan dashboard chiqmaydi |
| 8 | Ikki foydalanuvchi (admin va `sotuvchi`) bir savolni berishi | har biri o'z huquqidagi raqamni ko'radi |
| 9 | "Noto'g'ri" tugmasi | holat jurnalga tushadi |
| 10 | Qoralamani saqlamasdan chiqib ketish | qoralama yo'qolmaydi, keyin davom ettirsa bo'ladi |

### Tugadi, agar

- **[A]** yashil; UI testi 1–10 o'tdi.
- Oltin to'plamning birinchi natijasi o'lchangan va `notes/` da turibdi.
- **TZ 2-bosqich qabul mezoni:** savol yozilsa qoralama chiqadi, xato bo'lsa o'zi tuzatadi.

---

## F6. Qolgan grafik turlari, filtrlar, taqqoslash

**Maqsad:** ko'rinishlar to'liq to'plami va filtrlar.
**Modul:** `levelix_board`. Mazmun: T5.1–T5.3, T6.5.

### Ishlar

- [ ] Vidjetlar: `pie`, `heatmap` (hafta kuni × soat), `funnel`, `treemap`, `gauge`, `waterfall`, `scatter`, `combo` (T5.2). Har biri: papka + reyestr yozuvi + Python tomonida shakl qoidasi (`BAD_SHAPE`).
- [ ] Doira 8 tadan ko'p bo'lak bo'lsa avtomatik top 7 + "Boshqalar".
- [ ] Global filtrlar: `date_range`, `company`, `select`; `applies_to` xaritasi (T5.3).
- [ ] Cross-filter: bitta grafikni bosish qolganlarini filtrlaydi (vaqtinchalik, saqlanmaydi).
- [ ] `compare`: `previous_period` / `previous_year` (F0 spike natijasiga ko'ra).
- [ ] Hisoblangan o'lchovlar `calc` (o'z parser, `eval` yo'q) (T6.5).
- [ ] `others` va `having` to'liq.
- [ ] `fill_gaps`.
- [ ] AI uchun: yangi turlar prompt va validator'ga qo'shiladi, `levelix_ai_board` yangilanadi.

### Avtomatik test **[A]**

- Har tur uchun: yaxshi/yomon shakl (`BAD_SHAPE`).
- `calc`: nolga bo'lish → `null`; `eval` kabi narsa ishlatilmaydi (zararli satr rad etiladi).
- `compare`: siljitilgan davr to'g'ri hisoblanadi (oy chegarasi, kabisa yili).
- Filtr `applies_to` da yo'q modelga tegmaydi.
- Doira: 12 bo'lak → 7 + Boshqalar, yig'indi saqlanadi.

### UI testi **[U]**

| # | Qadam | Kutilgan natija |
|---|---|---|
| 1 | Hamma 12 turni bitta test dashboard'da ko'rsatish | har biri chiziladi, o'qiladi, qorong'i rejimda ham |
| 2 | Davr filtrini o'zgartirish | tegishli hamma vidjet yangilanadi |
| 3 | Tovar ustunini bosish (cross-filter) | qolgan grafiklar shu tovarga filtrlanadi; qayta bosilganda bekor |
| 4 | KPI da "oldingi davr bilan" ▲▼ | foiz o'zgarishi to'g'ri (qo'lda hisoblab solishtiriladi) |
| 5 | Heatmap'da katakni bosish | o'sha kun/soat buyurtmalari (drill) |
| 6 | Hisoblangan ko'rsatkich (marja) | qiymat to'g'ri |
| 7 | Doira 12 bo'lakli ma'lumotda | 7 + Boshqalar |
| 8 | AI orqali: "Hafta kunlari va soatlar bo'yicha buyurtmalar" | heatmap qoralamasi chiqadi |

### Tugadi, agar

- UI testi o'tdi; TZ 3-bosqich mezoni: **10 xil tur ishlaydi**, taqqoslash va filtrlar tekshirilgan.
- Oltin to'plam qayta ishga tushirildi, regressiya yo'q.

---

## F7. Tahrirlash, versiyalar, ulashish

**Maqsad:** dashboard'ni qo'lda va suhbat orqali o'zgartirish, orqaga qaytarish, boshqalarga ulashish.
**Modul:** `levelix_board`, `levelix_ai_board`. Mazmun: T3.1, T7.2.

### Qaror kerak

- Ulashish darajalari (TZ ochiq masala 3): faqat o'zi / guruh / butun kompaniya. Ochiq havola v1 da **yo'q**.

### Ishlar

- [ ] Qo'lda tahrirlash: vidjetni surish, o'lcham o'zgartirish, o'chirish, sarlavha, turni almashtirish.
- [ ] Vidjet qo'shish (turini tanlab, maydon tanlash oynasi, AI siz).
- [ ] `update_dashboard` va `lx_apply_patch`: cheklangan patch (`add`/`replace`/`remove`, faqat `/widgets`, `/filters`, `/title`), vidjet `id` lari saqlanadi (T7.2).
- [ ] Suhbat orqali tahrirlash: "ustunli qil", "oxirgi 3 oy", "qarzdorlarni ham qo'sh".
- [ ] Versiya tarixi, `lx_restore`, versiyalarni solishtirish ro'yxati.
- [ ] Ulashish: `lx_share`, ko'ruvchi o'z huquqi bilan ko'radi.
- [ ] Nusxalash (clone), arxivlash.
- [ ] Eksport: PNG (keyingi fazada PDF/XLSX).

### Avtomatik test **[A]**

- Patch: id lar saqlanadi, noto'g'ri yo'l/amal rad etiladi, patch'dan keyin butun spec qayta tekshiriladi.
- Versiya: har saqlashda yangi qator; qaytarishda yangi versiya (tarix o'chmaydi).
- Ulashish: guruh a'zosi ko'radi, tashqi odam ko'rmaydi, ko'ruvchi tahrir qila olmaydi.
- Bir vaqtda tahrir: ikkinchi saqlash eskirgan versiya haqida ogohlantiradi (ustiga yozib yubormaydi).

### UI testi **[U]**

| # | Qadam | Kutilgan natija |
|---|---|---|
| 1 | Vidjetni sichqoncha bilan surish va o'lchamini o'zgartirish | joyi saqlanadi, sahifa yangilanganda ham |
| 2 | Chatga "tovarlar grafigini ustunli qil" | faqat shu vidjet turi o'zgaradi, qolgani joyida |
| 3 | "Oxirgi 3 oy" | davr o'zgaradi, joylashuv saqlanadi |
| 4 | Versiya tarixidan oldingisini tiklash | dashboard avvalgi holatga qaytadi |
| 5 | Dashboard'ni kompaniyaga ulashish, `sotuvchi` bilan kirish | ko'radi, o'zining raqami bilan; tahrir tugmalari yo'q |
| 6 | Nusxa olish | mustaqil nusxa, asl o'zgarmaydi |
| 7 | Ikki oynada bir vaqtda tahrirlash | ikkinchi saqlashda ogohlantirish |
| 8 | PNG eksport | rasm ochiladi, grafiklar to'liq |

### Tugadi, agar

- UI testi o'tdi; TZ 4-bosqich mezoni: **"ustunli qil" ishlaydi, orqaga qaytarish mumkin, ulashishda ko'ruvchi o'z huquqi bilan ko'radi**.

---

## F8. Qo'shimcha funksiyalar

**Maqsad:** TZ 11-bo'limdagi foydali qo'shimchalar. Har biri alohida kichik qadam, har biri alohida test qilinadi va alohida yopiladi. Tartibni siz belgilaysiz.

| # | Funksiya | Nima | Test |
|---|---|---|---|
| F8.1 | Ogohlantirish (maqsad va chegara) | KPI chegaradan o'tsa xabar (`levelix.board.alert`) | **[A]** shart bajarilganda bir marta xabar, takrorlanmaydi · **[U]** chegarani o'tkazib xabar kelishini ko'rish |
| F8.2 | Rejali yuborish | har kuni PNG/PDF Telegram yoki emailga (`levelix.board.schedule`, cron) | **[A]** cron belgilangan vaqtda ishlaydi, xato yuborishni to'xtatmaydi · **[U]** haqiqiy xabar keladi |
| F8.3 | TV rejimi | to'liq ekran, avtomatik yangilanish, dashboard'lar almashishi | **[U]** 10 daqiqa ochiq qoldirib, yangilanishni kuzatish |
| F8.4 | "Nega tushdi?" | AI ikki davrni solishtirib sababni tushuntiradi | **[G]** kutilgan sabab ma'lum bo'lgan sun'iy ma'lumotda · **[U]** tushuntirish drill bilan tasdiqlanadi |
| F8.5 | Shablonlar galereyasi | Sotuv, Ombor, Buxgalteriya tayyor dashboard'lari | **[A]** har shablon validatordan o'tadi · **[U]** bitta bosish bilan nusxa |
| F8.6 | Eksport | PDF, XLSX, CSV | **[A]** fayl raqamlari ekrandagi bilan teng · **[U]** fayl ochiladi |
| F8.7 | Izohlar | grafik nuqtasiga eslatma | **[A]** huquq · **[U]** izoh nuqtada ko'rinadi |
| F8.8 | Ombor/qarzdorlik/CRM hint'lari | tekshirilgan hisobot modellari bilan | **[G]** yangi savollar oltin to'plamda |

**Tugadi, agar:** tanlangan har bir qadam o'zining testidan o'tdi. TZ 5-bosqich mezoni: **ertalab rejali yuborish ishlaydi, TV rejimi avtomatik yangilanadi**.

---

## F9. Yakun

**Maqsad:** ishlab chiqarishga tayyorlash.

### Ishlar

- [ ] **Tarjima:** `i18n/*.pot`, `uz.po`, `ru.po` (barcha modullar). Faqat shu fazada.
- [ ] **Migratsiya:** `levelix_ai` dagi eski dashboard elementlari (`query`) → yangi vidjet spec'i; eski modul bilan birga yashash yoki almashtirish qarori.
- [ ] **Tezlik:** katta bazada (M-Dom nusxasi) barcha tipik vidjetlarni o'lchash; sekinlari uchun kesh (T6.2) yoki limit.
- [ ] **Xavfsizlik ko'rigi:** T10 jadvalidagi har xavf uchun test mavjudligini tekshirish; XSS (sarlavha, tooltip), kalit sizishi, kompaniya aralashishi.
- [ ] **Oltin to'plam** yakuniy o'lchovi va natija hisoboti.
- [ ] **Hujjat:** `README` (o'rnatish, sozlash, yangi vidjet qo'shish, yangi AI vositasi qo'shish), foydalanuvchi qo'llanmasi (qisqa).
- [ ] **Image:** modullarni Levelix image'ga qo'shish, litsenziya sarlavhalari, manifest.
- [ ] Texnik hujjat (T15) yangilanadi: nima tekshirilgan.

### Test

- **[A]** to'liq to'plam, nol uzilish.
- **[U]** yangi (bo'sh) bazada Levelix image'dan o'rnatish → seed → butun yo'l (savol → dashboard → drill → ulashish) ishlaydi; `uz` va `ru` tillarda interfeys to'g'ri.
- **[G]** yakuniy aniqlik hisoboti.

---

## Keyinga (reja tashqarisi)

Faqat g'oya sifatida saqlanadi, hozir qilinmaydi:

- Sankey va xarita turlari.
- Ochiq havola (alohida xavfsizlik ko'rigidan keyin).
- Boshqa AI funksiyalar: hujjat tayyorlash, kontakt qidirish, o'zgartirish taklif qilish (`levelix_ai_actions`).
- M-Dom uchun maxsus hint'lar va shablonlar.

---

## Ochiq savollar (faza boshlanishidan oldin)

| Qachon | Savol |
|---|---|
| F0 oldidan | ~~Modul prefiksi va litsenziya~~ hal bo'ldi: `levelix_`, LGPL-3 |
| F0 oldidan | ~~Sinov bazasi va konteyner~~ hal bo'ldi: `aidash`, `levelix-aidash` |
| F4 oldidan | AI provayder va sinov API kaliti |
| F5 oldidan | 20–30 ta real savol (men dastlabki ro'yxatni taklif qilaman) |
| F7 oldidan | Ulashish darajalari |
| F8 oldidan | Qo'shimcha funksiyalar tartibi |
