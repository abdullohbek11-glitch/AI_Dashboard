/** @odoo-module **/
import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { formatFull, formatNumber } from "../../lib/format.js";
import { kpiModel, numberOptionsFor, seriesModel } from "../../lib/frame_model.js";
import { widgetRegistry } from "../widget_registry.js";

/** Big numbers; with a date axis the last bucket is the value and the buckets draw a small trend line. */
export class KpiWidget extends Component {
    static template = "levelix_board.KpiWidget";
    static props = { frame: Object, widget: Object, kind: { type: String, optional: true }, adapter: { type: String, optional: true }, onRowClick: { type: Function, optional: true } };

    setup() {
        this.root = useRef("root");
        this.theme = useService("levelix_board.theme");
        this.themeState = useState(this.theme.state);
        this.sparks = [];
        useEffect(
            () => {
                this.drawSparklines();
            },
            () => [this.props.frame, this.themeState.mode]
        );
        onWillUnmount(() => this.disposeSparklines());
    }

    get cards() {
        const frame = this.props.frame;
        const lang = user.lang || "en";
        return kpiModel(frame).map((card) => {
            const column = frame.columns.find((c) => c.id === card.id);
            const options = numberOptionsFor(column, frame, lang);
            return {
                ...card,
                text: formatNumber(card.value, options),
                full: formatFull(card.value, options),
                deltaText: card.delta ? this.deltaText(card.delta) : null,
            };
        });
    }

    /** A single card whose label repeats the widget title needs no label of its own. */
    showLabel(card) {
        return this.cards.length > 1 || card.label !== (this.props.widget.title || this.props.widget.id);
    }

    deltaText(delta) {
        const arrow = delta.direction === "up" ? "▲" : delta.direction === "down" ? "▼" : "■";
        const pct = delta.pct === null ? "" : ` ${Math.abs(delta.pct * 100).toFixed(1)}%`;
        return `${arrow}${pct}`;
    }

    onClick() {
        const lastRow = this.props.frame.rows.length - 1;
        if (this.props.onRowClick && lastRow >= 0) {
            this.props.onRowClick(lastRow);
        }
    }

    async drawSparklines() {
        const frame = this.props.frame;
        const hosts = this.root.el.querySelectorAll(".lxb-kpi__trend");
        this.disposeSparklines();
        if (!hosts.length) {
            return;
        }
        const Adapter = registry.category("levelix_board_charts").get("chartjs");
        const theme = this.theme.tokens(this.root.el);
        const model = seriesModel(frame);
        const lang = user.lang || "en";
        for (const host of hosts) {
            const index = Number(host.dataset.index);
            const one = { ...model, series: [model.series[index]] };
            const adapter = new Adapter();
            this.sparks.push(adapter);
            await adapter.mount(host, { kind: "area", model: one, theme, fmt: { lang, currency: frame.meta.currency }, sparkline: true, view: {} });
        }
    }

    disposeSparklines() {
        this.sparks.forEach((a) => a.dispose());
        this.sparks = [];
    }
}

widgetRegistry.add("kpi", { component: KpiWidget, defaultSize: { w: 6, h: 4 }, adapter: () => "chartjs" });
