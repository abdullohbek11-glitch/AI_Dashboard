# DEFERRED: tashqi resurs kerak bo'lgan, hali bajarilmagan tekshiruvlar

Bu ishlar **haqiqiy AI kaliti** kerak qiladi. Qolgan hamma narsa soxta vendor (`addons/levelix_ai_core/tests/fake_ai.py`) bilan tekshirilgan. Kalitni **siz** Odoo Sozlamalariga kiritasiz (Levelix AI → Settings → provayderni tanlab, kalitni qo'yib, "Save", so'ng "Test Connection"). Men kalitni o'zim kirita olmayman.

## F4: haqiqiy kalit bilan

Avval soxta vendorni bazadan olib tashlang: `docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/unseed_ai.py` (qaytarish: `scripts/seed_ai.py`). Keyin Sozlamalarda kalitni kiriting. Shundan keyin shu tartibda tekshiramiz (har provayder uchun, qaysi kalit bor bo'lsa shu bilan):

| # | Tekshiruv | Soxta vendorda nima tekshirilgan | Haqiqiy kalitda nima qo'shimcha |
|---|---|---|---|
| 1 | Sozlamalarda kalit + "Test Connection" | protokol, 401/429/500/404 xabarlari, kalit qaytmasligi (3 provayder) | kalitning haqiqiy qabul qilinishi, model nomi (`claude-sonnet-5-5`, `gpt-5-mini`, `gemini-2.5-flash`) hozir ham mavjudligi |
| 2 | "Ushbu oy nechta sotuv buyurtmasi bor?" | sikl, vosita chaqiruvi, KPI blok, son Odoo bilan teng | **model to'g'ri vositani tanlaydimi** (`find_models` → `aggregate`), sanani to'g'ri beradimi ("shu oy") |
| 3 | "Eng ko'p sotib olgan 5 mijoz" | jadval blok, nomlar Odoo guruhlashi bilan teng | model `sale.report` ni afzal ko'radimi (valyuta aralashmasligi uchun); aks holda ogohlantirish chiqadi |
| 5 | `schema` rejimida ism bilan so'rov | vendorga nom ketmaydi, tanlash tugmasi chiqadi | model `search_records` yo'qligida `pick_record`/`ask_user` ni o'zi ishlatadimi |
| 7 | Tarmoq uzilganda | tushunarli xato, chat qotmaydi | haqiqiy timeout sozlamasi bilan uzoq javob |

Kutilmagan natija chiqsa (model noto'g'ri vosita tanlasa, juda ko'p qadam ketsa) bu **prompt** (`lib/prompt.py`) va vosita ta'riflarini (`models/ai_tools.py`) yaxshilash ishi bo'ladi. Aniqlikni o'lchaydigan "oltin to'plam" F5 da.

## Boshqa
- Xarajatni o'lchash (tokenlar) faqat haqiqiy vendorda ma'noli: `levelix.ai.message.tokens_*` maydonlari yoziladi, soxta vendor tayyor raqam beradi.
- Katta bazada tezlik (M-Dom nusxasi lokalda yo'q).
