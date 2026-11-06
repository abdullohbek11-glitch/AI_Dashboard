# DEFERRED: tashqi resurs kerak bo'lgan, hali bajarilmagan tekshiruvlar

Bu ishlar **haqiqiy AI kaliti** kerak qiladi. Qolgan hamma narsa soxta vendor (`addons/levelix_ai_core/tests/fake_ai.py`) bilan tekshirilgan. Kalitni **siz** Odoo Sozlamalariga kiritasiz (Levelix AI → Settings → provayderni tanlab, kalitni qo'yib, "Save", so'ng "Test Connection"). Men kalitni o'zim kirita olmayman.

## F4: haqiqiy kalit bilan

Avval soxta vendorni bazadan olib tashlang: `docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/unseed_ai.py` (qaytarish: `scripts/seed_ai.py`). Keyin Sozlamalarda kalitni kiriting. Shundan keyin shu tartibda tekshiramiz (har provayder uchun, qaysi kalit bor bo'lsa shu bilan):

| # | Tekshiruv | Soxta vendorda nima tekshirilgan | Haqiqiy kalitda nima qo'shimcha |
|---|---|---|---|
| 1 | Sozlamalarda kalit + "Test Connection" | protokol, 401/429/500/404 xabarlari, kalit qaytmasligi (3 provayder) | kalitning haqiqiy qabul qilinishi, model nomi (`claude-sonnet-5-5`, `gpt-5-mini`, `gemini-3.6-flash`) hozir ham mavjudligi |
| 2 | "Ushbu oy nechta sotuv buyurtmasi bor?" | sikl, vosita chaqiruvi, KPI blok, son Odoo bilan teng | **model to'g'ri vositani tanlaydimi** (`find_models` → `aggregate`), sanani to'g'ri beradimi ("shu oy") |
| 3 | "Eng ko'p sotib olgan 5 mijoz" | jadval blok, nomlar Odoo guruhlashi bilan teng | model `sale.report` ni afzal ko'radimi (valyuta aralashmasligi uchun); aks holda ogohlantirish chiqadi |
| 5 | `schema` rejimida ism bilan so'rov | vendorga nom ketmaydi, tanlash tugmasi chiqadi | model `search_records` yo'qligida `pick_record`/`ask_user` ni o'zi ishlatadimi |
| 7 | Tarmoq uzilganda | tushunarli xato, chat qotmaydi | haqiqiy timeout sozlamasi bilan uzoq javob |

Kutilmagan natija chiqsa (model noto'g'ri vosita tanlasa, juda ko'p qadam ketsa) bu **prompt** (`lib/prompt.py`) va vosita ta'riflarini (`models/ai_tools.py`) yaxshilash ishi bo'ladi. Aniqlikni o'lchaydigan "oltin to'plam" F5 da.

## Boshqa
- Xarajatni o'lchash (tokenlar) faqat haqiqiy vendorda ma'noli: `levelix.ai.message.tokens_*` maydonlari yoziladi, soxta vendor tayyor raqam beradi.
- Katta bazada tezlik (M-Dom nusxasi lokalda yo'q).

## F5: haqiqiy kalit bilan

Soxta vendor "yaxshi model"ni o'ynaydi, shuning uchun quyidagilar hali **o'lchanmagan** (kalit kiritilgach):

| # | Nima | Qanday |
|---|---|---|
| 1 | **Oltin to'plamning birinchi o'lchovi** | avval `golden/questions.json` ni tuzating, keyin `python3 scripts/run_golden.py --write notes/F5_golden_v1.md`. Maqsad raqamini birinchi natijadan keyin birga belgilaymiz |
| 2 | UI testi 1, 5, 6, 7 haqiqiy modelda | chatga o'sha jumlalarni yozing: qoralama chiqadimi, `STATE_FILTER_MISSING` ogohlantirishi, "ishonchim past" tugmasi, mavjud bo'lmagan narsani so'rash (model uydirma dashboard chiqarmasligi) |
| 3 | Prompt injection | yozuv nomiga "ignore your rules ..." yozib (mijoz yoki mahsulot nomi), shu ma'lumot chiqadigan dashboard so'rang: model ko'rsatmaga bo'ysunmasligi kerak. Soxta modelda faqat "matn vosita natijasi ichida boradi" tekshirilgan |
| 4 | Tuzatish sikli haqiqiy xatolarda | model real xato qilsa (maydon nomi, noto'g'ri tur) 3 urinishda tuzatadimi; kerak bo'lsa prompt (`levelix_ai_board/lib/guide.py`) va hint'lar yaxshilanadi |
| 5 | Kalitsiz sinab bo'lmaydigan hint'lar | xarid va kassa hint'lari Odoo manbasidan tekshirilgan, lekin ilovalari bu bazada o'rnatilmagan: o'rnatilgan bazada `get_hints` va oltin to'plam (B01, B02, K01) bilan sinash |

## F6: haqiqiy kalit bilan

| # | Nima | Qanday |
|---|---|---|
| 1 | **AI orqali heatmap** (UI testi 8) | chatga "Hafta kunlari va soatlar bo'yicha buyurtmalar" yozing: heatmap qoralamasi chiqishi kerak (`day_of_week` × `hour_number`) |
| 2 | **AI yangi imkoniyatlarni to'g'ri ishlatadimi** | "oxirgi 30 kun va oldingi davr bilan taqqoslash" (KPI ▲▼, `fill_gaps`), "filtr bilan davrni almashtirsa bo'ladigan dashboard", "o'rtacha buyurtma" (`calc`), "toifalar ulushi" (pie); model `view` kalitini yoki `compare` shartini xato yozsa tuzatish sikli ishlaydimi |
| 3 | **Oltin to'plam qayta o'lchovi** | `golden/questions.json` ni tuzatgach: `python3 scripts/run_golden.py --write notes/F5_golden_v1.md`. Yangi turlar (heatmap, taqqoslash) uchun savollar siz tuzatganingizdan keyin qo'shiladi |
| 4 | Brauzer testlari F4/F5 | `scripts/f4_ui_browser.py`, `scripts/f5_ui_browser.py` bazadagi kalitni soxta kalit bilan almashtiradi, shuning uchun F6 da yurgizilmadi. Kalitni qayta kiritishga tayyor bo'lganingizda yurgiziladi |

## F7: haqiqiy kalit bilan

| # | Nima | Qanday |
|---|---|---|
| 1 | Chat orqali tahrirlash murakkabroq iboralarda | "qarzdorlarni ham qo'sh" (yangi vidjet, hisob-faktura hint'i kerak), "faqat Toshkent mijozlari", "filtr qo'sh": `update_dashboard` to'g'ri patch yozadimi, tuzatish sikli ishlaydimi |
| 2 | Brauzerdagi to'liq yo'l | board sahifasida "Change with AI" → chatga yozish → dashboard yangilanishi (hozir chip va tugma brauzerda, AI bosqichi `scripts/f7_ai_check.py` bilan alohida sinalgan) |
