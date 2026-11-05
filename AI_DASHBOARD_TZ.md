# AI Dashboard — Texnik topshiriq (qisqa)

> Holat: **qoralama v0.1**, 2026-11-03. Texnik tafsilotlar: `AI_DASHBOARD_TEXNIK_TZ.md`.
> Modul nomlari ishchi nomlar. Image'da `levelix_dashboard` moduli allaqachon bor (spreadsheet dashboard'lar ko'rinishi), shuning uchun yangi modul boshqa nom oladi.

---

## 1. Maqsad

Foydalanuvchi **oddiy tilda** yozadi, tizim **tayyor dashboard** chizadi.

> "Shu oy sotuvni kunlar bo'yicha ko'rsat, eng ko'p sotilgan 10 ta tovarni va qarzdor mijozlarni ham qo'sh."

Dasturchi ham, hisobot sozlovchi ham kerak emas. Dashboard har ochilganda **jonli** ma'lumot bilan yangilanadi.

## 2. Kim ishlatadi

**Hamma**: rahbar, sotuvchi, omborchi, buxgalter. Savollar oldindan noma'lum. Har kim o'z huquqiga mos narsani ko'radi.

## 3. Foydalanuvchi nima qila oladi

1. Chatga yozadi, dashboard chiqadi.
2. Natijani chatda **oddiy tilda** o'qiydi: "Men nima qildim" bloki (nimani sanadim, qaysi sana, nimani chiqarib tashladim).
3. Xato bo'lsa, tugma yoki gap bilan tuzatadi: "yetkazilgan bo'yicha qil", "ustunli qil", "oxirgi 3 oy".
4. Grafikdagi nuqtani **bosadi**, tagidagi yozuvlar ochiladi.
   Misol: to'lqinli sotuv grafigida 12-noyabrni bosadi, o'sha kunning sale order'lari jadvali chiqadi.
5. Dashboard'ni saqlaydi, nusxalaydi, boshqalarga ulashadi.

## 4. Ko'rinishlar

| Tur | Nima uchun |
|---|---|
| KPI karta (taqqoslash ▲▼, kichik grafik bilan) | bitta muhim raqam |
| To'lqinli / chiziqli / area | vaqt bo'yicha o'zgarish |
| Ustunli (yonma-yon, ustma-ust, gorizontal) | taqqoslash |
| Doira | ulushlar (8 tagacha bo'lak) |
| Jadval (jami qator, rangli belgilash) | aniq raqamlar |
| Heatmap (hafta kuni × soat) | qachon ko'p bo'ladi |
| Voronka, Treemap, Gauge, Waterfall, Scatter, Combo | maxsus tahlil |

Keyingi bosqichda: sankey va xarita.

## 5. Dizayn

- Odoo ko'rinishiga **bog'liq emas**: o'z dizayn tizimi (ranglar, shrift, bo'shliqlar).
- Yorug' va qorong'i rejim, mobil moslashuv, UZ/RU/EN formatlari.
- To'liq ekranli ish maydoni (kerak bo'lsa Odoo paneli yashirinadi).
- Yengil animatsiya, tez yuklanish, klaviatura bilan boshqarish.

## 6. Asosiy qoidalar

1. **AI raqam hisoblamaydi.** U faqat "nimani ko'rsatish"ni tanlaydi. Raqamlarni Odoo hisoblaydi.
2. **AI kod yoki SQL yozmaydi.** U qat'iy formatdagi tavsif (JSON) qaytaradi, tizim uni tekshirib bajaradi.
3. **Huquqlar saqlanadi.** Har kim faqat o'z ko'ra oladigan ma'lumotni ko'radi. Bir dashboard'ni ikki kishi ochsa, har biri o'z natijasini ko'radi.
4. **Dashboard tavsif sifatida saqlanadi**, natija sifatida emas. Ochilganda AI ishlamaydi, shuning uchun tez va arzon.
5. **Xato ko'rinadigan bo'lishi kerak.** "Men nima qildim" bloki, "qanday hisoblangan" tugmasi, raqamni bosib yozuvlarni ko'rish.
6. **AI ga ma'lumot yuborish sozlanadi.** Boshlang'ich: tuzilma va jamlangan natijalar yuboriladi. Sozlamada "faqat tuzilma" rejimi bor (maxfiylik uchun).

## 7. Xatolikdan himoya (qisqacha)

AI texnik jihatdan to'g'ri, lekin ma'nosi noto'g'ri so'rov tuzishi mumkin (masalan, bekor qilingan buyurtmalarni ham sanash). Himoya:

