/** @odoo-module **/
import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { seriesModel } from "../../lib/frame_model.js";

/** Draws a frame as a line / area / bar chart through whichever adapter the widget type asks for. */
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
        return seriesModel(this.props.frame);
    }

    /** Text version of the chart for screen readers. */
    get tableRows() {
        const model = this.model;
        return model.categories.map((category, i) => [category, ...model.series.map((s) => s.data[i])]);
    }

    async render() {
        const generation = ++this.generation;
        const host = this.root.el.querySelector(".lxb-chart__canvas");
        const model = this.model;
        const spec = {
            kind: this.props.kind,
            model,
            view: this.props.widget.view || {},
            theme: this.theme.tokens(this.root.el),
            fmt: { lang: user.lang || "en", currency: this.props.frame.meta.currency },
            animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        };
        if (!this.adapter) {
            const Adapter = registry.category("levelix_board_charts").get(this.props.adapter);
            const adapter = new Adapter();
            adapter.onPointClick(({ seriesIndex, pointIndex }) => {
                const rowIndex = this.model.series[seriesIndex]?.rowIndex[pointIndex];
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
