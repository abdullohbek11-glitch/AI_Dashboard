/** @odoo-module **/
// Pure number / date / text formatting. No Odoo imports: tested with `node --test`.

const UNITS = {
    en: ["K", "M", "B", "T"],
    uz: ["K", "M", "mlrd", "trln"],
    ru: ["тыс.", "млн", "млрд", "трлн"],
};
const DASH = "—";

/** "uz_UZ", "ru-RU", "en_US" -> "uz" | "ru" | "en" (the language of the unit words). */
export function unitLanguage(lang) {
    const base = String(lang || "en").split(/[-_@]/)[0].toLowerCase();
    return UNITS[base] ? base : "en";
}

/** Locale for Intl: Odoo's "uz_UZ" -> "uz-UZ". */
export function intlLocale(lang) {
    return String(lang || "en").replace("_", "-").split("@")[0];
}

function plain(value, lang, maxFraction) {
    return new Intl.NumberFormat(intlLocale(lang), { maximumFractionDigits: maxFraction }).format(value);
}

function withCurrency(text, currency) {
    if (!currency || !currency.symbol) {
        return text;
    }
    return currency.position === "before" ? `${currency.symbol}${text}` : `${text} ${currency.symbol}`;
}

/** Short form for axes and KPI cards: 1.2K, 3.4M, 2 mlrd. */
export function formatNumber(value, { lang = "en", decimals = 1, currency = null, percent = false } = {}) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return DASH;
    }
    const number = Number(value);
    let text;
    if (Math.abs(number) < 1000) {
        text = plain(number, lang, Number.isInteger(number) ? 0 : 2);
    } else {
        const units = UNITS[unitLanguage(lang)];
        let scaled = number;
        let index = -1;
        while (Math.abs(scaled) >= 1000 && index < units.length - 1) {
            scaled /= 1000;
            index += 1;
        }
        if (Math.abs(Number(scaled.toFixed(decimals))) >= 1000 && index < units.length - 1) {
            scaled /= 1000; // 999.96K must read 1M, not 1000K
            index += 1;
        }
        const unit = units[index];
        const glue = /^[A-Za-z]$/.test(unit) ? "" : " ";
        text = plain(scaled, lang, decimals) + glue + unit;
    }
    if (percent) {
        return `${text}%`;
    }
    return withCurrency(text, currency);
}

/** Full precision with digit grouping, for tables and tooltips. */
export function formatFull(value, { lang = "en", currency = null, percent = false } = {}) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return DASH;
    }
    const text = plain(Number(value), lang, 2);
    return percent ? `${text}%` : withCurrency(text, currency);
}

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Label of a bucket on a date axis. Values that are not ISO days (e.g. "Not set") pass through. */
export function formatDateLabel(value, granularity, lang = "en") {
    const match = ISO_DAY.exec(String(value));
    if (!match) {
        return String(value);
    }
    const [, year, month, day] = match;
    if (granularity === "year") {
        return year;
    }
    if (granularity === "quarter") {
        return `Q${Math.floor((Number(month) - 1) / 3) + 1} ${year}`;
    }
    const moment = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
    const options = granularity === "month"
        ? { month: "short", year: "numeric", timeZone: "UTC" }
        : { day: "numeric", month: "short", timeZone: "UTC" };
    return new Intl.DateTimeFormat(intlLocale(lang), options).format(moment);
}

export const DATE_PARTS = [
    "year_number", "quarter_number", "month_number", "iso_week_number", "day_of_year",
    "day_of_month", "day_of_week", "hour_number", "minute_number", "second_number",
];

/**
 * A numeric date part as a reader says it. Odoo counts the weekday from Sunday (0) to Saturday (6); months from 1.
 * Anything that is not a number (e.g. "Not set") passes through.
 */
export function formatPart(value, granularity, lang = "en") {
    const number = Number(value);
    if (value === null || value === undefined || value === "" || Number.isNaN(number)) {
        return String(value);
    }
    const locale = intlLocale(lang);
    if (granularity === "day_of_week") {
        return new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(2021, 0, 3 + number))); // 3 Jan 2021 was a Sunday
    }
    if (granularity === "month_number") {
        return new Intl.DateTimeFormat(locale, { month: "short", timeZone: "UTC" }).format(new Date(Date.UTC(2021, number - 1, 1)));
    }
    if (granularity === "hour_number") {
        return `${String(number).padStart(2, "0")}:00`;
    }
    if (granularity === "quarter_number") {
        return `Q${number}`;
    }
    return String(number);
}

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}
