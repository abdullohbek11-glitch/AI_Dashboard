# F7 natijalari (2026-11-06)

## Nima qilindi
- **Qo'lda tahrirlash** (`levelix_board`): surish/o'lcham (24 ustunli to'r, to'qnashuvda pastga suriladi), sarlavha, tur almashtirish, o'chirish, vidjet qo'shish (tur, manba, maydon, jonli ko'rinish). Qoralama, bitta "Saqlash".
- **Versiya va bir vaqtda tahrir:** `base_version` bilan `STALE_VERSION`; tarix (`lx_versions`, nima o'zgargani), `lx_restore` yangi versiya yozadi.
- **Ulashish:** faqat o'zi / tanlangan guruhlar / butun kompaniya; ko'ruvchi o'z raqamini ko'radi, tahrir tugmalari yo'q. **Nusxa, arxiv, PNG** (brauzerda).
- **Chat orqali tahrirlash** (`levelix_ai_board`): `update_dashboard` vositasi (patch, butun spec qayta tekshiriladi va ishga tushiriladi, 3 ta tuzatish), nishon = `board_id` (yozish huquqi shart) yoki suhbat qoralamasi. Board sahifasida **"Change with AI"** tugmasi chatni shu dashboard bilan ochadi (`levelix_ai_core`da `pin`).
- Hujjat: TZ 6.19, faza rejasi, `DEFERRED.md`.

## Sinov
- Python: `levelix_board` **302**, `levelix_ai_core` 99, `levelix_ai_board` **94** (84 edi; +10 `test_update_tool.py`); JS **55**.
- **Brauzer `scripts/f7_ui_browser.py`: 12 tekshiruv, hammasi o'tdi** (1 surish/o'lcham saqlanadi; 2/2b nom, tur, o'chirish, qo'shish; 4 tiklash; 5 sotuvchi o'z raqami, tugmalarsiz; 6 nusxa; 7 ikki oyna ogohlantirishi; 8 PNG 2888×2188; 8b/8c "Change with AI" chip; 9 arxiv; konsolda xato yo'q). F3 14/14, F6 17/17.
- **Haqiqiy modelda (`scripts/f7_ai_check.py`, hammasi bekor qilinadi):** "Top products ni ustunli qil" → faqat `w2.view.orientation=vertical`, `w1` o'zgarmadi, joylashuv saqlandi (6.6 s, 1 chaqiruv); "daily sales da oxirgi 3 oy" → faqat `w1` domeni o'zgardi (`today =1d -2m`, ya'ni kalendar 3 oy), `id` va joylashuv saqlandi (6.6 s). Versiyalar: manual → ai → ai, tarixdan qaytariladi.

## Topilmalar
- Sarlavha maydoni qayta chizishda yozilgan matnni yo'qotardi → `titleDraft` holati.
- Nusxa sarlavhasi asl nomda qolardi → spec sarlavhasi nusxa nomi.
- Pie uchun `limit` qo'shish oynasida noto'g'ri edi (pie ko'pi bilan 8) → pie uchun limit yo'q.
- Vidjet qo'shish va tahrirlashda `date` ning noto'g'ri nisbiy yozuvi (`today =90d`) serverda rad etildi: tuzatish sikli aynan shu uchun.

## Qarorlar (2026-11-06, foydalanuvchi)
- "Change with AI": chat shu dashboard bilan bog'lanadi. Chat allaqachon ochiq bo'lsa faqat yangi chatda ochiladi; ochiq bo'lmasa va oldingi chat bor bo'lsa "Davom ettirish / Yangi chat" so'raladi. Brauzer testi 8b–8h, core testlari `test_pin.py`.
- "Oxirgi N oy" = N*30 kun, bugun bilan (`today -89d`); kalendar oy faqat "kalendar/to'liq oy" deyilsa. Qo'llanmaga yozildi, haqiqiy modelda tasdiqlandi.
- "Faqat tuzilma" rejimida pin qilingan dashboard'ning sarlavhasi, shartlari va qiymatlari vendorga ketmaydi: faqat vidjet id, tur, manba va maydon nomlari beriladi.
