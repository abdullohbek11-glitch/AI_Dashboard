/** @odoo-module **/
import { registry } from "@web/core/registry";
import { createBatcher } from "../lib/batcher.js";

const MODEL = "levelix.board";
const MAX_BATCHERS = 24;

/** Message of a failed RPC (UserError text for our own errors). */
export function rpcMessage(error) {
    return (error && error.data && error.data.message) || (error && error.message) || String(error);
}

/** The only place that talks to the server. Components never build RPCs themselves. */
export class BoardData {
    constructor(orm) {
        this.orm = orm;
        this.batchers = new Map();
    }

    list() {
        return this.orm.call(MODEL, "lx_list", []);
    }

    load(boardId) {
        return this.orm.call(MODEL, "lx_load", [boardId]);
    }

    /**
     * Widgets that ask within the same moment (e.g. all visible ones) share one `lx_run`, as long as they ask with the same
     * dashboard filters and cross-filter. `filters` maps a filter id to the reader's choice; `cross` is `{widget_id, group_ref}`.
     */
    runWidget(boardId, widgetId, filters = null, cross = null) {
        const key = JSON.stringify([boardId, filters, cross]);
        if (!this.batchers.has(key)) {
            if (this.batchers.size >= MAX_BATCHERS) { // old choices are not asked again
                this.batchers.delete(this.batchers.keys().next().value);
            }
            this.batchers.set(key, createBatcher(async (widgetIds) => {
                const out = await this.orm.call(MODEL, "lx_run", [boardId, widgetIds, filters, false, cross]);
                return out.widgets;
            }));
        }
        return this.batchers.get(key).request(widgetId);
    }

    /** `groupRef` is the `meta.group_refs` entry of the clicked row; the server rebuilds the filter itself. */
    drill(boardId, widgetId, groupRef, filters = null, cross = null) {
        return this.orm.call(MODEL, "lx_drill", [boardId, widgetId, groupRef, filters, cross]);
    }

    async explain(boardId, widgetId, filters = null, cross = null) {
        const out = await this.orm.call(MODEL, "lx_explain", [boardId, [widgetId], filters, cross]);
        return out[widgetId];
    }

    // -- changing a dashboard ----------------------------------------------------------------------------------

    /** `base` is the version the editor started from: a newer stored version refuses the save instead of overwriting it. */
    save(boardId, spec, note, base) {
        return this.orm.call(MODEL, "lx_save", [boardId, spec, note || null, base]);
    }

    saveLayout(boardId, layout, base) {
        return this.orm.call(MODEL, "lx_save_layout", [boardId, layout, base]);
    }

    versions(boardId) {
        return this.orm.call(MODEL, "lx_versions", [boardId]);
    }

    restore(boardId, version, base) {
        return this.orm.call(MODEL, "lx_restore", [boardId, version, base]);
    }

    shareOptions() {
        return this.orm.call(MODEL, "lx_share_options", []);
    }

    share(boardId, mode, groupIds) {
        return this.orm.call(MODEL, "lx_share", [boardId, mode, groupIds || null]);
    }

    clone(boardId, name) {
        return this.orm.call(MODEL, "lx_clone", [boardId, name || null]);
    }

    archive(boardId) {
        return this.orm.call(MODEL, "lx_archive", [boardId]);
    }

    activate(boardId) {
        return this.orm.call(MODEL, "lx_activate", [boardId]);
    }

    meta() {
        return this.orm.call(MODEL, "lx_meta", []);
    }

    sources() {
        return this.orm.call(MODEL, "lx_sources", []);
    }

    fields(model) {
        return this.orm.call(MODEL, "lx_fields", [model]);
    }

    /** A widget that is not saved yet (new, or its type was changed), run with the caller's rights. */
    previewWidget(widget) {
        return this.orm.call(MODEL, "lx_preview_widget", [widget]);
    }

    /** What a reader may choose from for a company or choice filter: `[{value, label}]`. */
    filterOptions(boardId, filterId, query = "") {
        return this.orm.call(MODEL, "lx_filter_options", [boardId, filterId, query]);
    }
}

export const boardDataService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        return new BoardData(orm);
    },
};

registry.category("services").add("levelix_board.data", boardDataService);
