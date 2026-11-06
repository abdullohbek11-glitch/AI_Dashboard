# F5 natijalari (2026-11-05)

## Nima qilindi: `levelix_ai_board`
- **Vositalar:** `get_hints` (kalit so'z bo'yicha hint, foydalanuvchi o'qiy oladigan va bazada bor modellar uchun), `preview_widget` (bitta vidjet so'rovini sinab ko'rish: shakl, ogohlantirish yoki tuzatiladigan xatolar; `schema` rejimida namunasiz), `build_dashboard` (to'liq spec; server tekshiradi va **har vidjetni haqiqatan ishga tushiradi**; ok bo'lsa foydalanuvchining qoralamasi yaratiladi). `ask_user` core'da (F4).
- **Spec JSON matn sifatida uzatiladi** (vosita argumenti `string`): Gemini ichma-ich bo'sh obyekt sxemasini rad etadi, uchala vendor matnni qabul qiladi.
- **Tuzatish sikli:** xato `[{path, code, message}]` ko'rinishida AI ga qaytadi ("Did you mean ..."), birinchi urinish + 3 ta tuzatish; oxirgi ruxsat etilgan xatoning o'zida `give_up` + "to'xta, halol ayt" ko'rsatmasi (qadam byudjeti ichida javob berishi uchun). Undan keyingi chaqiruv rad etiladi. Qoralama yaratilmaydi.
- **Qoralama:** `levelix.board` `state=draft`, egasi foydalanuvchi, `source_conversation_id`. Bir suhbatda qayta so'rash o'sha qoralamani yangilaydi; [Saqlash] dan keyingi so'rov yangisini yaratadi. Saqlanmasdan chiqib ketsa yo'qolmaydi.
- **Hint reyestri** `levelix.ai.hint`: sotuv (`sale.report`), faktura (`account.invoice.report`), xarid (`purchase.report`), kassa (`report.pos.order`). Maydonlar dev bazadagi haqiqiy modeldan (sotuv, faktura) va Odoo 19 manbasidan (xarid, kassa: ilovalari bazada o'rnatilmagan) tekshirildi. **TZ tuzatildi:** kassa hisoboti `pos.order.report` emas, `report.pos.order`. Ombor/qarzdorlik/CRM hint'lari yozilmadi (tekshirib bo'lmadi).
- **Prompt qoidalari** (`lib/guide.py`): hint → describe → preview → build, tuzatish, halollik, spec formati, nisbiy sanalar, `assumptions`, `uncertain`, texnik nom yo'q, ≤8 vidjet.
- **`uncertain[]` tugmalari:** spec ichida `{text, patch}`; saqlashdan oldin har patch nusxada sinaladi (`UNCERTAIN_PATCH_INVALID`); bosilganda server patchni **saqlangan spec'dan** oladi (brauzerdan emas), qo'llaydi va butun spec'ni qayta tekshiradi. Vidjetlar ro'yxati o'zgarsa qolgan tugmalar olib tashlanadi (indekslar siljiydi), o'zgarmasa faqat hamon to'g'ri keladiganlari qoladi.
- **`levelix_board` ga:** `lib/patch.py` (add/replace/remove, faqat `/widgets /filters /title /assumptions`, vidjet id o'zgarmaydi), `lx_apply_patch`, `lx_apply_uncertain`, `lx_activate`; `assumptions`/`uncertain` shakl tekshiruvi.
- **`levelix_ai_core` ga:** "Wrong answer?" tugmasi va `levelix.ai.feedback` (savol, javob, nima qilingani, eslatma; server yozadi, foydalanuvchi o'qiydi, administrator ko'radi: "Marked as Wrong" menyusi); vosita "muvaffaqiyatsiz urinish" belgisi (`side.error`); bir vositadan bir nechta blok.
- **Chat bloklari:** `board_draft` (F3 vidjetlari chat ichida jonli, [Keep] [Change], "I was not sure about" tugmalari, ogohlantirishlar, farazlar), `board_explain` ("What I did": muhim qatorlar + Details).
- **Oltin to'plam:** `golden/questions.json` (30 savol + smoke), `scripts/run_golden.py` (oracle: ishga tushirish paytidagi Odoo so'rovi), `notes/F5_golden_v1.md` (hozircha "o'lchanmagan").

## Sinov
- Python: `levelix_board` 190, `levelix_ai_core` 76, `levelix_ai_board` 43; JS 35.
- **Brauzer** `scripts/f5_ui_browser.py`: 13 tekshiruv, hammasi o'tdi: reja bo'yicha 1–10 + tuzatish sikli audit logda + OpenAI/Gemini formatlari.
- Soxta vendor "yaxshi model"ni o'ynaydi, shuning uchun bu testlar modelning o'ziga emas, uning **atrofiga** (vositalar, sikl, bloklar, huquq, qoralama) tegishli. Model sifati: oltin to'plam (kalit kerak).

## Topilmalar va qarorlar
- **Qoida:** `build_dashboard` biznes ma'lumotni o'zgartirmaydi (test: sanab ko'rilgan jadvallar soni o'zgarmaydi); vositalar ro'yxatida yozuvchi vosita yo'q.
- **Prompt injection:** yozuv nomidagi "boshqa ko'rsatma" modelga faqat vosita natijasi ichida boradi (user/system matnida emas); `schema` rejimida umuman bormaydi. Haqiqiy modelning bunga chidamliligi **TEKSHIRILMAGAN** (kalit kerak).
- **Aniq tuzatish:** vidjetlar o'chirilgach tugma indeksi boshqa vidjetga tegib ketardi: test topdi, endi ro'yxat o'zgarsa tugmalar olib tashlanadi.
- `aggregate` (chatdagi savollar) hali core'ning o'z ijrochisida, board ijrochisiga yo'naltirilmadi (F4 yozuvidagi "F5 da" rejasi). Sabab: F5 ro'yxatida yo'q va hozir ikki ijrochi bir xil javob beradi. F6 da `compare`/`calc` bilan birga qaror qilinadi.
- `update_dashboard` (suhbat orqali tahrirlash) F7 da: hozir "Change" tugmasi savol maydonini to'ldiradi, yangi so'rov o'sha qoralamani qayta quradi.
