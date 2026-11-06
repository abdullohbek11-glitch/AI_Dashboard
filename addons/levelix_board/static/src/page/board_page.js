/** @odoo-module **/
import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpcMessage } from "../core/board_data.js";
import { DrillPanel } from "../drill/drill_panel.js";
import { AddWidgetDialog } from "../edit/add_widget_dialog.js";
import { AiChatDialog } from "../edit/ai_chat_dialog.js";
import { HistoryPanel } from "../edit/history_panel.js";
import { ShareDialog } from "../edit/share_dialog.js";
import { gridStyle, MOBILE_BREAKPOINT_PX, mobileOrder, placeWidgets } from "../lib/grid.js";
import { BoardWidget } from "../widgets/shell/board_widget.js";
import { defaultSizeOf } from "../widgets/widget_registry.js";
import { BoardEditor } from "./board_editor.js";

const PRESETS = [
    ["all", () => _t("All time")], ["today", () => _t("Today")], ["yesterday", () => _t("Yesterday")],
    ["this_week", () => _t("This week")], ["last_week", () => _t("Last week")], ["last_7_days", () => _t("Last 7 days")],
    ["last_30_days", () => _t("Last 30 days")], ["last_90_days", () => _t("Last 90 days")], ["this_month", () => _t("This month")],
    ["last_month", () => _t("Last month")], ["this_quarter", () => _t("This quarter")], ["last_quarter", () => _t("Last quarter")],
    ["this_year", () => _t("This year")], ["last_year", () => _t("Last year")],
];

/** The choices a dashboard starts with: each filter's default (nothing chosen when it has none; amounts without tax). */
export function startingChoices(filters) {
    const values = {};
    for (const filter of filters || []) {
        const fallback = filter.type === "date_range" ? "all" : filter.type === "amount_basis" ? "untaxed" : null;
        values[filter.id] = filter.default === undefined ? fallback : filter.default;
    }
    return values;
}

/** Full-screen dashboard page: the list of dashboards, and one dashboard with its widgets and filters. */
export class BoardPage extends Component {
    static template = "levelix_board.BoardPage";
    static components = { BoardWidget, DrillPanel, AddWidgetDialog, AiChatDialog, HistoryPanel, ShareDialog };
    static props = ["*"];

    setup() {
        this.data = useService("levelix_board.data");
        this.action = useService("action");
        this.theme = useService("levelix_board.theme");
        this.themeState = useState(this.theme.state);
        this.state = useState({
            view: "list", boards: [], board: null, error: null, loading: true, reloadKey: 0, drill: null,
            filters: {}, options: {}, custom: {}, customOn: {}, cross: null,
            edit: null, panel: "", confirm: "", notice: "", busy: false, aiChats: [],
        });
        this.gridRef = useRef("grid");
        this.sheetRef = useRef("sheet");
        this.editor = new BoardEditor(this);
        onWillStart(async () => {
            await this.showList();
            const context = (this.props.action && this.props.action.context) || {};
            const params = (this.props.action && this.props.action.params) || {};
            const boardId = context.board_id || params.board_id;
            if (boardId) {
                await this.open(boardId);
            }
        });
    }

