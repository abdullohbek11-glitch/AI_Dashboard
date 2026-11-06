/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { blocksRegistry } from "@levelix_ai_core/blocks/blocks";
import { BoardWidget } from "@levelix_board/widgets/shell/board_widget";

const noop = () => {};

/**
 * The dashboard the assistant built, drawn live (the same widgets as the dashboard page) with the buttons:
 * Keep, Change, and the options the assistant was unsure about. The draft is a real record: leaving the chat loses nothing.
 */
export class BoardDraftBlock extends Component {
    static template = "levelix_ai_board.BoardDraftBlock";
    static components = { BoardWidget };
    static props = {
        block: Object,
        onOpen: { type: Function, optional: true },
        onChoose: { type: Function, optional: true },
        onPrefill: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.theme = useService("levelix_board.theme");
        this.themeState = useState(this.theme.state);
        this.noop = noop;
        this.state = useState({ board: null, error: "", busy: false, reloadKey: 1 });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.board = await this.orm.call("levelix.board", "lx_load", [this.props.block.board_id]);
            this.state.error = "";
        } catch (error) {
            this.state.board = null;
            this.state.error = _t("This dashboard no longer exists or you cannot see it.");
        }
    }

    get board() {
        return this.state.board;
    }

    get saved() {
        return Boolean(this.board) && this.board.state === "active";
    }

    get uncertain() {
        return (this.board && this.board.spec.uncertain) || [];
    }

    async run(call) {
        this.state.busy = true;
        try {
            await call();
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || String(error);
        }
        this.state.busy = false;
    }

    keep() {
        return this.run(async () => {
            await this.orm.call("levelix.board", "lx_activate", [this.board.id]);
            await this.load();
        });
    }

    applyOption(index) {
        return this.run(async () => {
            await this.orm.call("levelix.board", "lx_apply_uncertain", [this.board.id, index]);
            await this.load();
            this.state.reloadKey += 1; // the widgets run again with the changed spec
        });
    }

    change() {
        this.props.onPrefill?.(_t("Change the dashboard: "));
    }

    open() {
        return this.action.doAction({ type: "ir.actions.client", tag: "levelix_board.board_page", name: this.board.name, context: { board_id: this.board.id } });
    }
}

/** "What I did", in plain words, written by the server from the query that really ran. Important lines first, the rest under Details. */
export class BoardExplainBlock extends Component {
    static template = "levelix_ai_board.BoardExplainBlock";
    static props = {
        block: Object,
        onOpen: { type: Function, optional: true },
        onChoose: { type: Function, optional: true },
        onPrefill: { type: Function, optional: true },
    };

    important(widget) {
        return widget.lines.filter((line) => !line.detail);
    }

    details(widget) {
        return widget.lines.filter((line) => line.detail);
    }
}

/**
 * Under the charts, numbers and tables an answer calculated: "keep this as a dashboard?". Nothing happens until the
 * user presses the button; ignoring it costs nothing. The server makes the dashboard from the query it stored.
 */
export class SaveOfferBlock extends Component {
    static template = "levelix_ai_board.SaveOfferBlock";
    static props = {
        block: Object,
        onOpen: { type: Function, optional: true },
        onChoose: { type: Function, optional: true },
        onPrefill: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ busy: false, error: "", saved: null });
    }

    get savedBoard() {
        if (this.state.saved) {
            return this.state.saved;
        }
        return this.props.block.board_id ? { board_id: this.props.block.board_id, name: "", notes: [] } : null;
    }

    async save() {
        this.state.busy = true;
        this.state.error = "";
        try {
            this.state.saved = await this.orm.call("levelix.board", "lx_save_chat_answer", [this.props.block.message_id]);
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || String(error);
        }
        this.state.busy = false;
    }

    open() {
        const saved = this.savedBoard;
        return this.action.doAction({ type: "ir.actions.client", tag: "levelix_board.board_page", name: saved.name || _t("Dashboard"), context: { board_id: saved.board_id } });
    }
}

blocksRegistry.add("board_draft", { component: BoardDraftBlock });
blocksRegistry.add("save_offer", { component: SaveOfferBlock });
blocksRegistry.add("board_explain", { component: BoardExplainBlock });
