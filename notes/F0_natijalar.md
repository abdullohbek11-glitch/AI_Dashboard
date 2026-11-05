# F0 natijalari (2026-11-05)

Skriptlar: `scripts/` papkasida. Hammasi `levelix-aidash` konteynerida, `aidash` bazasida ishlatilgan.

## 1. Muhit

| Nima | Qiymat |
|---|---|
| Konteyner | `levelix-aidash` (image `odoo-custom:19.0`), `scripts/start_dev.sh` bilan ishga tushadi |
| Manzil | http://localhost:8075 |
| Baza | `aidash` (faqat shu baza ko'rinadi, `dbfilter=^aidash$`) |
| Kod | `AI_Dashboard/addons` to'g'ridan-to'g'ri mount (rsync kerak emas) |
| O'rnatilgan | `sale_management`, `contacts` (demo yo'q) |
| Foydalanuvchilar | `admin` / `admin`, `sotuvchi` / `sotuvchi`, `omborchi` / `omborchi` |
| Boshqa konteynerlar | tegilmagan (`odoo-dev`, `odoo-dev-2` va ularning bazalari) |

Sinov ma'lumoti: `scripts/seed_test_data.py` (takrorlanadigan, ikkinchi ishga tushirishda eski ma'lumotni o'chirib qayta yaratadi).
Tarkibi: kompaniya valyutasi UZS, USD yoqilgan; ikkinchi kompaniya "Filial MChJ"; 12 tovar; 15 mijoz; 230 buyurtma (60 kun): 139 tasdiqlangan, 43 tasdiqlangan+qulflangan, 24 qoralama, 24 bekor qilingan; 21 tasi USD da.

Tekshirilgan (HTTP orqali): `admin` Sotuv hisobotini ko'radi, `sotuvchi` faqat o'z buyurtmalarini (172 qator, admin 424), `omborchi` da `AccessError`.

## 2. Spike natijalari

| # | Savol | Natija | Qaror |
|---|---|---|---|
| 1 | `fill_temporal` ishlaydimi | **Yo'q.** `datetime` maydonda foydalanuvchi tz bor bo'lsa chegaralar bilan `AttributeError: 'datetime.date' object has no attribute 'tzinfo'` (Odoo yadrosida xato). Chegarasiz (`True`) ishlaydi, lekin faqat mavjud sanalar oralig'ini to'ldiradi. `limit` bilan `ValueError` | Bo'sh kunlarni **o'zimiz** `lib/frame.py` da to'ldiramiz (davr chegaralari filtrdan ma'lum). `compare` uchun ham: ikki davr indeks bo'yicha tekislanadi |
| 2 | `__extra_domain` shakli | Sana: `['&', ('date','>=','2026-10-25 19:00:00'), ('date','<','2026-10-26 19:00:00')]` (UTC, Toshkent kuni 19:00 dan boshlanadi, ya'ni tz hisobga olingan). JSON ga o'tadi. Sana qismi: `('date.day_of_week','=',0.0)`, `('date.hour_number','=',14.0)` | `map` maydon nomini almashtiradi, nuqtali qismni saqlaydi (`date.x` → `date_order.x`) |
| 2b | Drill soni mos keladimi | **Ha.** `sale.report` kuniga `name:count_distinct` == `sale.order` soni: 28 kun, 0 farq. Hafta kuni (7) va soat (10) bo'yicha ham 0 farq | `map` yondashuvi ishlaydi |
| 3 | ECharts | Odoo 19 da yo'q, o'zimiz qo'shamiz. Maxsus yig'ma (line, bar, pie, heatmap, funnel, treemap, gauge, scatter, custom + asosiy komponentlar): **783 KB, gzip 275 KB** (to'liq kutubxona 1.1 MB). Litsenziya Apache-2.0 | `static/lib/echarts/` ga tayyor yig'ma fayl qo'yiladi (npm+esbuild), faqat kerak bo'lganda yuklanadi. NOTICE fayli kerak |
| 4 | Grid | Prototip F3/F7 ga qoldirildi: F3 da faqat joylashtirish (o'z CSS grid), surish F7 da. F7 boshida o'z `useGridDrag` yoki GridStack qarori qabul qilinadi | |
| 5 | `providers.py` | O'qildi (279 qator). Toza, ishlatishga yaroqli: neytral xabar formati, 3 provayder, SSE. Farqlar: hodisalar `text`, `tool_use`, `usage`, `stop`; vosita sxemasi kaliti `parameters`; xabar formati `{"role", "content":[blok]}`; **qayta urinish yo'q**; model `claude-sonnet-5-5` | Ko'chiramiz, qayta urinish va aniq xato matnlarini qo'shamiz (F4). Texnik hujjat 4.1 ga `stop` hodisasi qo'shilgan hisoblanadi |
| 6 | Katta bazada tezlik | M-Dom nusxasi lokalda yo'q (`mdom` bazasida 0 buyurtma). Sun'iy sinov: ~59 000 qator (`sale.report`), tranzaksiya oxirida orqaga qaytarildi. 30 kun kunlik: 83 ms; oylik: 112 ms; top-10 tovar: 91 ms; mijoz × oy: 119 ms; heatmap: 75 ms; sotuvchi huquqi bilan: 39 ms. Chiziqli o'ssa 1 mln qatorda ~1–2 s | `statement_timeout=8000` yetarli ko'rinadi. Haqiqiy M-Dom ma'lumotida F9 da qayta o'lchanadi |
| 7 | Formula parseri | `mdom/report_constructor/models/formula.py` (204 qator): toza, `ast` bilan oq ro'yxat, `+ - * /`, taqqoslash, `IF`, `ROUND`, `ABS`, `MIN`, `MAX`, `AND`, `OR`, `NOT`, tsikl aniqlash. Nolga bo'lish **0** beradi (texnik hujjatda `null` edi) | F6 da qayta ishlatamiz. Nolga bo'lishda 0 yoki bo'sh qiymat: F6 boshida so'raymiz |

## 3. Texnik hujjatga kiritilgan tuzatishlar

- Odoo 19 da `sale.order.state` qiymatlari: `draft`, `sent`, `sale`, `cancel`. **`done` yo'q** (qulflash `locked` maydonida). Hujjatdagi `["sale","done"]` hamma joyda `["sale"]` ga almashtirildi.
- `fill_gaps` Odoo ning `fill_temporal` iga tayanmaydi (6.3 / 5.1 ga mos).
- 15-bo'lim yangilandi: nima tasdiqlangan, nima qoldi.

## 4. Ogohlantirish

Docker diski (Colima, `/var/lib/postgresql/data`) **99% to'la**, bo'sh joy ~1 GB. Bu avval ham Postgres ni yiqitgan. Katta sinovlarni faqat tranzaksiya ichida va orqaga qaytarib o'tkazdim. Katta hajm kerak bo'lsa, avval joy bo'shatish kerak.

## 5. UI testi

Brauzer kengaytmasi ulanmagan edi, shuning uchun skrinshot olinmadi. Odoo ga HTTP orqali kirish va huquqlar tekshirildi (yuqorida). Brauzerda qo'lda ko'rish: http://localhost:8075, `admin` / `admin`, Sotuv → Hisobotlar.