    async showList() {
        this.state.view = "list";
        this.state.board = null;
        this.state.edit = null;
        this.state.panel = "";
        this.state.drill = null;
        this.state.error = null;
        try {
            this.state.boards = await this.data.list();
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
        this.state.loading = false;
    }

    async open(boardId) {
        this.state.error = null;
        this.state.drill = null;
        this.state.cross = null;
        this.state.edit = null;
        this.state.panel = "";
        this.state.confirm = "";
        this.state.notice = "";
        try {
            this.state.board = await this.data.load(boardId);
            this.state.filters = startingChoices(this.state.board.spec.filters);
            this.state.options = {};
            this.state.custom = {};
            this.state.customOn = {};
            this.state.view = "board";
            this.state.reloadKey += 1;
            this.loadOptions();
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
    }

    /** The lists behind the company and choice filters. A failure leaves the list empty; the dashboard still works. */
    async loadOptions() {
        const board = this.state.board;
        for (const filter of board.spec.filters || []) {
            if (filter.type === "date_range" || filter.type === "amount_basis") {
                continue;
            }
            try {
                this.state.options[filter.id] = await this.data.filterOptions(board.id, filter.id);
            } catch {
                this.state.options[filter.id] = [];
            }
        }
    }

    // -- dashboard filters ---------------------------------------------------------------

    get filters() {
        return (this.state.board && this.state.board.spec.filters) || [];
    }

    /** The two ways to read money: the switch of the "Amounts" filter. */
    get bases() {
        return [{ value: "untaxed", label: _t("Without tax") }, { value: "taxed", label: _t("With tax") }];
    }

    setBasis(filter, value) {
        if (this.state.filters[filter.id] !== value) {
            this.state.filters[filter.id] = value;
            this.apply();
        }
    }

    get presets() {
        return PRESETS.map(([value, label]) => ({ value, label: label() }));
    }

    /** What the period control shows: a preset name, or "custom" for a range of the reader's own. */
    periodChoice(filter) {
        const value = this.state.filters[filter.id];
        return this.state.customOn[filter.id] || (value && typeof value === "object") ? "custom" : value || "all";
    }

    setPeriod(filter, choice) {
        this.state.customOn[filter.id] = choice === "custom";
        if (choice === "custom") {
            const range = this.state.custom[filter.id] || {};
            this.state.custom[filter.id] = range;
            this.state.filters[filter.id] = this.rangeOf(range); // nothing typed yet: no limit until a date is chosen
        } else {
            this.state.filters[filter.id] = choice;
        }
        this.apply();
    }

    setCustom(filter, edge, value) {
        const range = { ...(this.state.custom[filter.id] || {}), [edge]: value || undefined };
        this.state.custom[filter.id] = range;
        this.state.filters[filter.id] = this.rangeOf(range);
        this.apply();
    }

    rangeOf(range) {
        const out = {};
        if (range.from) {
            out.from = range.from;
        }
        if (range.to) {
            out.to = range.to;
        }
        return Object.keys(out).length ? out : "all";
    }

    setChoice(filter, index) {
        const option = index >= 0 ? this.state.options[filter.id][index] : null;
        this.state.filters[filter.id] = option ? option.value : null;
        this.apply();
    }

    chosenIndex(filter) {
        const value = this.state.filters[filter.id];
        const list = this.state.options[filter.id] || [];
        return value === null || value === undefined ? -1 : list.findIndex((o) => o.value === value);
    }

    toggleCompany(filter, id) {
        const now = this.state.filters[filter.id] || [];
        this.state.filters[filter.id] = now.includes(id) ? now.filter((c) => c !== id) : [...now, id];
        this.apply();
    }

    isCompanyOn(filter, id) {
        return (this.state.filters[filter.id] || []).includes(id);
    }

    /** A choice changed: every widget asks again, with the new choice. */
    apply() {
        this.state.drill = null;
        this.state.reloadKey += 1;
    }

    // -- cross-filtering --------------------------------------------------------------------

    /** The same group clicked twice lifts the filter. */
    toggleCross(request) {
        const same = this.state.cross && this.state.cross.widget_id === request.widgetId
            && JSON.stringify(this.state.cross.group_ref) === JSON.stringify(request.groupRef);
        this.state.cross = same ? null : { widget_id: request.widgetId, group_ref: request.groupRef, title: request.title, label: request.label };
        this.apply();
    }

    clearCross() {
        this.state.cross = null;
        this.apply();
    }

    /** What the server gets: the widget and group, nothing the reader typed. */
    get crossRequest() {
        const cross = this.state.cross;
        return cross ? { widget_id: cross.widget_id, group_ref: cross.group_ref } : null;
    }

    refresh() {
        this.state.reloadKey += 1;
    }

    get gridElement() {
        return this.gridRef.el;
    }

    /** May this reader change, share, archive it? (The owner and board managers; the server decides, this only hides buttons.) */
    get canEdit() {
        return Boolean(this.state.board && this.state.board.can_edit);
    }

    /** Editing needs room: on a phone-sized screen the widgets sit in one column and cannot be placed. */
    get canEditHere() {
        return this.canEdit && window.innerWidth >= MOBILE_BREAKPOINT_PX;
    }

    /** The AI chat is a separate app; the button shows only where it is installed. */
    get canAskAi() {
        return registry.category("actions").contains("levelix_ai_core.chat");
    }

    /**
     * Open the chat about this dashboard. When the dashboard has chats (the one that made it, earlier ones), a small dialog asks first:
     * continue one of them, or start a new chat. (The chat is a page of its own, so it is never "open" next to a dashboard.)
     */
    async askAi() {
        const board = this.state.board;
        const chat = this.env.services["levelix_ai.chat"];
        if (chat) {
            try {
                const chats = await chat.pinnedChats("levelix.board", board.id);
                if (chats.length) {
                    this.state.aiChats = chats;
                    this.state.panel = "ai";
                    return;
                }
            } catch {
                // the question is a courtesy: without it a new chat opens
            }
        }
        this.openChat();
    }

    pickChat(chat) {
        this.state.panel = "";
        this.openChat(chat ? chat.id : null);
    }

    openChat(conversationId = null) {
        const board = this.state.board;
        this.action.doAction({
            type: "ir.actions.client", tag: "levelix_ai_core.chat", name: _t("AI assistant"),
            context: { pin: { model: "levelix.board", id: board.id, label: board.name }, conversation_id: conversationId },
        });
    }

    get editing() {
        return Boolean(this.state.edit);
    }

    /** The dashboard on screen: the editor's copy while editing, else what is stored. */
    get shownSpec() {
        return this.state.edit ? this.state.edit.spec : this.state.board.spec;
    }

    get shareLabel() {
        const mode = this.state.board && this.state.board.share_mode;
        return mode === "company" ? _t("Everyone in the company") : mode === "groups" ? _t("Selected groups") : _t("Only me");
    }

    typesFor(widget) {
        return this.editor.typesFor(widget);
    }

    isDraft(widget) {
        return Boolean(this.state.edit && this.state.edit.draft[widget.id]);
    }

    /** Widgets with their grid cell and mobile reading order. */
    get cells() {
        const widgets = (this.shownSpec.widgets || []);
        const cells = placeWidgets(widgets, defaultSizeOf);
        const order = new Map(mobileOrder(cells).map((cell, index) => [cell.id, index]));
        const byId = new Map(widgets.map((w) => [w.id, w]));
        return cells.map((cell) => ({ widget: byId.get(cell.id), style: gridStyle(cell, order.get(cell.id)) }));
    }

    openDrill(request) {
        // the records are read with the same choices the chart was drawn with
        this.state.drill = {
            ...request, key: `${request.widgetId}:${JSON.stringify(request.groupRef)}`,
            filters: Object.keys(this.state.filters).length ? { ...this.state.filters } : null, cross: this.crossRequest,
        };
    }

    manage() {
        this.action.doAction("levelix_board.action_levelix_board");
    }

    // -- actions on the whole dashboard ---------------------------------------------------------------------------

    async run(call) {
        this.state.busy = true;
        this.state.notice = "";
        try {
            await call();
        } catch (error) {
            this.state.notice = rpcMessage(error);
        }
        this.state.busy = false;
    }

    keep() {
        return this.run(async () => {
            await this.data.activate(this.state.board.id);
            await this.open(this.state.board.id);
        });
    }

    copy() {
        return this.run(async () => {
            const card = await this.data.clone(this.state.board.id);
            await this.open(card.id);
            this.state.notice = _t("This is your own copy. Only you can see it.");
        });
    }

    archive() {
        return this.run(async () => {
            await this.data.archive(this.state.board.id);
            this.state.confirm = "";
            await this.showList();
        });
    }

    closePanel() {
        this.state.panel = "";
    }

    onShared(card) {
        Object.assign(this.state.board, { share_mode: card.share_mode });
        this.state.board.group_ids = card.group_ids || this.state.board.group_ids;
        this.state.panel = "";
        this.open(this.state.board.id);
    }

    onRestored() {
        this.state.panel = "";
        this.open(this.state.board.id);
    }

    /** The page as a picture: the title, the chosen filters and every widget, as they look now. Made in the browser, nothing is sent anywhere. */
    exportPng() {
        return this.run(async () => {
            await loadJS("/levelix_board/static/lib/html_to_image/html-to-image.min.js");
            const sheet = this.sheetRef.el;
            const root = sheet.closest(".lxb");
            sheet.classList.add("lxb-sheet--export");
            try {
                const background = getComputedStyle(root).getPropertyValue("--lxb-bg").trim() || "#ffffff";
                const url = await window.htmlToImage.toPng(sheet, { pixelRatio: 2, backgroundColor: background, cacheBust: true });
                const link = document.createElement("a");
                link.download = `${(this.state.board.name || "dashboard").replace(/[^\w\-]+/g, "_")}.png`;
                link.href = url;
                link.click();
            } finally {
                sheet.classList.remove("lxb-sheet--export");
            }
        });
    }
}

registry.category("actions").add("levelix_board.board_page", BoardPage);
