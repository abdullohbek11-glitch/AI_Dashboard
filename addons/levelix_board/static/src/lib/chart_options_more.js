/** @odoo-module **/
// ECharts options of the widget types beyond line / area / bar / pie: heat map, funnel, treemap, gauge, waterfall,
// scatter and combo. Pure (no browser), so they are tested with `node --test`.
import { escapeHtml, formatFull, formatNumber } from "./format.js";
import { colorAt, withAlpha } from "./theme.js";

export const MORE_KINDS = ["heatmap", "funnel", "treemap", "gauge", "waterfall", "scatter", "combo"];

const money = (measure, fmt) => ({
    lang: fmt.lang, percent: measure && measure.type === "percent", currency: measure && measure.type === "monetary" ? fmt.currency : null,
});
const short = (value, measure, fmt) => formatNumber(value, money(measure, fmt));
const full = (value, measure, fmt) => formatFull(value, money(measure, fmt));

function base(theme, animate) {
    return {
        animation: animate,
        color: theme.palette,
        textStyle: { color: theme.text, fontFamily: theme.font },
        tooltip: { confine: true, backgroundColor: theme.surface, borderColor: theme.border, textStyle: { color: theme.text } },
    };
}

const axisText = (theme) => ({ color: theme.textMuted, hideOverlap: true });
const axisLine = (theme) => ({ lineStyle: { color: theme.grid } });

/** Each data item carries `rowIndex`, which is how a click finds its row of the frame (and so its `group_ref`). */
const item = (value, rowIndex, extra = {}) => ({ value, rowIndex, ...extra });

export function heatmapOption({ model, theme, fmt, animate }) {
    const cells = model.cells.map((c) => item([c[0], c[1], c[2]], c[3]));
    return {
        ...base(theme, animate),
        tooltip: {
            ...base(theme, animate).tooltip, position: "top",
            formatter: (p) => `${escapeHtml(model.xs[p.value[0]])} · ${escapeHtml(model.ys[p.value[1]])}<br/><b>${escapeHtml(full(p.value[2], model.measure, fmt))}</b>`,
        },
        grid: { left: 8, right: 16, top: 12, bottom: 48, containLabel: true },
        xAxis: { type: "category", data: model.xs, splitArea: { show: false }, axisLine: axisLine(theme), axisTick: { show: false }, axisLabel: axisText(theme) },
        yAxis: { type: "category", data: model.ys, splitArea: { show: false }, axisLine: axisLine(theme), axisTick: { show: false }, axisLabel: axisText(theme) },
        visualMap: {
            min: model.min, max: model.max || 1, calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 12, itemHeight: 120,
            text: [short(model.max, model.measure, fmt), short(model.min, model.measure, fmt)], textStyle: { color: theme.textMuted },
            inRange: { color: [withAlpha(theme.palette[0], 0.12), theme.palette[0]] },
        },
        series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: theme.surface, borderWidth: 2, borderRadius: 3 }, emphasis: { itemStyle: { borderColor: theme.text } } }],
    };
}

export function funnelOption({ model, theme, fmt, animate }) {
    return {
        ...base(theme, animate),
        tooltip: { ...base(theme, animate).tooltip, trigger: "item", formatter: (p) => `${escapeHtml(p.name)}: <b>${escapeHtml(full(p.value, model.measure, fmt))}</b>` },
        series: [{
            type: "funnel", left: "8%", width: "84%", top: 8, bottom: 8, sort: "none", gap: 3, minSize: "12%",
            label: { show: true, position: "inside", color: "#fff", formatter: (p) => `${p.name} · ${short(p.value, model.measure, fmt)}`, overflow: "truncate" },
            itemStyle: { borderColor: theme.surface, borderWidth: 1 },
            data: model.items.map((it, i) => item(it.value, it.rowIndex, { name: it.name, itemStyle: { color: it.muted ? withAlpha(theme.textMuted, 0.6) : colorAt(theme, i) } })),
        }],
    };
}

