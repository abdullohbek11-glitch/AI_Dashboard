// Pure frontend logic of the chat. Run: node --test addons/levelix_ai_core/tests/js/lib.test.mjs
import assert from "node:assert/strict";
import test from "node:test";

import { choiceToQuestion, isStreaming, reduceEvent, statusText } from "../../static/src/lib/chat_state.js";
import { escapeHtml, renderMarkdown } from "../../static/src/lib/markdown.js";

test("html is escaped before anything else", () => {
    assert.equal(escapeHtml(`<img src=x onerror="a()">&'`), "&lt;img src=x onerror=&quot;a()&quot;&gt;&amp;&#39;");
    const html = renderMarkdown('<script>alert(1)</script> and <b onclick="x">bold</b>');
    assert.ok(!html.includes("<script") && !html.includes("<b "), html);
    assert.ok(html.includes("&lt;script&gt;"));
});

test("markdown: inline formatting", () => {
    assert.equal(renderMarkdown("**Bold** and *soft* and `code`"), "<p><strong>Bold</strong> and <em>soft</em> and <code>code</code></p>");
    assert.equal(renderMarkdown("2 * 3 * 4"), "<p>2 * 3 * 4</p>"); // stars between numbers are not emphasis
    assert.equal(renderMarkdown("snake_case_name"), "<p>snake_case_name</p>");
});

test("markdown: paragraphs, line breaks, lists, headings", () => {
    assert.equal(renderMarkdown("one\ntwo\n\nthree"), "<p>one<br>two</p><p>three</p>");
    assert.equal(renderMarkdown("- a\n- b"), "<ul><li>a</li><li>b</li></ul>");
    assert.equal(renderMarkdown("1. a\n2) b"), "<ol><li>a</li><li>b</li></ol>");
    assert.equal(renderMarkdown("Intro\n- a\n- b\nOutro"), "<p>Intro</p><ul><li>a</li><li>b</li></ul><p>Outro</p>");
    assert.equal(renderMarkdown("Done.\n\n* One more thing."), "<p>Done.</p><p>One more thing.</p>"); // a lone bullet is a sentence
    assert.equal(renderMarkdown("## Title"), "<p><strong>Title</strong></p>");
    assert.equal(renderMarkdown(""), "");
    assert.equal(renderMarkdown(null), "");
});

test("markdown: links and images stay plain text", () => {
    const html = renderMarkdown("[click](javascript:alert(1)) ![x](http://a/b.png)");
    assert.ok(!html.includes("<a ") && !html.includes("<img"), html);
});

test("a streamed answer builds up and ends", () => {
    let message = { id: 1, text: "", state: "streaming" };
    let step = reduceEvent(message, { kind: "status", tool: "aggregate" }, (p) => "doing " + p.tool);
    assert.equal(step.status, "doing aggregate");
    message = reduceEvent(message, { kind: "delta", text: "Hel" }).message;
    message = reduceEvent(message, { kind: "delta", text: "lo" }).message;
    assert.equal(message.text, "Hello");
    assert.equal(reduceEvent(message, { kind: "reset" }).message.text, "");
    step = reduceEvent(message, { kind: "done", message: { text: "Final", state: "done", blocks: [1] } });
    assert.deepEqual([step.message.text, step.message.state, step.done], ["Final", "done", true]);
    assert.equal(reduceEvent(message, { kind: "unknown" }).done, false);
});

test("status words by tool", () => {
    assert.equal(statusText({ tool: "aggregate" }), "Calculating…");
    assert.equal(statusText({ tool: "find_models" }), "Finding where this data lives…");
    assert.equal(statusText({ tool: "something_new" }), "Working…");
    assert.equal(statusText({ tool: "aggregate" }, (s) => s.toUpperCase()), "CALCULATING…");
});

test("streaming and choices", () => {
    assert.equal(isStreaming({ state: "streaming" }), true);
    assert.equal(isStreaming({ state: "done" }), false);
    assert.deepEqual(choiceToQuestion({ label: "Ali", text: "Ali", mention: { model: "res.partner", id: 4 } }), { text: "Ali", mentions: [{ model: "res.partner", id: 4 }] });
    assert.deepEqual(choiceToQuestion({ label: "This month" }), { text: "This month", mentions: [] });
});
