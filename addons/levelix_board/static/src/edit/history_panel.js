/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useService } from "@web/core/utils/hooks";
import { rpcMessage } from "../core/board_data.js";

const ORIGINS = { manual: () => _t("By hand"), ai: () => _t("Assistant"), restore: () => _t("Restored") };

/** Every saved state of the dashboard, newest first, with what changed. Restoring makes a NEW version: nothing is ever lost. */
export class HistoryPanel extends Component {
    static template = "levelix_board.HistoryPanel";
    static props = { boardId: Number, version: Number, onClose: Function, onRestored: Function };

    setup() {
        this.data = useService("levelix_board.data");
        this.state = useState({ loading: true, error: "", rows: [], confirm: 0, busy: false });
        useHotkey("escape", () => this.props.onClose());
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.rows = await this.data.versions(this.props.boardId);
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
        this.state.loading = false;
    }

    origin(row) {
        return (ORIGINS[row.origin] || (() => row.origin))();
    }

    /** What changed, in words: "Added: A, B · Moved: C". */
    summary(row) {
        const c = row.changes;
        const parts = [];
        const list = (label, items) => items.length && parts.push(`${label}: ${items.join(", ")}`);
        list(_t("Added"), c.added);
        list(_t("Removed"), c.removed);
        list(_t("Changed"), c.changed);
        list(_t("Moved"), c.moved);
        if (c.other.length) {
            parts.push(c.other.map((o) => ({ title: _t("Title"), filters: _t("Filters"), notes: _t("Notes") }[o] || o)).join(", "));
        }
        return parts.join(" · ") || _t("No visible change");
    }

    async restore(row) {
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.data.restore(this.props.boardId, row.version, this.props.version);
            this.props.onRestored();
        } catch (error) {
            this.state.error = rpcMessage(error);
            this.state.confirm = 0;
        }
        this.state.busy = false;
    }
}
