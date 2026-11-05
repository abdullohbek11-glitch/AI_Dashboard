/** @odoo-module **/
// Frame model -> option objects of the two chart libraries. Pure, so it is tested without a browser.
// Both builders read the same theme and the same formatters, which keeps the two libraries looking alike.
import { escapeHtml, formatDateLabel, formatFull, formatNumber } from "./format.js";
import { colorAt, withAlpha } from "./theme.js";

const MANY_POINTS = 40; // above this, point markers are hidden

function isTime(model) {
    return model.dimType === "date" || model.dimType === "datetime";
}

export function categoryLabels(model, lang) {
    return model.categories.map((value) => (isTime(model) ? formatDateLabel(value, model.granularity, lang) : String(value)));
}

function numberOptions(series, fmt) {
    const percent = series.type === "percent";
    return { lang: fmt.lang, percent, currency: series.type === "monetary" ? fmt.currency : null };
}

/** `new Chart(canvas, config)` for line / area / bar. */
export function buildChartJs({ kind, model, theme, fmt, view = {}, animate = true, sparkline = false }) {
    const labels = categoryLabels(model, fmt.lang);
    const horizontal = kind === "bar" && view.orientation === "horizontal";
    const stacked = Boolean(view.stacked);
    const few = model.categories.length <= MANY_POINTS;
    const datasets = model.series.map((s, i) => {
        const color = colorAt(theme, i);
        return kind === "bar"
            ? {
                label: s.name, data: s.data, borderRadius: 4, maxBarThickness: 48,
                // the "Others" bar is a sum of many groups: drawn muted so it is not read as one of them
                backgroundColor: s.muted.some(Boolean) ? s.muted.map((m) => (m ? withAlpha(theme.textMuted, 0.55) : color)) : color,
            }
            : {
                label: s.name, data: s.data, borderColor: color, borderWidth: 2, tension: view.smooth ? 0.35 : 0,
                fill: kind === "area", backgroundColor: withAlpha(color, 0.16), pointRadius: few ? 3 : 0,
                pointHoverRadius: 5, pointBackgroundColor: color, spanGaps: true,
            };
    });
    const first = model.series[0] || { type: "number" };
    const valueAxis = {
        stacked, beginAtZero: true,
        grid: { color: theme.grid }, border: { display: false },
        ticks: { color: theme.textMuted, maxRotation: 0, maxTicksLimit: 6, callback: (v) => formatNumber(v, numberOptions(first, fmt)) },
    };
    // names of groups (products, customers) are never skipped, they are turned instead; dates may be thinned out
    const categoryTicks = isTime(model)
        ? { color: theme.textMuted, maxRotation: 0, autoSkipPadding: 12 }
        : { color: theme.textMuted, autoSkip: false, maxRotation: horizontal ? 0 : 50 };
    const categoryAxis = { stacked, grid: { display: false }, ticks: categoryTicks };
    if (sparkline) { // a KPI trend: no axes, no legend, no tooltip
        datasets.forEach((d) => Object.assign(d, { pointRadius: 0, pointHoverRadius: 0, borderWidth: 2 }));
        return {
            type: "line", data: { labels, datasets },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false, events: [],
                scales: { x: { display: false }, y: { display: false } },
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
            },
        };
    }
    return {
        type: kind === "bar" ? "bar" : "line",
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: animate ? { duration: 300 } : false,
            indexAxis: horizontal ? "y" : "x",
            interaction: { mode: "index", intersect: false },
            scales: horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
            plugins: {
                legend: { display: model.series.length > 1, labels: { color: theme.text, usePointStyle: true, boxWidth: 8 } },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const series = model.series[ctx.datasetIndex];
                            const value = horizontal ? ctx.parsed.x : ctx.parsed.y;
                            return `${ctx.dataset.label}: ${formatFull(value, numberOptions(series, fmt))}`;
                        },
                    },
                },
            },
        },
    };
}

/** `echarts.setOption(option)` for line / area (smooth lines). */
export function buildECharts({ kind, model, theme, fmt, view = {}, animate = true }) {
    const labels = categoryLabels(model, fmt.lang);
    const few = model.categories.length <= MANY_POINTS;
    const first = model.series[0] || { type: "number" };
    return {
        animation: animate,
        color: theme.palette,
        textStyle: { color: theme.text, fontFamily: theme.font },
        grid: { left: 8, right: 16, top: model.series.length > 1 ? 36 : 16, bottom: 8, containLabel: true },
        legend: { show: model.series.length > 1, top: 0, textStyle: { color: theme.text }, icon: "circle", itemWidth: 8 },
        tooltip: {
            trigger: "axis", confine: true,
            backgroundColor: theme.surface, borderColor: theme.border, textStyle: { color: theme.text },
            formatter: (params) => {
                const rows = Array.isArray(params) ? params : [params];
                const head = escapeHtml(rows[0].axisValueLabel ?? rows[0].name);
                const lines = rows.map((p) => {
                    const series = model.series[p.seriesIndex];
                    return `${p.marker}${escapeHtml(p.seriesName)}: <b>${escapeHtml(formatFull(p.value, numberOptions(series, fmt)))}</b>`;
                });
                return [head, ...lines].join("<br/>");
            },
        },
        xAxis: {
            type: "category", data: labels, boundaryGap: false,
            axisLine: { lineStyle: { color: theme.grid } }, axisTick: { show: false },
            axisLabel: { color: theme.textMuted, hideOverlap: true },
        },
        yAxis: {
            type: "value",
            axisLabel: { color: theme.textMuted, formatter: (v) => formatNumber(v, numberOptions(first, fmt)) },
            splitLine: { lineStyle: { color: theme.grid } },
        },
        series: model.series.map((s, i) => ({
            type: "line", name: s.name, data: s.data,
            smooth: Boolean(view.smooth), showSymbol: few, symbolSize: 6, connectNulls: true,
            lineStyle: { width: 2 },
            areaStyle: kind === "area" ? { opacity: 0.16 } : undefined,
            itemStyle: { color: colorAt(theme, i) },
            emphasis: { focus: "series" },
        })),
    };
}
