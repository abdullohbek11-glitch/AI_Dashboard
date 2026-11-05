# F2 natijalari (2026-11-05)

## Nima qilindi
- Modellar `levelix.board` va `levelix.board.version`; har spec o'zgarishi saqlovchi huquqi bilan tekshiriladi va versiya yozadi.
- Xavfsizlik: guruh `Board manager`, `ir.model.access.csv`, yozuv qoidalari (kompaniya, ko'rish, egasi yozadi, tarix).
- RPC: `lx_list`, `lx_load`, `lx_run`, `lx_explain`, `lx_drill`, `lx_save`.
- Drill: `lib/drill.py` (toza), `Runner.fetch`, `engine._drill_spec`. Saqlashda dry-run validator ichida.
- Vaqtinchalik forma: menyu "Dashboards", ro'yxat, forma (spec JSON matn, ace muharriri), tarix sahifasi.

## F1 topilmalaridan tuzatilganlari (PHASE1_ANALYSIS.md 7.3)
- Kutilmagan xato butun `_run_spec` ni yiqitmasin: vidjet ichida `INTERNAL` ga aylanadi (test bor).
- `_resolve_names` `AccessError` bersa, "#id" ko'rsatiladi.
- `widget_ids` dagi noma'lum id jim tashlanmaydi: `UNKNOWN_WIDGET`.
- "Boshqalar" kaliti endi `["__others__"]` (avval `[None]` edi, "Belgilanmagan" bilan aralashardi).
- **Tuzatilmagan:** domain qiymatlarini tekshirish (selection'da noto'g'ri qiymat jim 0 qator beradi). F5 dan oldin qoladi.

## Sinov
- `scripts/run_tests.sh`: 155 test, 0 xato. Yangilari: `test_board.py` (yozuv, ko'rinish, huquq, RPC argumentlari), `test_drill.py` (sozlama, nomlarni almashtirish, guruhni topish), `test_drill_engine.py` (haqiqiy ORM).
- Drill soni: har kun va har mijoz bo'yicha ochilgan yozuvlar soni == guruh qiymati; `sale.report` → `sale.order` (`count_distinct`) ham teng.
- Huquq: `sotuvchi` faqat o'z buyurtmasini ko'radi (admin 3, sotuvchi 1); oddiy ichki foydalanuvchi vidjetda `NO_ACCESS` oladi, boshqa vidjet ishlaydi.
- UI 1–4: `scratchpad/f2_ui_rpc.py` (JSON-RPC, `sotuvchi` egasi, `omborchi` ko'ruvchi). Natija: yaratildi (v1); noto'g'ri maydon "Did you mean 'price_subtotal'?" xabari bilan rad etildi; buzuq JSON rad etildi; versiya o'zgarmadi; ulashishgacha ko'rinmadi, ulashgandan keyin ko'rindi, ko'ruvchi o'z huquqi bilan (`NO_ACCESS`) xato oldi va tahrirlay olmadi.

## Qaror/izoh
- Spec saqlanganda tekshiruv saqlovchi huquqi bilan bo'lgani uchun, sotuvni o'qiy olmaydigan menejer sotuv spec'ini saqlay olmaydi. Xavfsizlik uchun ataylab.
- Server kodi o'zgargach konteynerni qayta ishga tushirish kerak (`docker restart levelix-aidash`).
- Brauzer kengaytmasi ulanmagan, shuning uchun UI testi `scripts/f2_ui_browser.py` bilan o'tkazildi (Playwright + Mac'dagi Chrome, headless). Skrinshotlar repoga saqlanmaydi (skript ularni vaqtinchalik papkaga yozadi).

## Brauzer testida topilgan xatolar
- Menyu nomi "Dashboards" Odoo'ning o'z spreadsheet-dashboard ilovasi bilan to'qnashdi: **"Levelix Boards"** deb o'zgartirildi.
- `BoardError`/`SpecInvalid` brauzerda umumiy "Oops, something went wrong" oynasini berardi (web klient xato oynasini sinf nomi bo'yicha tanlaydi). `static/src/error_dialogs.js` ularni ogohlantirish oynasiga ulaydi. RPC testlari buni ko'rsatmagan edi.
