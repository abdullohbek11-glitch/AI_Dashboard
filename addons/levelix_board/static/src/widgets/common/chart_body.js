/** @odoo-module **/
import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import {
    comboModel, compareSeries, funnelModel, gaugeModel, heatmapModel, scatterModel, seriesModel, treemapModel, waterfallModel,
} from "../../lib/frame_model.js";

/** The model each type draws from a frame. Line, area, bar and pie share the series model. */
const MODELS = {
    heatmap: (frame, view, lang) => heatmapModel(frame, lang),
    funnel: (frame, view, lang) => funnelModel(frame, lang),
    treemap: (frame, view, lang) => treemapModel(frame, lang),
    waterfall: (frame, view, lang) => waterfallModel(frame, lang),
    scatter: (frame, view, lang) => scatterModel(frame, lang),
    combo: (frame, view, lang) => comboModel(frame, view, lang),
    gauge: (frame, view) => gaugeModel(frame, view),
};

/** Draws a frame as a chart through whichever adapter the widget type asks for. */
export class ChartBody extends Component {
    static template = "levelix_board.ChartBody";
    static props = {
        frame: Object,
        widget: Object,
        kind: String,
        adapter: String, // "chartjs" | "echarts"
        onRowClick: { type: Function, optional: true },
    };

    setup() {
        this.root = useRef("root");
        this.theme = useService("levelix_board.theme");
        this.themeState = useState(this.theme.state);
        this.adapter = null;
        this.generation = 0;
        useEffect(
            () => {
                this.render();
            },
            () => [this.props.frame, this.themeState.mode]
        );
        onWillUnmount(() => {
            this.generation += 1;
            this.observer?.disconnect();
            this.adapter?.dispose();
        });
    }

    get model() {
        const build = MODELS[this.props.kind];
        return build ? build(this.props.frame, this.props.widget.view || {}, user.lang || "en") : seriesModel(this.props.frame);
    }

    /** Text version of the chart for screen readers: the frame as it came. */
    get tableRows() {
        return this.props.frame.rows;
    }

    get columnLabels() {
        return this.props.frame.columns.map((c) => c.label);
    }

    /** The earlier period, as dashed series named after what it is. */
    get compare() {
        const kind = this.props.frame.meta.compare && this.props.frame.meta.compare.kind;
        const name = kind === "previous_year" ? _t("previous year") : _t("previous period");
        return compareSeries(this.props.frame, (label) => `${label} · ${name}`);
    }

    async render() {
        const generation = ++this.generation;
        const host = this.root.el.querySelector(".lxb-chart__canvas");
        const model = this.model;
        const spec = {
            kind: this.props.kind,
            model,
            compare: this.compare,
            labels: { total: _t("Total") },
            view: this.props.widget.view || {},
            theme: this.theme.tokens(this.root.el),
            fmt: { lang: user.lang || "en", currency: this.props.frame.meta.currency },
            animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        };
        if (!this.adapter) {
            const Adapter = registry.category("levelix_board_charts").get(this.props.adapter);
            const adapter = new Adapter();
            adapter.onPointClick((point) => {
                // an adapter names the row itself (heat map cells, funnel stages ...) or a series and a position on the axis
                const rowIndex = point.rowIndex !== undefined ? point.rowIndex : this.model.series?.[point.seriesIndex]?.rowIndex[point.pointIndex];
                if (rowIndex !== null && rowIndex !== undefined && this.props.onRowClick) {
                    this.props.onRowClick(rowIndex);
                }
            });
            await adapter.mount(host, spec);
            if (generation !== this.generation) {
                adapter.dispose();
                return;
            }
            this.adapter = adapter;
            this.observer = new ResizeObserver(() => this.adapter?.resize());
            this.observer.observe(host);
        } else {
            this.adapter.update(spec);
        }
    }
}
