/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

const locale = () => (user.lang || "en").replace("_", "-");

export function formatCell(value) {
    if (typeof value === "number") {
        return new Intl.NumberFormat(locale(), { maximumFractionDigits: 2 }).format(value);
    }
    return value === null || value === undefined ? "" : String(value);
}

export function formatUnit(value, unit) {
    const text = formatCell(value);
    if (!unit || !unit.symbol) {
        return text;
    }
    return unit.position === "before" ? `${unit.symbol}${text}` : `${text} ${unit.symbol}`;
}

/** Blocks are what an answer can show besides text. Add a type = add a component here (or in another module). */
export const blocksRegistry = registry.category("levelix_ai_blocks");

class BlockBase extends Component {
    static props = {
        block: Object,
        onOpen: { type: Function, optional: true },
        onChoose: { type: Function, optional: true },
        onPrefill: { type: Function, optional: true },
    };
    formatCell = formatCell;
    formatUnit = formatUnit;
}

export class TableBlock extends BlockBase {
    static template = "levelix_ai_core.TableBlock";
    isNumber(value) {
        return typeof value === "number";
    }
}

export class KpiBlock extends BlockBase {
    static template = "levelix_ai_core.KpiBlock";
}

export class ChoicesBlock extends BlockBase {
    static template = "levelix_ai_core.ChoicesBlock";
}

export class ChartBlock extends BlockBase {
    static template = "levelix_ai_core.ChartBlock";

    setup() {
        this.canvas = useRef("canvas");
        onMounted(() => this.draw());
        onWillUnmount(() => this.chart?.destroy());
    }

    async draw() {
        await loadBundle("web.chartjs_lib");
        const style = getComputedStyle(this.canvas.el);
        const colors = Array.from({ length: 8 }, (_, i) => style.getPropertyValue(`--lxai-cat-${i + 1}`).trim());
        const { block } = this.props;
        const pie = block.chart === "pie";
        const datasets = block.datasets.map((set, i) => ({
            label: set.label,
            data: set.data,
            backgroundColor: pie ? block.labels.map((_, j) => colors[j % 8]) : colors[i % 8],
            borderColor: pie ? "transparent" : colors[i % 8],
            tension: 0.3,
        }));
        this.chart = new window.Chart(this.canvas.el, {
            type: block.chart,
            data: { labels: block.labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: pie || datasets.length > 1 },
                    tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label || ctx.label}: ${formatUnit(ctx.parsed.y ?? ctx.parsed, block.unit)}` } },
                },
            },
        });
    }
}

blocksRegistry.add("table", { component: TableBlock });
blocksRegistry.add("kpi", { component: KpiBlock });
blocksRegistry.add("chart", { component: ChartBlock });
blocksRegistry.add("choices", { component: ChoicesBlock });
