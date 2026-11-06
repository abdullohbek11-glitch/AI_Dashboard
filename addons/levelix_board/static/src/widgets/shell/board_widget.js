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
        onCross: { type: Function, optional: true },
        editing: { type: Boolean, optional: true },
        draft: { type: Boolean, optional: true }, // not saved yet: run it from the editor's copy, not from the stored dashboard
        types: { type: Array, optional: true }, // the types this widget could be switched to
        onDragStart: { type: Function, optional: true },
        onRename: { type: Function, optional: true },
        onRetype: { type: Function, optional: true },
        onRemove: { type: Function, optional: true },
        filters: { type: Object, optional: true },
        cross: { optional: true }, // {widget_id, group_ref} or null
        style: { type: String, optional: true },
    };

    setup() {
        this.data = useService("levelix_board.data");
        this.root = useRef("root");
        this.state = useState({ status: "idle", frame: null, error: null, explain: null, titleDraft: null });
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
            onRowClick: this.canClick ? (rowIndex) => this.clicked(rowIndex) : undefined,
        };
    }

    get clickAction() {
        return ((this.props.widget.interact || {}).on_click || {}).action;
    }

    /** A click opens the records behind the point (`drill`) or narrows the other widgets to it (`cross_filter`). */
    get canClick() {
        return ["drill", "cross_filter"].includes(this.clickAction);
    }

    /** This widget is the one the dashboard is currently filtered by. */
    get isCrossSource() {
        return Boolean(this.props.cross && this.props.cross.widget_id === this.props.widget.id);
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
            const result = this.props.draft
                ? await this.data.previewWidget(this.props.widget)
                : await this.data.runWidget(this.props.boardId, this.props.widget.id, this.filterValues, this.props.cross || null);
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

    /** What is being typed in the title box survives a redraw of the card (the data arriving, a filter changing). */
    onTitleInput(event) {
        this.state.titleDraft = event.target.value;
    }

    onTitleChange(event) {
        this.state.titleDraft = null;
        this.props.onRename(this.props.widget.id, event.target.value);
    }

    get filterValues() {
        const values = this.props.filters;
        return values && Object.keys(values).length ? { ...values } : null;
    }

    clicked(rowIndex) {
        const frame = this.state.frame;
        if (!isDrillableRow(frame, rowIndex)) {
            return;
        }
        const dims = frame.columns.filter((c) => c.role === "dimension").length;
        const request = {
            widgetId: this.props.widget.id,
            title: this.title,
            groupRef: groupRefAt(frame, rowIndex),
            label: frame.rows[rowIndex].slice(0, dims).join(" · "),
        };
        if (this.clickAction === "cross_filter") {
            this.props.onCross && this.props.onCross(request);
        } else {
            this.props.onDrill(request);
        }
    }

    async toggleExplain() {
        if (this.state.explain) {
            this.state.explain = null;
            return;
        }
        try {
            const result = await this.data.explain(this.props.boardId, this.props.widget.id, this.filterValues, this.props.cross || null);
            this.state.explain = result.explain || [{ kind: "warning", text: (result.error && result.error.message) || "", detail: false }];
        } catch (error) {
            this.state.explain = [{ kind: "warning", text: rpcMessage(error), detail: false }];
        }
    }
}
