/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { rpcMessage } from "../core/board_data.js";

const GRANULARITIES = ["day", "week", "month", "quarter", "year"];
const TIME_TYPES = ["line", "area"];

/**
 * "Add a widget" without the assistant: pick a type, a source, what to group by and what to measure, look at a preview, add.
 * The server checks the widget as the user (the preview is that check), so what can be added is always valid.
 */
export class AddWidgetDialog extends Component {
    static template = "levelix_board.AddWidgetDialog";
    static props = { shapes: Object, nextId: Function, onAdd: Function, onClose: Function };

    setup() {
        this.data = useService("levelix_board.data");
        this.granularities = GRANULARITIES;
        this.state = useState({
            sources: [], model: "", fields: null, type: "bar", title: "", dim: "", gran: "month", measure1: "__count", agg1: "count", measure2: "", agg2: "sum",
            status: "", target: "", preview: null, error: "", busy: false,
        });
        onWillStart(async () => {
            try {
                this.state.sources = await this.data.sources();
                if (this.state.sources.length) {
                    await this.pickSource(this.state.sources[0].model);
                }
            } catch (error) {
                this.state.error = rpcMessage(error);
            }
        });
    }

    get types() {
        return Object.keys(this.props.shapes);
    }

    get shape() {
        return this.props.shapes[this.state.type];
    }

    get needsDimension() {
        return this.shape.dimensions[0] >= 1;
    }

    get needsSecondMeasure() {
        return this.shape.measures[0] >= 2;
    }

    /** Which fields may be the axis: a date for a line or an area, a date for a heat map, anything else for the rest. */
    get dimensionChoices() {
        const all = (this.state.fields && this.state.fields.dimensions) || [];
        return TIME_TYPES.includes(this.state.type) || this.state.type === "heatmap" ? all.filter((d) => ["date", "datetime"].includes(d.type)) : all;
    }

    get measureChoices() {
        return (this.state.fields && this.state.fields.measures) || [];
    }

    isDate(name) {
        const found = ((this.state.fields && this.state.fields.dimensions) || []).find((d) => d.name === name);
        return Boolean(found && ["date", "datetime"].includes(found.type));
    }

    aggregatesOf(name) {
        const found = this.measureChoices.find((m) => m.name === name);
        return found ? found.aggregates.filter((a) => ["sum", "avg", "min", "max", "count_distinct"].includes(a)) : [];
    }

    async pickSource(model) {
        this.state.model = model;
        this.state.preview = null;
        this.state.error = "";
        try {
            this.state.fields = await this.data.fields(model);
        } catch (error) {
            this.state.fields = null;
            this.state.error = rpcMessage(error);
            return;
        }
        this.state.dim = this.dimensionChoices[0] ? this.dimensionChoices[0].name : "";
        this.state.status = "";
        const first = this.measureChoices[0];
        this.state.measure2 = first ? first.name : "";
        this.state.agg2 = first ? this.aggregatesOf(first.name)[0] || "sum" : "sum";
    }

    changeType(type) {
        this.state.type = type;
        this.state.preview = null;
        if (!this.dimensionChoices.some((d) => d.name === this.state.dim)) {
            this.state.dim = this.dimensionChoices[0] ? this.dimensionChoices[0].name : "";
        }
    }

    pickMeasure(which, name) {
        const aggs = this.aggregatesOf(name);
        if (which === 1) {
            this.state.measure1 = name;
            this.state.agg1 = name === "__count" ? "count" : aggs[0] || "sum";
        } else {
            this.state.measure2 = name;
            this.state.agg2 = aggs[0] || "sum";
        }
        this.state.preview = null;
    }

    measure(id, name, agg) {
        return name === "__count" ? { id, agg: "count" } : { id, field: name, agg };
    }

    /** The widget as the spec writes it. */
    build() {
        const { type, model, dim, gran, status } = this.state;
        const data = { source: model, domain: status ? [["state", "=", status]] : [], dimensions: [], measures: [this.measure("m1", this.state.measure1, this.state.agg1)] };
        if (this.needsSecondMeasure) {
            data.measures.push(this.measure("m2", this.state.measure2, this.state.agg2));
        }
        const widget = { id: this.props.nextId(), type, title: this.state.title.trim() || _t("New widget"), data };
        if (type === "heatmap") {
            data.dimensions = [{ field: dim, granularity: "day_of_week" }, { field: dim, granularity: "hour_number" }];
        } else if (this.needsDimension) {
            data.dimensions = [this.isDate(dim) ? { field: dim, granularity: gran } : { field: dim }];
            if (this.isDate(dim)) {
                if (TIME_TYPES.includes(type)) {
                    data.fill_gaps = true;
                }
                data.order = { by: dim, dir: "asc" };
            } else {
                data.order = { by: "m1", dir: "desc" };
                if (type !== "pie") { // a pie keeps its biggest slices and groups the rest by itself
                    data.limit = 10;
                }
            }
        }
        if (type === "gauge") {
            widget.view = { target: Number(this.state.target) || 0 };
        } else if (type === "combo") {
            widget.view = { line: "m2" };
        }
        return widget;
    }

    async preview() {
        this.state.busy = true;
        this.state.error = "";
        this.state.preview = null;
        try {
            const result = await this.data.previewWidget(this.build());
            this.state.preview = result.frame
                ? { columns: result.frame.columns.map((c) => c.label), rows: result.frame.rows.slice(0, 5), more: Math.max(0, result.frame.rows.length - 5) }
                : { error: (result.error && result.error.message) || _t("Nothing to show.") };
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
        this.state.busy = false;
    }

    get canAdd() {
        return Boolean(this.state.preview && !this.state.preview.error && !this.state.busy);
    }

    add() {
        this.props.onAdd(this.build());
    }
}
