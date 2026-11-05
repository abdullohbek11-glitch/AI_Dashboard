/** @odoo-module **/
import { registry } from "@web/core/registry";
import { createBatcher } from "../lib/batcher.js";

const MODEL = "levelix.board";

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

    /** Widgets that ask within the same moment (e.g. all visible ones) share one `lx_run`. */
    runWidget(boardId, widgetId) {
        if (!this.batchers.has(boardId)) {
            this.batchers.set(boardId, createBatcher(async (widgetIds) => {
                const out = await this.orm.call(MODEL, "lx_run", [boardId, widgetIds]);
                return out.widgets;
            }));
        }
        return this.batchers.get(boardId).request(widgetId);
    }

    /** `groupRef` is the `meta.group_refs` entry of the clicked row; the server rebuilds the filter itself. */
    drill(boardId, widgetId, groupRef) {
        return this.orm.call(MODEL, "lx_drill", [boardId, widgetId, groupRef]);
    }

    async explain(boardId, widgetId) {
        const out = await this.orm.call(MODEL, "lx_explain", [boardId, [widgetId]]);
        return out[widgetId];
    }
}

export const boardDataService = {
    dependencies: ["orm"],
    start(env, { orm }) {
        return new BoardData(orm);
    },
};

registry.category("services").add("levelix_board.data", boardDataService);
