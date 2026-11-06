/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { rpcMessage } from "../core/board_data.js";
import { placeWidgets } from "../lib/grid.js";
import { appended, cellsMoved, gridOf, moved, pitchOf, resized } from "../lib/layout.js";
import { defaultSizeOf } from "../widgets/widget_registry.js";

const STALE = "changed since you opened it";

const clone = (value) => JSON.parse(JSON.stringify(value));
const withoutGrid = (widget) => {
    const { grid, ...rest } = widget; // eslint-disable-line no-unused-vars
    return rest;
};

/**
 * Editing a dashboard by hand: move, resize, rename, retype, remove, add. The editor works on a COPY of the spec; nothing is
 * stored until Save, and Save names the version it started from so a change made meanwhile by someone else is never overwritten.
 */
export class BoardEditor {
    constructor(page) {
        this.page = page;
    }

    get state() {
        return this.page.state;
    }

    get edit() {
        return this.state.edit;
    }

    get active() {
        return Boolean(this.state.edit);
    }

    // -- starting and leaving ---------------------------------------------------------------------------------

    async start() {
        const board = this.state.board;
        const spec = clone(board.spec);
        const cells = placeWidgets(spec.widgets, defaultSizeOf);
        const grid = gridOf(cells);
        spec.widgets.forEach((widget) => (widget.grid = grid[widget.id]));
        this.state.drill = null;
        this.state.cross = null;
        this.state.edit = { spec, base: board.version, draft: {}, saving: false, error: "", stale: false, adding: false, dirty: false, confirmCancel: false, meta: null };
        try {
            this.state.edit.meta = await this.page.data.meta();
        } catch (error) {
            this.state.edit.error = rpcMessage(error);
        }
        this.page.apply();
    }

    cancel(force = false) {
        if (this.edit && this.edit.dirty && !force) {
            this.edit.confirmCancel = true;
            return;
        }
        this.state.edit = null;
        this.page.apply();
    }

    // -- the places ----------------------------------------------------------------------------------------------

    cells() {
        return placeWidgets(this.edit.spec.widgets, defaultSizeOf);
    }

    setCells(cells) {
        const grid = gridOf(cells);
        for (const widget of this.edit.spec.widgets) {
            const next = grid[widget.id];
            const now = widget.grid;
            if (next && (!now || now.x !== next.x || now.y !== next.y || now.w !== next.w || now.h !== next.h)) {
                widget.grid = next;
                this.edit.dirty = true;
            }
        }
    }

    /** Pointer down on a drag handle or a resize corner: the widget follows the pointer in whole grid cells until it is let go. */
    dragStart(event, widgetId, kind) {
        event.preventDefault();
        const gridElement = this.page.gridElement;
        if (!gridElement) {
            return;
        }
        const pitch = pitchOf(gridElement.getBoundingClientRect().width, parseFloat(getComputedStyle(gridElement).columnGap) || 16);
        const origin = { x: event.clientX, y: event.clientY };
        const start = this.cells();
        const onMove = (move) => {
            const { dx, dy } = cellsMoved(move.clientX - origin.x, move.clientY - origin.y, pitch);
            this.setCells(kind === "move" ? moved(start, widgetId, dx, dy) : resized(start, widgetId, dx, dy));
        };
        const onUp = () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            window.removeEventListener("pointercancel", onUp);
        };
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
    }

    // -- one widget ---------------------------------------------------------------------------------------------------

    widget(id) {
        return this.edit.spec.widgets.find((w) => w.id === id);
    }

    rename(id, value) {
        const widget = this.widget(id);
        const title = String(value || "").trim().slice(0, 80);
        if (widget && title && widget.title !== title) {
            widget.title = title;
            this.edit.dirty = true;
        }
    }

    /** The types a widget could become: those that take as many axes and measures as it has. The server checks the rest. */
    typesFor(widget) {
        const shapes = this.edit && this.edit.meta && this.edit.meta.shapes;
        if (!shapes) {
            return [widget.type];
        }
        const dims = (widget.data.dimensions || []).length;
        const measures = (widget.data.measures || []).length;
        const fits = Object.keys(shapes).filter((type) => {
            const { dimensions, measures: m } = shapes[type];
            return dims >= dimensions[0] && dims <= dimensions[1] && measures >= m[0] && measures <= m[1];
        });
        return fits.includes(widget.type) ? fits : [widget.type, ...fits];
    }

    retype(id, type) {
        const widget = this.widget(id);
        if (widget && widget.type !== type) {
            widget.type = type;
            widget.view = {}; // the options of one type mean nothing to another
            this.edit.draft[id] = true; // it is drawn from the editor's copy until saved
            this.edit.dirty = true;
        }
    }

    remove(id) {
        const edit = this.edit;
        edit.spec.widgets = edit.spec.widgets.filter((w) => w.id !== id);
        delete edit.draft[id];
        this.setCells(this.cells());
        edit.dirty = true;
    }

    add(widget) {
        const edit = this.edit;
        const cells = appended(this.cells(), widget.id, defaultSizeOf(widget));
        edit.spec.widgets.push(widget);
        edit.draft[widget.id] = true;
        this.setCells(cells);
        edit.adding = false;
        edit.dirty = true;
    }

    nextId() {
        const used = new Set(this.edit.spec.widgets.map((w) => w.id));
        let n = used.size + 1;
        while (used.has(`w${n}`)) {
            n += 1;
        }
        return `w${n}`;
    }

    // -- saving ----------------------------------------------------------------------------------------------------------

    /** Only the places changed? Then the history says "Layout changed" instead of a vague edit. */
    get layoutOnly() {
        const stored = this.state.board.spec;
        const mine = this.edit.spec;
        return (
            mine.widgets.length === stored.widgets.length &&
            mine.widgets.every((w, i) => stored.widgets[i].id === w.id && JSON.stringify(withoutGrid(w)) === JSON.stringify(withoutGrid(stored.widgets[i])))
        );
    }

    async save() {
        const edit = this.edit;
        const board = this.state.board;
        edit.saving = true;
        edit.error = "";
        edit.stale = false;
        try {
            if (this.layoutOnly) {
                await this.page.data.saveLayout(board.id, gridOf(this.cells()), edit.base);
            } else {
                await this.page.data.save(board.id, edit.spec, _t("Edited by hand"), edit.base);
            }
        } catch (error) {
            const message = rpcMessage(error);
            edit.error = message;
            edit.stale = message.includes(STALE);
            edit.saving = false;
            return;
        }
        this.state.edit = null;
        await this.page.open(board.id);
    }

    /** Someone else saved meanwhile: drop the edit and show what is stored now. */
    async reload() {
        const id = this.state.board.id;
        this.state.edit = null;
        await this.page.open(id);
    }
}

