/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ExplainPanel } from "../../explain/explain_panel.js";
import { isEmptyFrame, isDrillableRow, groupRefAt } from "../../lib/frame_model.js";
import { rpcMessage } from "../../core/board_data.js";
import { definitionFor } from "../widget_registry.js";

/**
 * The card around every widget: title, loading / empty / error states, the explain button.
 * It loads its data only when it scrolls into view, and a failure stays inside the card.
 */
export class BoardWidget extends Component {
    static template = "levelix_board.BoardWidget";
    static components = { ExplainPanel };
    static props = {
        boardId: Number,
        widget: Object,
        reloadKey: Number,
        onDrill: Function,
        style: { type: String, optional: true },
    };

    setup() {
        this.data = useService("levelix_board.data");
        this.root = useRef("root");
        this.state = useState({ status: "idle", frame: null, error: null, explain: null });
        this.visible = false;
        this.requestId = 0;

        onMounted(() => {
            this.observer = new IntersectionObserver((entries) => {
                if (!this.visible && entries.some((e) => e.isIntersecting)) {
                    this.visible = true;
                    this.observer.disconnect();
                    this.load();
                }
            }, { rootMargin: "200px" });
            this.observer.observe(this.root.el);
        });
        onWillUnmount(() => this.observer?.disconnect());
        useEffect(
            () => {
                if (this.visible) {
                    this.load();
                }
            },
            () => [this.props.reloadKey]
        );
    }

    get definition() {
        return definitionFor(this.props.widget.type);
    }

    get title() {
        return this.props.widget.title || this.props.widget.id;
    }

    get bodyProps() {
        const definition = this.definition;
        return {
            frame: this.state.frame,
            widget: this.props.widget,
            kind: definition.kind,
            adapter: definition.adapter(this.props.widget),
            onRowClick: this.canDrill ? (rowIndex) => this.drill(rowIndex) : undefined,
        };
    }

    get canDrill() {
        const click = (this.props.widget.interact || {}).on_click;
        return Boolean(click && click.action === "drill");
    }

    get isEmpty() {
        return this.state.frame && isEmptyFrame(this.state.frame);
    }

    get warnings() {
        return (this.state.frame && this.state.frame.meta.warnings) || [];
    }

    get noAccess() {
        return this.state.error && this.state.error.code === "NO_ACCESS";
    }

    /** Trying again cannot fix a missing right or a widget type this version does not know. */
    get canRetry() {
        return !["NO_ACCESS", "UNKNOWN_TYPE"].includes(this.state.error && this.state.error.code);
    }

    async load() {
        if (!this.definition) {
            this.state.error = { code: "UNKNOWN_TYPE", message: `The widget type '${this.props.widget.type}' cannot be shown yet.` };
            this.state.status = "error";
            return;
        }
        const requestId = ++this.requestId;
        this.state.status = "loading";
        this.state.explain = null;
        try {
            const result = await this.data.runWidget(this.props.boardId, this.props.widget.id);
            if (requestId !== this.requestId) {
                return;
            }
            if (result && result.frame) {
                this.state.frame = result.frame;
                this.state.error = null;
                this.state.status = "ready";
            } else {
                this.state.error = (result && result.error) || { code: "UNKNOWN", message: "No answer from the server." };
                this.state.status = "error";
            }
        } catch (error) {
            if (requestId === this.requestId) {
                this.state.error = { code: "RPC", message: rpcMessage(error) };
                this.state.status = "error";
            }
        }
    }

    drill(rowIndex) {
        const frame = this.state.frame;
        if (!isDrillableRow(frame, rowIndex)) {
            return;
        }
        const dims = frame.columns.filter((c) => c.role === "dimension").length;
        this.props.onDrill({
            widgetId: this.props.widget.id,
            title: this.title,
            groupRef: groupRefAt(frame, rowIndex),
            label: frame.rows[rowIndex].slice(0, dims).join(" · "),
        });
    }

    async toggleExplain() {
        if (this.state.explain) {
            this.state.explain = null;
            return;
        }
        try {
            const result = await this.data.explain(this.props.boardId, this.props.widget.id);
            this.state.explain = result.explain || [{ kind: "warning", text: (result.error && result.error.message) || "", detail: false }];
        } catch (error) {
            this.state.explain = [{ kind: "warning", text: rpcMessage(error), detail: false }];
        }
    }
}