export function treemapOption({ model, theme, fmt, animate }) {
    let index = 0;
    const paint = (node) => {
        const own = node.children ? { itemStyle: { borderColor: theme.surface, borderWidth: 2, gapWidth: 2 } } : {};
        const color = node.muted ? withAlpha(theme.textMuted, 0.6) : colorAt(theme, index++);
        return {
            name: node.name, value: node.value, rowIndex: node.rowIndex ?? null,
            ...(node.children ? { children: node.children.map((c) => ({ ...paint(c), itemStyle: { color } })), ...own, itemStyle: { color } } : { itemStyle: { color } }),
        };
    };
    return {
        ...base(theme, animate),
        tooltip: { ...base(theme, animate).tooltip, formatter: (p) => `${escapeHtml(p.name)}: <b>${escapeHtml(full(p.value, model.measure, fmt))}</b>` },
        series: [{
            type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, left: 0, right: 0, top: 0, bottom: 0,
            label: { show: true, color: "#fff", formatter: (p) => `${p.name}\n${short(p.value, model.measure, fmt)}`, overflow: "truncate" },
            upperLabel: { show: false }, itemStyle: { borderColor: theme.surface, borderWidth: 2 },
            data: model.nodes.map(paint),
        }],
    };
}

export function gaugeOption({ model, theme, fmt, animate }) {
    const share = model.share === null ? null : Math.round(model.share * 100);
    return {
        ...base(theme, animate),
        series: [{
            type: "gauge", min: 0, max: model.max, radius: "88%", center: ["50%", "62%"], startAngle: 200, endAngle: -20,
            progress: { show: true, width: 18, roundCap: true, itemStyle: { color: theme.palette[0] } },
            axisLine: { roundCap: true, lineStyle: { width: 18, color: [[1, theme.grid]] } },
            axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false }, // the value and the share say it; scale numbers only crowd the dial
            pointer: { show: false }, anchor: { show: false },
            title: { show: share !== null, offsetCenter: [0, "34%"], color: theme.textMuted, fontSize: 13 },
            detail: { valueAnimation: animate, offsetCenter: [0, "-6%"], fontSize: 26, fontWeight: 700, color: theme.text, formatter: (v) => short(v, model.measure, fmt) },
            data: [{ value: model.value, name: share === null ? "" : `${share}% of ${short(model.target, model.measure, fmt)}` }],
        }],
    };
}

export function waterfallOption({ model, theme, fmt, animate, labels = {} }) {
    const names = model.steps.map((s) => (s.total ? labels.total || "Total" : s.name));
    const colorOf = (s) => (s.total ? theme.palette[0] : s.delta < 0 ? theme.palette[3] : theme.palette[2]);
    return {
        ...base(theme, animate),
        grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
        tooltip: {
            ...base(theme, animate).tooltip, trigger: "item",
            formatter: (p) => {
                const s = model.steps[p.dataIndex];
                const sign = s.total || s.delta < 0 ? "" : "+";
                return `${escapeHtml(names[p.dataIndex])}: <b>${escapeHtml(sign + full(s.delta, model.measure, fmt))}</b><br/>${escapeHtml(full(s.to, model.measure, fmt))}`;
            },
        },
        xAxis: { type: "category", data: names, axisLine: axisLine(theme), axisTick: { show: false }, axisLabel: { color: theme.textMuted, interval: 0, rotate: names.length > 6 ? 35 : 0 } },
        yAxis: { type: "value", axisLabel: { color: theme.textMuted, formatter: (v) => short(v, model.measure, fmt) }, splitLine: { lineStyle: { color: theme.grid } } },
        series: [{
            type: "custom",
            renderItem: (params, api) => {
                const from = api.coord([api.value(0), api.value(1)]);
                const to = api.coord([api.value(0), api.value(2)]);
                const width = api.size([1, 0])[0] * 0.6;
                return { type: "rect", shape: { x: from[0] - width / 2, y: Math.min(from[1], to[1]), width, height: Math.max(1, Math.abs(to[1] - from[1])) }, style: api.style() };
            },
            data: model.steps.map((s, i) => item([i, s.from, s.to], s.rowIndex, { itemStyle: { color: colorOf(s) } })),
        }],
    };
}

