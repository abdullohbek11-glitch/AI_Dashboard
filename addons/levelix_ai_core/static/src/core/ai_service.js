/** @odoo-module **/
import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { choiceToQuestion, reduceEvent, statusText } from "../lib/chat_state.js";

const MODEL = "levelix.ai.conversation";
// silence on the socket for this long means: fetch the stored answer instead
const WATCHDOG_MS = 15000;

/** The chat's state and its only door to the server. Components draw `state`; they never call RPCs. */
export const aiChatService = {
    dependencies: ["orm", "bus_service", "action"],

    start(env, { orm, bus_service: bus, action }) {
        const state = reactive({
            loaded: false,
            configured: true,
            isAdmin: false,
            privacy: "aggregates",
            suggestions: [],
            conversations: [],
            conversation: null,
            messages: [],
            busy: false,
            status: "",
            error: "",
        });
        let lastEvent = 0;
        let watchdog;

        function finish() {
            state.busy = false;
            state.status = "";
            browser.clearInterval(watchdog);
        }

        bus.subscribe("levelix_ai/event", (payload) => {
            const index = state.messages.findIndex((m) => m.id === payload.message_id);
            if (index < 0) {
                return;
            }
            lastEvent = Date.now();
            const step = reduceEvent(state.messages[index], payload, (p) => statusText(p, _t));
            state.messages[index] = step.message;
            if (step.status !== null) {
                state.status = step.status;
            }
            if (step.done) {
                finish();
            }
        });
        bus.start();

        async function load(conversationId) {
            const data = await orm.call(MODEL, "lx_load", [[conversationId]]);
            state.conversation = data.conversation;
            state.messages = data.messages;
            const streaming = data.messages.some((m) => m.state === "streaming");
            if (!streaming) {
                finish();
            }
            return streaming;
        }

        const api = {
            state,
            async bootstrap() {
                const data = await orm.call(MODEL, "lx_bootstrap", [{}]);
                Object.assign(state, {
                    loaded: true,
                    configured: data.configured,
                    isAdmin: data.is_admin,
                    privacy: data.privacy,
                    suggestions: data.suggestions,
                    conversations: data.conversations,
                });
            },
            newChat() {
                state.conversation = null;
                state.messages = [];
                state.error = "";
                finish();
            },
            async openConversation(id) {
                finish();
                state.error = "";
                state.busy = await load(id);
            },
            async archive(id) {
                await orm.call(MODEL, "lx_archive", [[id]]);
                state.conversations = state.conversations.filter((c) => c.id !== id);
                if (state.conversation?.id === id) {
                    api.newChat();
                }
            },
            /** Ask a question. A failure to start (no key, limit reached...) lands in `state.error`. */
            async send(text, mentions = [], choice = false) {
                text = (text || "").trim();
                if (!text || state.busy) {
                    return;
                }
                state.error = "";
                state.busy = true;
                state.status = _t("Thinking…");
                try {
                    const data = await orm.call(MODEL, "lx_send", [state.conversation?.id || false, text, { mentions, choice }]);
                    if (!state.conversation) {
                        state.conversations.unshift(data.conversation);
                    }
                    state.conversation = data.conversation;
                    state.messages.push(...data.messages);
                } catch (error) {
                    finish();
                    state.error = error?.data?.message || error?.message || String(error);
                    return;
                }
                // if the socket drops, the answer is still stored: fetch it
                lastEvent = Date.now();
                browser.clearInterval(watchdog);
                watchdog = browser.setInterval(() => {
                    if (state.busy && state.conversation && Date.now() - lastEvent > WATCHDOG_MS) {
                        lastEvent = Date.now();
                        load(state.conversation.id);
                    }
                }, 5000);
            },
            /** A button the assistant offered was pressed: the choice becomes the next question. */
            choose(option) {
                const question = choiceToQuestion(option);
                return api.send(question.text, question.mentions, true);
            },
            /** Open the full list behind an answer, filtered the same way. */
            openSpec(spec, title) {
                return action.doAction({
                    type: "ir.actions.act_window",
                    name: title,
                    res_model: spec.model,
                    domain: spec.domain,
                    views: [[false, "list"], [false, "form"]],
                    target: "current",
                });
            },
            openSettings() {
                return action.doAction("levelix_ai_core.action_levelix_ai_settings");
            },
        };
        return api;
    },
};

registry.category("services").add("levelix_ai.chat", aiChatService);
