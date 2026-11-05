# F4 natijalari (2026-11-05)

## Nima qilindi: `levelix_ai_core`
- **Provayderlar** (`providers/`): Anthropic, OpenAI, Gemini, bitta interfeys `stream(system, messages, tools)`. Timeout (sozlanadi), faqat tarmoq xatosida qayta urinish (2 marta), tushunarli xato matnlari (401, 404 model, 429, 5xx), kalit hech qachon xabarga tushmaydi (`redact`), `check()` ulanish sinovi uchun.
- **Vositalar reyestri** (`levelix.ai.tools`): `_tool_defs()` / `_run()` / `_to_ai()`, `_inherit` bilan kengayadi. Faqat ro'yxatdagi (va maxfiylik rejimi ruxsat bergan) vosita ishlaydi. Vositalar: `find_models` (hisobot modellari birinchi), `describe_model` (faqat saqlanadigan maydonlar, "summable" belgisi), `search_records`, `aggregate`, `pick_record`, `ask_user`.
- **`aggregate` tuzatilgan cheklovlar bilan:** ≤2 guruh, ≤4 o'lchov, 200 guruh; `sum` faqat Odoo `aggregator=sum` deb e'lon qilgan maydonga; guruhlash maydon tekshiruvi; sana bez vaqt = butun mahalliy kun; valyuta aralashsa ogohlantirish va birliksiz.
- **Maxfiylik rejimlari** (`lib/privacy.py`): `aggregates` (standart) va `schema`. `schema` da vendor faqat tuzilmani ko'radi (guruhlar/ustunlar soni), `search_records` taklif etilmaydi va ishlamaydi, kontekstda foydalanuvchi/kompaniya nomi ham yo'q, tanlov tugmasi nomni emas id'ni yuboradi. Foydalanuvchi ekranida natija to'liq.
- **Modellar:** `levelix.ai.conversation/message/tool.call`. Foydalanuvchi xabar va jurnalni **faqat o'qiydi**; yozuvlarni server yozadi (`sudo`, faqat bookkeeping). Administrator hammasini o'qiydi (audit), tahrirlay olmaydi.
- **Sozlamalar:** provayder, kalit (**yozish-faqat**: formaga qaytmaydi, "A key is saved" belgisi, saqlangach vaqtinchalik qatordan ham tozalanadi), model, manzil (proksi), timeout, temperature, maxfiylik, kunlik savol va token limiti, "Assistant for all internal users", "Test Connection", "Remove Saved Key". Faqat `base.group_system`.
- **Dvigatel:** MAX_STEPS=8, tarix (10 navbat), bus bilan oqim, fon oqimi, vosita uchun savepoint + 8 s timeout, har vosita chaqiruvi jurnalga (maxfiylik rejimi bilan).
- **Prompt** (`lib/prompt.py`): core qoidalari + modullar qo'shadigan bo'laklar (`_prompt_pieces`).
- **Frontend:** `AiChat` (qayta ishlatiladigan), xizmat `levelix_ai.chat`, bloklar reyestri `levelix_ai_blocks` (`table`, `kpi`, `chart`, `choices`), xavfsiz markdown, alohida sahifa (menyu "Levelix AI"). Stil `--lxai-*`, board sahifasida `--lxb-*` tokenlarini avtomatik oladi.
- Ikkala modulga ilova ikonkasi.

## Sinov
- Python `levelix_ai_core`: **71 test** (`scripts/run_ai_tests.sh`); `levelix_board`: 170; JS: **35** (`scripts/run_js_tests.sh`).
- **Soxta vendor** (`tests/fake_ai.py`) uchala provayderning haqiqiy simli formatida gaplashadi va so'rovni vendor kabi o'qiydi (rollar, vosita natijalari, vosita e'lonlari, auth sarlavhasi). Shu bilan: uchala provayder uchun matn oqimi, vosita chaqiruvi va natijasi, token hisobi, xatolar, qayta urinish, kalit sizmasligi sinaldi.
- **Brauzer** `scripts/f4_ui_browser.py`: **21 tekshiruv**, hammasi o'tdi. Reja bo'yicha 1–7 qadamlar (uchala provayder uchun: sozlamalar, kalit qaytmasligi, ulanish sinovi, "ushbu oy nechta buyurtma" = Odoo bilan teng, top-5 mijoz = Odoo guruhlashi bilan teng, huquqsiz foydalanuvchi, schema rejimi, jurnal, tarmoq uzilishi) + markdown/XSS, sekin javob, suhbatni qayta ochish/arxivlash, sozlanmagan holat, kunlik limit, konsolda xato yo'qligi.
- **Haqiqiy kalit bilan sinovlar `DEFERRED.md` da** (siz kalitni kiritganingizdan keyin).

## Topilmalar va qarorlar
- **`levelix_ai` (eski modul) bilan birga o'rnatib bo'lmaydi:** bir xil model nomlari (`levelix.ai.conversation` va h.k.) va sozlama prefiksi `levelix_ai.`. TZ eski modulni almashtirishni ko'zda tutadi (F9: migratsiya). Dev bazada eski modul yo'q.
- **Eski moduldagi kamchilik tuzatildi:** kalit sozlamalar formasiga to'liq qaytardi; endi qaytmaydi.
- **`aggregate` core'da, board'da emas:** core dashboard'ni bilmasligi kerak. F5 da `levelix_ai_board` uni board ijrochisiga yo'naltiradi. Sana mantig'i (`lib/dates.py`) `levelix_board.lib.filters` dan ~60 qator takror; F9 da umumiy joyga chiqarish mumkin.
- `ask_user` TZ da `ai_board` ro'yxatida edi; UI testi 5 ("tanlash tugmasi") uchun core'ga ko'chirildi, `pick_record` qo'shildi (schema rejimida ism tanlash).
- Testlarda `-standard` tegi: Odoo test himoyasi `(connect, read)` timeout juftligini bilmaydi; testlar faqat 127.0.0.1 ga ulanadi.
- Dev: boshqa jarayondan (shell) sozlama o'zgartirilsa, ishlayotgan server keshi baʼzi kalitlar uchun yangilanmaydi. Test skripti sozlamani serverning o'z RPC si orqali o'zgartiradi. Haqiqiy hayotda sozlama Sozlamalar sahifasi orqali saqlanadi (shu jarayon).
- Odoo `res.config.settings` formasida tugma bosishdan oldin "Save" so'raladi: "Test Connection" saqlangan kalit bilan ishlaydi.

## Qoldi
- `search_records` natijasi `MAX_ROWS=50` va `RESULT_CHARS=12000` bilan cheklangan; katta natija modelga kesilib boradi.
- Dark rejim chat uchun alohida yo'q: `--lxb-*` mavjud bo'lsa (board sahifasida) o'shandan oladi.
- Ovoz, `propose_change` ko'chirilmadi (TZ bo'yicha).
- Suhbat tarixi saqlash muddati va tozalash (retention) belgilanmagan: xabarlarda vosita natijalari (ma'lumot) saqlanadi. F9 da qaror kerak.
