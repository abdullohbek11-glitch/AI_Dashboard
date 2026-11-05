/** @odoo-module **/
import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { readTheme } from "../lib/theme.js";

const STORAGE_KEY = "levelix_board.theme";

export const boardThemeService = {
    start() {
        const stored = browser.localStorage.getItem(STORAGE_KEY);
        const prefersDark = browser.matchMedia && browser.matchMedia("(prefers-color-scheme: dark)").matches;
        const state = reactive({ mode: stored === "dark" || stored === "light" ? stored : prefersDark ? "dark" : "light" });
        return {
            state,
            toggle() {
                state.mode = state.mode === "dark" ? "light" : "dark";
                browser.localStorage.setItem(STORAGE_KEY, state.mode);
            },
            /** Design tokens as the chart libraries need them, read from the page so both look the same. */
            tokens(element) {
                const style = getComputedStyle(element);
                return readTheme((name) => style.getPropertyValue(name));
            },
        };
    },
};

registry.category("services").add("levelix_board.theme", boardThemeService);
