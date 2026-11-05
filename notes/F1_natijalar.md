# F1 natijalari (2026-11-05)

Modul: `addons/levelix_board` (v19.0.1.0.0, LGPL-3), `aidash` bazasida o'rnatilgan.
Ishga tushirish: `scripts/run_tests.sh` (testlar), `scripts/f1_compare.py` (SQL bilan solishtirish), `scripts/smoke_engine.py` (qo'lda sinov).

## Nima qurildi

| Fayl | Vazifa |
|---|---|
| `lib/spec.py` | spec dataclass'lari, o'qish/yozish, `migrate`, 13 vidjet turi uchun shakl jadvali |
| `lib/validator.py` | semantik tekshiruv: 30 dan ortiq xato kodi, "Did you mean" tavsiyasi, ogohlantirishlar |
| `lib/filters.py` | nisbiy sanalar (`today -7d`, `today =1d -1m`), mahalliy kun semantikasi, davr chegaralari, hafta/oy/chorak boshlari |
| `lib/domain.py` | domain'ni o'qish (har doim shart bo'lgan qismlarni topish) |
| `lib/planner.py` | vidjet -> `Plan` (guruhlash, jamlama, tartib, limit, to'ldirish oralig'i) |
| `lib/runner.py` | yagona Odoo-ga bog'langan joy: `sudo` yo'q, savepoint, `statement_timeout` 8 s (keyin tiklanadi), xatolarni `BoardError` ga o'tkazish |
| `lib/frame.py` | natija -> Frame: yorliqlar, mahalliy sana, bo'sh kunlarni to'ldirish, top-N + "Others", `group_refs` |
| `lib/explain.py` | "Men nima qildim" qatorlari (kod yozadi, AI emas) |
| `models/env_catalog.py`, `models/engine.py` | yupqa Odoo adapteri: foydalanuvchi ko'ra oladigan maydonlar, valyuta, `_run_spec`, `_validate_spec` |

## Testlar

`scripts/run_tests.sh`: **105 ta test, 0 xato** (90 ta birlik + 15 ta integratsiya).

- Birlik (ma'lumotlar bazasiz): spec (11), filtrlar (18), validator (20), planner (13), frame (19), explain (9).
- Integratsiya (haqiqiy ORM): umumiy summa kompaniya valyutasida (UZS + boshqa valyuta, kurs bilan), kunlik qator foydalanuvchi vaqt zonasida (21:30 UTC buyurtma Toshkentda 11-mart), bo'shliqlarni to'ldirish, hafta va oy qutilari Odoo bilan mos, top-N + "Others" yig'indisi, `group_refs`, huquq (sotuvga ruxsatsiz foydalanuvchida `NO_ACCESS` va boshqa vidjetlar ishlaydi), ikkinchi kompaniya yozuv qoidasi, bir nechta valyuta ogohlantirishi, tushuntirish matni, nisbiy sana, `statement_timeout` tiklanishi.

## Mustaqil solishtirish (`scripts/f1_compare.py`)

Ijrochi natijalari `sale_order` / `sale_order_line` jadvallaridan to'g'ridan-to'g'ri SQL bilan hisoblangan qiymatlarga teng:

| Tekshiruv | Ijrochi | SQL | |
|---|---|---|---|
| Umumiy tushum | 84,348,935 | 84,348,935 | OK |
| Tasdiqlangan buyurtmalar | 158 | 158 | OK |
| Kunlik qator (30 kun), har kun | 30 qator | har kun teng | OK |
| Top 5 tovar (Coffee 348, Butter 292, Milk 285, Sunflower oil 277, Tea 260) | | | OK |
| "Others" (qolgan tovarlar) | 1,483 | 1,483 | OK |
| Sotuvchi: Administrator | 46,326,116 / 78 buyurtma | | OK |
| Sotuvchi: Sotuvchi | 38,022,819 / 80 buyurtma | | OK |

Shu sonlar Odoo'ning tayyor Sales dashboard'idagi (Revenue 84,349K, Orders 158) bilan ham mos.

## Yo'lda topilganlar

- Test yordamchisida bo'sh recordset `or` bilan ishlatilsa yolg'on (falsy) bo'ladi (`engine or default` standart muhitni tanlab qo'ygan edi). Tuzatildi: `if engine is None`.
- `tz` kontekstida `UTC` va `Asia/Tashkent` ni almashtirib ishlatish xavfsiz; kun chegarasi (21:30 UTC) to'g'ri.
- Hafta qutilari `get_lang(env).week_start` bilan Odoo guruhlashiga mos (integratsiya testi tasdiqladi).

## Qolgan / keyingi fazaga

- Haqiqiy katta bazada tezlik: F9.
- `compare` va `calc`: F6 (hozir `UNSUPPORTED`).
- `lx_*` ochiq RPC, saqlash, huquq modeli, drill serveri: F2.
- Tarjima (uz/ru): F9 (barcha matnlar `lib/i18n.t()` orqali o'tadi).
