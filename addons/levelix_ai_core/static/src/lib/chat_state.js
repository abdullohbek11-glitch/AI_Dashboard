/** @odoo-module **/
// How a streamed answer builds up. Pure: the service feeds events in, the component draws the result.

/** Bus event of the engine -> changes to apply to the answer message (and to the chat status line). */
export function reduceEvent(message, payload, statusFor = (p) => p.tool || "") {
    switch (payload.kind) {
        case "delta":
            return { message: { ...message, text: message.text + payload.text }, status: "", done: false };
        case "reset": // text before a tool call is working notes, not the answer
            return { message: { ...message, text: "" }, status: null, done: false };
        case "status":
            return { message, status: statusFor(payload), done: false };
        case "done":
            return { message: { ...message, ...payload.message }, status: "", done: true };
        default:
            return { message, status: null, done: false };
    }
}

/** Plain words for what the assistant is doing, by tool. `t` translates. */
export function statusText(payload, t = (s) => s) {
    switch (payload.tool) {
        case "find_models":
        case "describe_model":
            return t("Finding where this data lives…");
        case "aggregate":
            return t("Calculating…");
        case "search_records":
            return t("Reading records…");
        case "pick_record":
        case "ask_user":
            return t("Preparing a question for you…");
        default:
            return t("Working…");
    }
}

/** Is a message still being written (and not abandoned)? */
export function isStreaming(message) {
    return message.state === "streaming";
}

/** The chosen answer to a question the assistant asked on screen: the text to send, and the record to mention. */
export function choiceToQuestion(option) {
    return { text: option.text || option.label, mentions: option.mention ? [option.mention] : [] };
}
