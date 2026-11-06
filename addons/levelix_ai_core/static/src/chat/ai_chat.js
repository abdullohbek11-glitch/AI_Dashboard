/** @odoo-module **/
import { Component, markup, onMounted, onPatched, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { blocksRegistry } from "../blocks/blocks.js";
import { renderMarkdown } from "../lib/markdown.js";

/** The conversation: a list of questions and answers, a box to ask in, and the answers' blocks. Reusable anywhere. */
export class AiChat extends Component {
    static template = "levelix_ai_core.AiChat";
    static props = { sidebar: { type: Boolean, optional: true } };

    setup() {
        this.chat = useService("levelix_ai.chat");
        this.state = useState(this.chat.state); // subscribes this component to the service's state
        this.ui = useState({ draft: "", marking: 0, note: "" });
        this.scroller = useRef("scroller");
        this.input = useRef("input");
        onMounted(async () => {
            if (!this.state.loaded) {
                await this.chat.bootstrap();
            }
            this.input.el?.focus();
        });
        onPatched(() => {
            const el = this.scroller.el;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        });
    }

    html(text) {
        return markup(renderMarkdown(text));
    }

    blockComponent(block) {
        return blocksRegistry.contains(block.type) ? blocksRegistry.get(block.type).component : null;
    }

    get privacyLabel() {
        return this.state.privacy === "schema" ? "Structure only" : "Totals shared";
    }

    get privacyHelp() {
        return this.state.privacy === "schema"
            ? "The AI provider sees models and fields, never a value or a name. You still see full results."
            : "The AI provider sees the totals and search results it asks for, never more than you may read.";
    }

    get canAsk() {
        return this.state.configured && !this.state.busy && this.ui.draft.trim().length > 0;
    }

    async submit() {
        if (!this.canAsk) {
            return;
        }
        const text = this.ui.draft;
        this.ui.draft = "";
        if (this.input.el) {
            this.input.el.value = ""; // the state may flip back to "" before OWL has rendered the typed text
        }
        await this.chat.send(text);
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
            ev.preventDefault();
            this.submit();
        }
    }

    /** A block asks to start the next question for the user (for example "Change the dashboard: "). */
    prefill(text) {
        this.ui.draft = text;
        this.input.el?.focus();
    }

    suggest(text) {
        this.ui.draft = text;
        this.submit();
    }

    startMarking(message) {
        this.ui.marking = message.id;
        this.ui.note = "";
    }

    async sendMark(message) {
        await this.chat.markWrong(message, this.ui.note);
        this.ui.marking = 0;
    }

    retry(index) {
        const question = [...this.state.messages.slice(0, index)].reverse().find((m) => m.role === "user");
        if (question) {
            this.chat.send(question.text);
        }
    }
}
