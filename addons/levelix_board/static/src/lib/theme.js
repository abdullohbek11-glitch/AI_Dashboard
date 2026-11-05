/** @odoo-module **/
// What the chart libraries need from the design tokens (--lxb-*). Pure: `get(name)` is
// `getComputedStyle(root).getPropertyValue`, so both libraries end up with the same colours.

export const CATEGORY_COUNT = 8;

export const FALLBACK_THEME = {
    text: "#1d2433",
    textMuted: "#5c667a",
    grid: "#e3e7ee",
    surface: "#ffffff",
    border: "#d5dbe5",
    font: "system-ui, sans-serif",
    palette: ["#0072b2", "#e69f00", "#009e73", "#d55e00", "#cc79a7", "#56b4e9", "#8c8c3f", "#7a7f8c"],
};

const TOKENS = { text: "--lxb-text", textMuted: "--lxb-text-muted", grid: "--lxb-grid", surface: "--lxb-surface", border: "--lxb-border", font: "--lxb-font" };

export function readTheme(get) {
    const read = (name, fallback) => (get(name) || "").trim() || fallback;
    const theme = { palette: [] };
    for (const [key, token] of Object.entries(TOKENS)) {
        theme[key] = read(token, FALLBACK_THEME[key]);
    }
    for (let i = 1; i <= CATEGORY_COUNT; i++) {
        theme.palette.push(read(`--lxb-cat-${i}`, FALLBACK_THEME.palette[i - 1]));
    }
    return theme;
}

/** "#0072b2" + 0.18 -> "rgba(0, 114, 178, 0.18)"; anything that is not #rrggbb is returned unchanged. */
export function withAlpha(color, alpha) {
    const match = /^#([0-9a-f]{6})$/i.exec(color);
    if (!match) {
        return color;
    }
    const n = parseInt(match[1], 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export function colorAt(theme, index) {
    return theme.palette[index % theme.palette.length];
}