- AI o'z talqinini oddiy tilda yozadi, foydalanuvchi o'qib tuzatadi.
- Kod noto'g'ri holatlarni o'zi ushlaydi (yig'ib bo'lmaydigan maydon, valyutalar aralashishi, takroriy sanash).
- Saqlashdan oldin har so'rov sinab ko'riladi, xato bo'lsa AI tuzatadi.
- 50–100 ta real savoldan iborat sinov to'plami bilan aniqlik doim o'lchanadi.
- "Noto'g'ri" tugmasi: foydalanuvchi bildirgan holat keyingi yaxshilashga ketadi.

Xatoni nolga tushirib bo'lmaydi. Maqsad: xato **ko'rinsin** va tuzatish **oson** bo'lsin.

## 8. Kelajakka tayyorlik

AI qismi dashboard'dan **ajratilgan** modul. Keyinchalik boshqa funksiyalar (masalan, hujjat tayyorlash, kontakt qidirish, o'zgartirish taklif qilish) shu AI poydevoriga yangi modul sifatida qo'shiladi, dashboard kodiga tegmasdan.

Dashboard modulining o'zi AI'siz ham ishlaydi (qo'lda tuzish mumkin).

## 9. Modullar (ishchi nomlar)

| Modul | Vazifa |
|---|---|
| `levelix_ai_core` | AI provayderlar (OpenAI, Claude, Gemini), suhbat, vositalar reyestri, jurnal |
| `levelix_board` | dashboard: tavsif formati, so'rov ijrochisi, vidjetlar, drill-down, saqlash |
| `levelix_ai_board` | ikkisini ulaydi: AI dan dashboard yaratish va tahrirlash |

`levelix_ai` dagi tayyor qismlar (provayderlar, vositalar sikli, nisbiy sanalar) tanlab ko'chiriladi. Ovozli suhbat va hozirgi panel ko'chirilmaydi.

## 10. Bosqichlar

| # | Bosqich | Natija (qabul mezoni) |
|---|---|---|
| 1 | Tavsif formati + ijrochi + 4 vidjet (KPI, to'lqin, ustun, jadval) + drill-down. Qo'lda yozilgan tavsif bilan | to'lqin grafigida kunni bosganda o'sha kunning sale order'lari ochiladi |
| 2 | `levelix_ai_core` + `levelix_ai_board`: chatdan dashboard, tekshiruv, o'zini tuzatish, qoralama, "Men nima qildim" bloki | savol yozilsa, qoralama chiqadi, xato bo'lsa o'zi tuzatadi |
| 3 | Qolgan grafik turlari, filtrlar, cross-filter, davr taqqoslash, hisoblangan ko'rsatkichlar | 10 xil tur ishlaydi |
| 4 | Qo'lda tahrirlash, suhbat orqali tahrirlash, versiya tarixi, ulashish | "ustunli qil" ishlaydi, orqaga qaytarish mumkin |
| 5 | Ogohlantirish, rejali yuborish (Telegram/email), TV rejimi, "nega tushdi?" | ertalab dashboard o'zi yuboriladi |

## 11. Qo'shimcha funksiyalar (kelajak ro'yxati)

- Maqsad va chegara (KPI belgilangan darajadan o'tsa xabar).
- Rejali yuborish: har kuni PNG/PDF Telegram yoki emailga.
- TV rejimi: to'liq ekran, avtomatik yangilanish va almashish.
- "Nega tushdi?": AI ikki davrni solishtirib sababini tushuntiradi.
- Hisoblangan ko'rsatkichlar (marja = daromad − tannarx).
- Eksport: PNG, PDF, XLSX, CSV.
- Shablonlar galereyasi (Sotuv, Ombor, Buxgalteriya).
- Izohlar: grafik nuqtasiga eslatma qoldirish.
- Ochiq havola (faqat alohida xavfsizlik ko'rigidan keyin).

## 12. Qabul qilingan qarorlar

- Hamma foydalanuvchi uchun, har qanday savol (qattiq ro'yxat yo'q).
- Grafik kutubxonalari: ECharts (boy ko'rinishlar) va Chart.js (oddiy), ikkalasi, bitta adapter orqali.
- AI ga ma'lumot: jamlangan natijalar ham yuboriladi, sozlamada o'chiriladi.
- Tushuntirish bloki chatda, tavsifdan avtomatik yoziladi (AI emas), faqat "ishonchim past" qismini AI yozadi.

## 13. Ochiq masalalar

1. Yangi modullar prefiksi va litsenziyasi (`levelix_ai` OPL-1, boshqalar LGPL-3).
2. 20–30 ta real savol ro'yxati (sinov to'plami uchun). Rahbar, omborchi, buxgalter nimani so'raydi?
3. Dashboard'ni ulashish darajalari: faqat o'zi / guruh / butun kompaniya. Ochiq havola kerakmi?
4. Image qaysi Odoo'da ishlaydi: faqat Odoo 19 Community (hozirgi image) deb qabul qilindi.