export function scatterOption({ model, theme, fmt, animate }) {
    return {
        ...base(theme, animate),
        grid: { left: 8, right: 24, top: 24, bottom: 8, containLabel: true },
        tooltip: {
            ...base(theme, animate).tooltip, trigger: "item",
            formatter: (p) => `${escapeHtml(p.name)}<br/>${escapeHtml(model.xMeasure.label)}: <b>${escapeHtml(full(p.value[0], model.xMeasure, fmt))}</b><br/>${escapeHtml(model.yMeasure.label)}: <b>${escapeHtml(full(p.value[1], model.yMeasure, fmt))}</b>`,
        },
        xAxis: { type: "value", name: model.xMeasure.label, nameLocation: "middle", nameGap: 28, nameTextStyle: { color: theme.textMuted }, axisLabel: { color: theme.textMuted, formatter: (v) => short(v, model.xMeasure, fmt) }, splitLine: { lineStyle: { color: theme.grid } } },
        yAxis: { type: "value", name: model.yMeasure.label, nameTextStyle: { color: theme.textMuted }, axisLabel: { color: theme.textMuted, formatter: (v) => short(v, model.yMeasure, fmt) }, splitLine: { lineStyle: { color: theme.grid } } },
        series: [{
            type: "scatter", symbolSize: 12, itemStyle: { color: withAlpha(theme.palette[0], 0.8), borderColor: theme.surface, borderWidth: 1 },
            data: model.points.map((pt) => item([pt.x, pt.y], pt.rowIndex, { name: pt.name })),
        }],
    };
}

export function comboOption({ model, theme, fmt, animate }) {
    const all = [...model.columns, model.line];
    const axis = (series, position) => ({
        type: "value", position, axisLabel: { color: theme.textMuted, formatter: (v) => short(v, series, fmt) },
        splitLine: { show: position === "left", lineStyle: { color: theme.grid } },
    });
    return {
        ...base(theme, animate),
        grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
        legend: { top: 0, textStyle: { color: theme.text }, icon: "circle", itemWidth: 8 },
        tooltip: {
            ...base(theme, animate).tooltip, trigger: "axis",
            formatter: (params) => {
                const rows = Array.isArray(params) ? params : [params];
                const lines = rows.map((p) => `${p.marker}${escapeHtml(p.seriesName)}: <b>${escapeHtml(full(p.value, all[p.seriesIndex], fmt))}</b>`);
                return [escapeHtml(rows[0].axisValueLabel ?? rows[0].name), ...lines].join("<br/>");
            },
        },
        xAxis: { type: "category", data: model.categories, axisLine: axisLine(theme), axisTick: { show: false }, axisLabel: { color: theme.textMuted, hideOverlap: true } },
        yAxis: [axis(model.columns[0] || model.line, "left"), axis(model.line, "right")],
        series: [
            ...model.columns.map((s, i) => ({
                type: "bar", name: s.name, yAxisIndex: 0, barMaxWidth: 40, itemStyle: { color: colorAt(theme, i), borderRadius: [4, 4, 0, 0] },
                data: s.data.map((v, row) => item(v, model.rowIndex[row])),
            })),
            {
                type: "line", name: model.line.name, yAxisIndex: 1, smooth: false, symbolSize: 6, lineStyle: { width: 2 }, itemStyle: { color: colorAt(theme, model.columns.length) },
                data: model.line.data.map((v, row) => item(v, model.rowIndex[row])),
            },
        ],
    };
}

const BUILDERS = { heatmap: heatmapOption, funnel: funnelOption, treemap: treemapOption, gauge: gaugeOption, waterfall: waterfallOption, scatter: scatterOption, combo: comboOption };

export function buildMore(spec) {
    return BUILDERS[spec.kind](spec);
}
