/** @odoo-module **/
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { AiChat } from "../chat/ai_chat.js";

/** Full-screen chat: the menu entry. */
export class AiPage extends Component {
    static template = "levelix_ai_core.AiPage";
    static components = { AiChat };
    static props = ["*"];

    setup() {
        this.chat = useService("levelix_ai.chat");
        onWillStart(() => this.openAbout());
    }

    /**
     * Opened from a record ("Change with AI"): action context { pin: { model, id, label }, conversation_id? }. The record's page has
     * already asked what the reader wants: a given conversation_id is opened (and is about the record from now on); otherwise a new chat.
     */
    async openAbout() {
        const context = this.props.action?.context || {};
        const pin = context.pin;
        if (!pin || !pin.model || !Number.isInteger(pin.id)) {
            return;
        }
        const about = { model: pin.model, id: pin.id, label: String(pin.label || "").slice(0, 80) };
        if (Number.isInteger(context.conversation_id)) {
            await this.chat.openConversation(context.conversation_id);
        } else {
            this.chat.newChat();
        }
        this.chat.pin(about);
    }
}

registry.category("actions").add("levelix_ai_core.chat", AiPage);
