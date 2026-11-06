# F6 natijalari (2026-11-06)

## Nima qilindi (`levelix_board`, `levelix_ai_board`)
- **13 vidjet turi:** kpi, line, area, bar, table (avvalgi) + **pie** (Chart.js), **heatmap, funnel, treemap, gauge, waterfall, scatter, combo** (ECharts; bundle'da hammasi bor edi, qayta yig'ish kerak bo'lmadi). Har bir turning shakli `lib/spec.py` `SHAPES` da, qoidalari validator'da.
- **Pie:** 8 tadan ko'p bo'lak avtomatik "eng katta 7 + Boshqalar" (15 mijoz → 8 bo'lak, yig'indi saqlanadi).
- **Global filtrlar** (`date_range` presetlar va oraliq, `company`, `select`): `applies_to {model: maydon}`; tanlov spec'ga saqlanmaydi; drill, tushuntirish va taqqoslash o'sha tanlov bilan ishlaydi. Filtr paneli sahifa tepasida; "Custom range" sana maydonlari bilan.
- **Cross-filter:** `interact.on_click.action = "cross_filter"`; bosilgan guruhni server qayta topadi, bir xil model vidjetlarini filtrlaydi; qayta bosish bekor qiladi; chip ko'rinadi.
- **`compare`:** oldingi davr / oldingi yil; KPI da ▲▼ foiz va "vs previous period", chiziqda punktir qator; butun kalendar oy oldingi kalendar oy bilan taqqoslanadi.
- **`calc`:** o'z parseri (`eval` yo'q), nolga bo'lish = bo'sh qiymat; jadval jami va "Boshqalar" qatorida formula jamlar ustida.
- **View kalitlari qat'iy** (yozuv xatosi xato bo'ladi), heatmap yorliqlari (Du/Se..., 15:00), pie uchun faqat yig'iladigan o'lchov.
- **AI:** qo'llanma (`guide.py`) va chat prompt yangilandi: yangi turlar, `view`, `compare`, `calc`, `filters`, `cross_filter`; xato xabarlari tuzatish sikli uchun aniq ("needs 'fill_gaps': true").
- Hujjat: TZ 6.14, faza rejasi, `DEFERRED.md`.

