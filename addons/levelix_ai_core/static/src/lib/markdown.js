/** @odoo-module **/
// A small, safe Markdown reader for model answers. Everything is HTML-escaped FIRST and only then are
// our own tags added, so text from the model (or from data it read) can never become markup.
// Supported: paragraphs, line breaks, **bold**, *italic*, `code`, "- " / "1. " lists, "#" headings.
// Links and images are deliberately not supported.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(text) {
    return String(text ?? "").replace(/[&<>"']/g, (c) => ESCAPES[c]);
}

function inline(escaped) {
    return escaped
        .replace(/`([^`\n]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^*\w])\*(?=\S)([^*\n]*?[^\s*])\*(?!\w)/g, "$1<em>$2</em>");
}

export function renderMarkdown(text) {
    const lines = escapeHtml(text || "").replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let list = null; // { tag, items }
    let paragraph = [];
    const flushParagraph = () => {
        if (paragraph.length) {
            out.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
            paragraph = [];
        }
    };
    const flushList = () => {
        if (list) {
            out.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`);
            list = null;
        }
    };
    for (const line of lines) {
        const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
        const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
        const heading = /^\s*#{1,6}\s+(.*)$/.exec(line);
        if (bullet || numbered) {
            flushParagraph();
            const tag = bullet ? "ul" : "ol";
            if (list && list.tag !== tag) {
                flushList();
            }
            list = list || { tag, items: [] };
            list.items.push((bullet || numbered)[1]);
        } else if (heading) {
            flushParagraph();
            flushList();
            out.push(`<p><strong>${inline(heading[1])}</strong></p>`);
        } else if (!line.trim()) {
            flushParagraph();
            flushList();
        } else {
            flushList();
            paragraph.push(line);
        }
    }
    flushParagraph();
    flushList();
    return out.join("");
}
