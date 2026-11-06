/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { useService } from "@web/core/utils/hooks";
import { rpcMessage } from "../core/board_data.js";

/** Who else may open the dashboard. Readers calculate with their own rights, so sharing never shows anyone numbers they could not see. */
export class ShareDialog extends Component {
    static template = "levelix_board.ShareDialog";
    static props = { board: Object, onClose: Function, onSaved: Function };

    setup() {
        this.data = useService("levelix_board.data");
        this.state = useState({
            mode: this.props.board.share_mode || "private", groups: [...(this.props.board.group_ids || [])], options: [], error: "", busy: false,
        });
        useHotkey("escape", () => this.props.onClose());
        onWillStart(async () => {
            try {
                this.state.options = await this.data.shareOptions();
            } catch (error) {
                this.state.error = rpcMessage(error);
            }
        });
    }

    get levels() {
        return [
            { value: "private", label: _t("Only me") },
            { value: "groups", label: _t("Selected groups") },
            { value: "company", label: _t("Everyone in the company") },
        ];
    }

    get isDraft() {
        return this.props.board.state === "draft";
    }

    toggle(id) {
        const now = this.state.groups;
        this.state.groups = now.includes(id) ? now.filter((g) => g !== id) : [...now, id];
    }

    get canSave() {
        return !this.state.busy && (this.state.mode !== "groups" || this.state.groups.length > 0);
    }

    async save() {
        this.state.busy = true;
        this.state.error = "";
        try {
            const card = await this.data.share(this.props.board.id, this.state.mode, this.state.mode === "groups" ? this.state.groups : null);
            this.props.onSaved(card);
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
        this.state.busy = false;
    }
}