## Sinov
- Python: `levelix_board` **262** (F5 da 190), `levelix_ai_core` 81, `levelix_ai_board` 52; JS **47** (35 edi).
- **Brauzer `scripts/f6_ui_browser.py`: 15 tekshiruv, hammasi o'tdi.** Raqamlar mustaqil SQL bilan solishtirildi: 16 vidjet yorug' va qorong'i rejimda; ▲▼ foizi qo'lda hisoblangan bilan teng (180.5% / 238.9%); davr filtri (7 kun, oraliq), sotuvchi tanlovi; oktabr sentabr bilan (`2026-09-01 – 2026-09-30`); cross-filter (Cheese 1kg → daromad SQL'ga teng, qayta bosilsa qaytadi); heatmap katagi drill (5 buyurtma = SQL 5); `calc` har qatorda; pie 7 + Boshqalar; "how it was calculated" davrni va taqqoslashni nomlaydi; `sotuvchi` o'z raqamini ko'radi.
- F3 brauzer testi 14/14 (yangi: sahifa scroll qilinadi; "hali qurilmagan tur" sifatida `funnel` o'rniga `sankey`).
- Test dashboard: **"F6 all types"** (egasi `boshliq`, kompaniyaga ulashilgan; `scripts/seed_f6.py`).

## Topilmalar (testlar topdi)
- Hisoblangan o'lchovli jadvalda valyuta so'rovi `None` kalitni `formatted_read_group` ga berar edi (ichki xato): `runner.currency_ids` tuzatildi.
- "Custom range" tanlanganda sana maydonlari chiqmas edi (bo'sh oraliq "all" ga aylanib tanlov yo'qolardi): alohida holat saqlanadi.
- Gauge'da shkala raqamlari qiymat bilan to'qnashardi: shkala raqamlari olib tashlandi.
- Taqqoslash uchun davr faqat domain'dan emas, global davr filtridan ham olinadi (aks holda yolg'on ogohlantirish chiqardi).

## Qarorlar va cheklovlar
- Cross-filter faqat **manbasi bir xil** vidjetlar orasida; yoqilganda shu vidjetlarda taqqoslash o'chadi.
- `compare` faqat kpi/line/area, ≤1 sana o'qi, sana o'qida `fill_gaps: true`; davr topilmasa xato emas, ogohlantirish.
- Tanlov ro'yxati (`select`) 50 tagacha qiymat (`name_search` limiti), qidiruv oynasi yo'q.
- Haftaning birinchi kuni heatmap'da dushanba (Odoo `day_of_week`: 0 = yakshanba).
- **Chatdagi `aggregate` hali core'ning o'z ijrochisida** (board ijrochisiga yo'naltirish F6 ro'yxatida yo'q; core board'ga bog'lana olmaydi, shuning uchun `levelix_ai_board` ichida alohida ish bo'ladi). Chatda hozircha `compare`/`calc` yo'q, ular faqat dashboard'da.
- Haqiqiy modelda heatmap so'rovi, oltin to'plam qayta o'lchovi va F4/F5 brauzer testlari `DEFERRED.md` da (F4/F5 skriptlari bazadagi kalitni almashtiradi).

## Qo'shimcha: chat javobini dashboard qilib saqlash (F6 dan keyin)
Foydalanuvchi "dashboard yarat" demaydi, "ma'lumot yig'ib ber" deydi (suhbat #1414: so'nggi 30 kun, pie chart). Endi hisoblab chiqilgan grafik/raqam/jadval ostida **"Keep this as a dashboard? [Save as dashboard]"** chiqadi. Bosilsa dashboard yaratiladi (nisbiy sanalar bilan, har ochilganda bugungi ma'lumot), bosilmasa hech narsa bo'lmaydi. TZ 6.15.
- Testlar: `levelix_ai_board` 68 (52 edi), `levelix_ai_core` 81, `levelix_board` 262.
- Haqiqiy OpenAI va brauzerda sinaldi: pie chart → taklif → saqlash → chat qayta ochilganda "Saved" → dashboard ochildi (doira 3 toifa bilan, xato yo'q). Sinov foydalanuvchisi va yozuvlari o'chirildi.

## Qo'shimcha: "Summalar" filtri (soliqsiz / soliq bilan), TZ 6.16
"Har vidjetda ikkala summa" qoidasi almashtirildi: dashboard tepasida **Amounts: [Without tax | With tax]** tugmasi, har vidjet bitta summa ko'rsatadi, tugma hammasini birdan o'zgartiradi (pie ham, KPI ham, jadval ham). `"fixed": true` o'lchov o'z maydonida qoladi. AI pul bor dashboard'ga filtrni o'zi qo'shadi; chat javobini saqlaganda ham.
- Testlar: `levelix_board` 273, `levelix_ai_core` 81, `levelix_ai_board` 73, JS 47; brauzer f6 **17/17** (soliqli test buyurtma bilan: soliqsiz 63 181 756 → soliq bilan 63 301 756, ikkisi SQL'ga teng; Hamkorning daromadi aynan buyurtma solig'i 120 000 ga oshdi, "doim soliq bilan" ustuni o'zgarmadi, buyurtmalar soni o'zgarmadi), f3 14/14.
- **Haqiqiy OpenAI:** "so'nggi 30 kun, kunlik daromad, top 5 mahsulot, sotuvchi" → qoralamada `amount_basis` filtri va har vidjetda bitta `price_subtotal` o'lchovi, soliq bilan ham ishlaydi. Bitta tuzatish ketdi (drill xaritasida `date` unutilgan: oldingidek).

## Qo'shimcha: AI tezligi (TZ 6.17)
Chat sekin edi: vaqtning >99% i model kutish (vositalar 0.1–0.3 s). Qilingan: **"Thinking Time" sozlamasi** (standart Fast=`low`), **oldindan tayyorlangan hint va maydonlar** (2 qadam kam), **`preview_widget` ixtiyoriy**, **drill qisqa yozuvi**. Haqiqiy modellarda: OpenAI count 23→5 s, dashboard 65→19 s; Gemini count 14→7 s, dashboard 15 s. Testlar: `levelix_ai_core` 86, `levelix_ai_board` 82.
- Cheklov: `minimal` tezroq, lekin aniqlikni buzdi (qatorlarni sanadi); sozlamada "Fastest" deb belgilangan, standart emas. Gemini'da `low`/`high` darajalari kvota tufayli to'liq solishtirilmadi (faqat yuqoridagi `low` natijasi bor).
- Hali qilinmagan: yengilroq model tanlovi (masalan `gpt-5-nano` yoki Gemini flash-lite) oddiy savollar uchun; token keshi Gemini'da 0 ko'rsatadi (OpenAI'da ishlaydi).

## Qo'shimcha: suhbat #2039 tahlili va tuzatishlar (TZ 6.18)
Heatmap so'ralganda AI "mavjud emas" degan edi. Asosiy sabab: **qo'llanmada eski "Other chart types are not available yet" qatori qolgan** (F6 yozuvi jimgina bajarilmagan). Tuzatildi va qo'llanma har tur va `view` kaliti uchun testlanadi. Yana: yo'naltirish qoidasi (oddiy savol chatda, murakkab dashboard'da), chatga hafta kuni/soat/oy bo'yicha guruhlash, tartib iborasini tushunish, bitta aniqlashtiruvchi savol, "oxirgi N kun" = N kun, `date:day_of_week` yozuvi, matnga oqib chiqqan `(show=chart)` tozalanadi. Testlar: `levelix_board` 274, `levelix_ai_core` 99+, `levelix_ai_board` 84.
