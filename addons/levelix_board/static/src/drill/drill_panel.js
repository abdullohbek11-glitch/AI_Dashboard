/** @odoo-module **/
import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { formatFull } from "../lib/format.js";
import { rpcMessage } from "../core/board_data.js";

/** Side panel with the records behind the clicked point; "Open in Odoo" opens the full list with the same filter. */
export class DrillPanel extends Component {
    static template = "levelix_board.DrillPanel";
    static props = { boardId: Number, request: Object, onClose: Function };

    setup() {
        this.data = useService("levelix_board.data");
        this.action = useService("action");
        this.closeButton = useRef("close");
        this.state = useState({ loading: true, error: null, result: null });
        useHotkey("escape", () => this.props.onClose());
        onWillStart(() => this.load());
        onMounted(() => this.closeButton.el && this.closeButton.el.focus());
    }

    async load() {
        const { widgetId, groupRef } = this.props.request;
        try {
            this.state.result = await this.data.drill(this.props.boardId, widgetId, groupRef);
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
        this.state.loading = false;
    }

    isNumber(column) {
        return ["integer", "float", "monetary"].includes(column.type);
    }

    /** Numbers get digit grouping; everything else arrives from the server already readable. */
    cell(column, value) {
        return this.isNumber(column) && typeof value === "number" ? formatFull(value, { lang: user.lang || "en" }) : value;
    }

    openInOdoo() {
        this.action.doAction(this.state.result.action);
    }
}
