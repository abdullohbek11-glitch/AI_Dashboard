/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { AiChat } from "../chat/ai_chat.js";

/** Full-screen chat: the menu entry. */
export class AiPage extends Component {
    static template = "levelix_ai_core.AiPage";
    static components = { AiChat };
    static props = ["*"];
}

registry.category("actions").add("levelix_ai_core.chat", AiPage);
