# F3 natijalari (2026-11-05)

## Nima qilindi
- Dizayn tizimi `.lxb` (`scss/board.scss`): `--lxb-*` tokenlar, yorug'/qorong'i rejim, Okabe-Ito asosidagi 8 ta kategoriya rangi, mobil, `prefers-reduced-motion`.
- Toza JS (`static/src/lib`): raqam formati (K/M/mlrd tilga qarab), grid hisobi, frame → Chart.js/ECharts sozlamalari, so'rovlarni birlashtirish, tema o'qish.
- Xizmatlar: `levelix_board.data` (barcha RPC shu yerda), `levelix_board.theme`.
- Adapterlar: `ChartJsAdapter`, `EChartsAdapter` (lazy, o'zimiz yig'gan 663 KB bundle), reyestr.
- Vidjetlar: `kpi`, `line`/`area`, `bar`, `table` (jami qatori) + umumiy "karta" (skeleton, bo'sh, xato, ruxsat yo'q, tushuntirish).
- Sahifa `BoardPage`: dashboard kartalari ro'yxati, dashboard, drill yon paneli, "How it was calculated".
- Backend: `table` uchun `meta.totals`; "Others" kaliti `__others__`; formada "Open dashboard" tugmasi; menyu "Levelix Boards".
- Demo: `scripts/seed_boards.py` ("Sales overview" dashboard'i, test foydalanuvchi `boshliq`/`boshliq`).

## Sinov
- `scripts/run_tests.sh` 159, `scripts/run_js_tests.sh` 28, `scripts/f3_ui_browser.py` 13 tekshiruv. Hammasi yashil.
- Brauzer testida kutilgan sonlar mustaqil: SQL (daromad 84 348 935.00, 158 buyurtma; sotuvchi 38 022 819.00, 80), ORM `search_count` (kun va tovar bo'yicha drill).
- TZ 1-bosqich mezoni: 2026-10-20 nuqtasi bosilganda panelda 8 buyurtma, ORM'da ham 8, hammasi o'sha mahalliy kun.

## Brauzer testi topgan xatolar (Python testlari ko'rsatmagan)
- libsass `clamp()`/`min()` ni hisoblashga urinib kompilyatsiyani buzdi (butun baza uchun "Style error").
- OWL shablonida `JSON` global'i yo'q, `t-on-keydown.enter` modifikatori yo'q.
- Qorong'i rejimda sarlavha ko'rinmasdi (Odoo `h1` rangi meros bo'lgan).
- Gorizontal grafikda o'q yozuvlari yopishgan; mahsulot nomlari tashlab ketilgan.
- Yangilangan menyu yozuvining eski `action` maydoni tozalanmagan.

## Qoldi / izoh
- KPI ▲▼ (taqqoslash) chizilishi tayyor, ma'lumot F6 da (server hozir `compare` ni rad etadi).
- Klaviatura: kartalar fokuslanadi, jadval qatori Enter/Space bilan ochiladi, grafikning matnli jadvali ekran o'qigichlar uchun bor. Avtomatik testda tekshirilmagan.
- Domain qiymatlarini tekshirish (F1 topilmasi) hali tuzatilmagan: noto'g'ri selection qiymati jim 0 qator beradi.
- JS o'zgargach eski asset keshi qolsa: `ir.attachment` dan `/web/assets/%` ni o'chirish va konteynerni qayta ishga tushirish.
