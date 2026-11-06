/** @odoo-module **/
import { Component } from "@odoo/owl";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";

/** "Change with AI" when this dashboard already has chats: two buttons, the old chat (the one that made it first) or a new chat. */
export class AiChatDialog extends Component {
    static template = "levelix_board.AiChatDialog";
    static props = { chats: Array, onPick: Function, onClose: Function };

    setup() {
        useHotkey("escape", () => this.props.onClose());
    }
}
