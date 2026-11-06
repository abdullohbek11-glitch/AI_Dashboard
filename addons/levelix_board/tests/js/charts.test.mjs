// The other chart types: models and options, without a browser. Run: node --test addons/levelix_board/tests/js
import assert from "node:assert/strict";
import test from "node:test";

import { buildChartJs, buildECharts, categoryLabels } from "../../static/src/lib/chart_options.js";
import { MORE_KINDS, buildMore } from "../../static/src/lib/chart_options_more.js";
import { formatPart } from "../../static/src/lib/format.js";
import {
    compareSeries, comboModel, funnelModel, gaugeModel, heatmapModel, labelOf, scatterModel, seriesModel, treemapModel, waterfallModel,
} from "../../static/src/lib/frame_model.js";
import { FALLBACK_THEME } from "../../static/src/lib/theme.js";

const theme = { ...FALLBACK_THEME, surface: "#ffffff" };
const fmt = { lang: "en", currency: { symbol: "UZS", position: "after" } };
const col = (id, role, type = "number", extra = {}) => ({ id, label: id.toUpperCase(), role, type, ...extra });
const frame = (columns, rows, extra = {}) => ({ columns, rows, meta: { group_refs: rows.map((_, i) => [i]), ...(extra.meta || {}) }, ...extra });

// -- date parts ----------------------------------------------------------------

test("date parts read as weekday, hour and month names (Odoo counts Sunday as 0)", () => {
    assert.equal(formatPart(0, "day_of_week", "en"), "Sun");
    assert.equal(formatPart(1, "day_of_week", "en"), "Mon");
    assert.equal(formatPart(6, "day_of_week", "en"), "Sat");
    assert.equal(formatPart(15, "hour_number", "en"), "15:00");
    assert.equal(formatPart(7, "hour_number", "en"), "07:00");
    assert.equal(formatPart(3, "month_number", "en"), "Mar");
    assert.equal(formatPart(2, "quarter_number", "en"), "Q2");
    assert.equal(formatPart(18, "iso_week_number", "en"), "18");
    assert.equal(formatPart("Not set", "day_of_week", "en"), "Not set");
    assert.equal(formatPart(null, "hour_number", "en"), "null");
});

test("labels follow the column: parts, dates, names", () => {
    assert.equal(labelOf(1, col("d", "dimension", "datetime", { granularity: "day_of_week" })), "Mon");
    assert.equal(labelOf("2026-11-05", col("d", "dimension", "date", { granularity: "year" })), "2026");
    assert.equal(labelOf("Hamkor", col("p", "dimension", "many2one")), "Hamkor");
    assert.equal(categoryLabels({ categories: [0, 3], granularity: "day_of_week", dimType: "datetime" }, "en").join(), "Sun,Wed");
});

// -- models --------------------------------------------------------------------

test("heat map: Monday first, hours in order, one cell per row", () => {
    const f = frame(
        [col("d", "dimension", "datetime", { granularity: "day_of_week" }), col("h", "dimension", "datetime", { granularity: "hour_number" }), col("m1", "measure")],
        [[0, 15, 5], [1, 9, 2], [1, 15, 7], [6, 9, 1]],
    );
    const model = heatmapModel(f, "en");
    assert.deepEqual(model.xs, ["Mon", "Sat", "Sun"]); // 1, 6, 0 in reading order
    assert.deepEqual(model.ys, ["09:00", "15:00"]);
    assert.deepEqual(model.cells, [[2, 1, 5, 0], [0, 0, 2, 1], [0, 1, 7, 2], [1, 0, 1, 3]]);
    assert.equal(model.max, 7);
    assert.equal(model.min, 0);
    assert.equal(heatmapModel(frame([col("a", "dimension"), col("b", "dimension"), col("m1", "measure")], []), "en").max, 0);
});

test("funnel and treemap keep the row index and mute Others", () => {
    const f = frame([col("p", "dimension", "many2one"), col("m1", "measure")], [["A", 10], ["B", 4], ["Others", 2]], { meta: { group_refs: [[1], [2], ["__others__"]] } });
    const funnel = funnelModel(f);
    assert.deepEqual(funnel.items.map((i) => [i.name, i.value, i.rowIndex, i.muted]), [["A", 10, 0, false], ["B", 4, 1, false], ["Others", 2, 2, true]]);
    assert.equal(treemapModel(f).nodes.length, 3);
    const two = frame([col("c", "dimension"), col("p", "dimension"), col("m1", "measure")], [["Dairy", "Milk", 5], ["Dairy", "Butter", 3], ["Drinks", "Cola", 4]]);
    const tree = treemapModel(two).nodes;
    assert.deepEqual(tree.map((n) => [n.name, n.value, n.children.length]), [["Dairy", 8, 2], ["Drinks", 4, 1]]);
    assert.equal(tree[0].children[1].rowIndex, 1);
});

test("waterfall: each step starts where the last one ended, and a total closes it", () => {
    const f = frame([col("p", "dimension"), col("m1", "measure")], [["Sales", 100], ["Returns", -30], ["Fees", -20], ["Bonus", 5]]);
    const { steps } = waterfallModel(f);
    assert.deepEqual(steps.map((s) => [s.from, s.to, s.delta]), [[0, 100, 100], [100, 70, -30], [70, 50, -20], [50, 55, 5], [0, 55, 55]]);
    assert.equal(steps.at(-1).total, true);
    assert.equal(steps.at(-1).rowIndex, null); // the total is not a group: it cannot be drilled
    assert.equal(waterfallModel(frame([col("p", "dimension"), col("m1", "measure")], [["Debt", -10]])).steps[1].to, -10); // may end below zero
});

test("scatter and combo split the measures", () => {
    const f = frame([col("p", "dimension"), col("m1", "measure"), col("m2", "measure")], [["A", 10, 3], ["B", 20, 8]]);
    const scatter = scatterModel(f);
    assert.deepEqual(scatter.points.map((p) => [p.name, p.x, p.y, p.rowIndex]), [["A", 10, 3, 0], ["B", 20, 8, 1]]);
    assert.equal(scatter.xMeasure.id, "m1");
    const combo = comboModel(f);
    assert.deepEqual(combo.columns.map((s) => s.measureId), ["m1"]);
    assert.equal(combo.line.measureId, "m2"); // the last measure is the line by default
    assert.deepEqual(combo.line.data, [3, 8]);
    assert.equal(comboModel(f, { line: "m1" }).line.measureId, "m1");
    assert.deepEqual(comboModel(f, { line: "m1" }).columns.map((s) => s.measureId), ["m2"]);
});

test("gauge: the share of the target", () => {
    const f = frame([col("m1", "measure")], [[75]]);
    assert.deepEqual(gaugeModel(f, { target: 100 }), { measure: f.columns[0], value: 75, target: 100, share: 0.75, max: 100 });
    assert.equal(gaugeModel(f, { target: 50 }).max, 75); // past the target the dial grows instead of overflowing
    assert.equal(gaugeModel(frame([col("m1", "measure")], []), { target: 10 }).share, null);
    assert.equal(gaugeModel(f, {}).share, null);
});

test("the earlier period lines up with the current one", () => {
    const f = frame([col("d", "dimension", "date", { granularity: "day" }), col("m1", "measure")], [["2026-11-01", 5], ["2026-11-02", 6]], { compare_rows: [["2026-10-01", 3], ["2026-10-02", 4]] });
    const series = compareSeries(f, (label) => `${label} · before`);
    assert.deepEqual(series.map((s) => [s.name, s.measureId, s.data]), [["M1 · before", "m1", [3, 4]]]);
    assert.deepEqual(compareSeries(frame([col("m1", "measure")], [[1]])), []);
});

// -- options -------------------------------------------------------------------------

test("a pie keeps the share in the tooltip and mutes Others", () => {
    const f = frame([col("p", "dimension", "many2one"), col("m1", "measure", "monetary")], [["A", 75], ["Others", 25]], { meta: { group_refs: [[1], ["__others__"]] } });
    const config = buildChartJs({ kind: "pie", model: seriesModel(f), theme, fmt, view: {} });
    assert.equal(config.type, "pie");
    assert.deepEqual(config.data.labels, ["A", "Others"]);
    assert.equal(config.data.datasets[0].backgroundColor[0], theme.palette[0]);
    assert.notEqual(config.data.datasets[0].backgroundColor[1], theme.palette[1]);
    assert.equal(config.options.plugins.tooltip.callbacks.label({ label: "A", parsed: 75 }), "A: 75 UZS (75.0%)");
    assert.equal(buildChartJs({ kind: "pie", model: seriesModel(f), theme, fmt, view: { donut: true } }).type, "doughnut");
});

test("a comparison is drawn dashed beside the current series", () => {
    const f = frame([col("d", "dimension", "date", { granularity: "day" }), col("m1", "measure")], [["2026-11-01", 5], ["2026-11-02", 6]], { compare_rows: [["2026-10-01", 3], ["2026-10-02", 4]] });
    const model = seriesModel(f);
    const compare = compareSeries(f, (label) => `${label} (before)`);
    const chartjs = buildChartJs({ kind: "line", model, theme, fmt, view: {}, compare });
    assert.equal(chartjs.data.datasets.length, 2);
    assert.deepEqual(chartjs.data.datasets[1].borderDash, [6, 4]);
    assert.equal(chartjs.options.plugins.legend.display, true); // one series and its comparison need a legend
    assert.equal(chartjs.options.plugins.tooltip.callbacks.label({ datasetIndex: 1, dataset: chartjs.data.datasets[1], parsed: { y: 3 } }), "M1 (before): 3");
    const echarts = buildECharts({ kind: "area", model, theme, fmt, view: {}, compare });
    assert.equal(echarts.series.length, 2);
    assert.equal(echarts.series[1].lineStyle.type, "dashed");
    assert.equal(buildChartJs({ kind: "line", model, theme, fmt, view: {} }).options.plugins.legend.display, false);
});

test("every other type builds an option and every datum knows its row", () => {
    const cat = frame([col("p", "dimension", "many2one"), col("m1", "measure", "monetary")], [["A", 10], ["B", 4]]);
    const two = frame([col("p", "dimension", "many2one"), col("m1", "measure"), col("m2", "measure")], [["A", 10, 3], ["B", 20, 8]]);
    const heat = frame([col("d", "dimension", "datetime", { granularity: "day_of_week" }), col("h", "dimension", "datetime", { granularity: "hour_number" }), col("m1", "measure")], [[1, 9, 2]]);
    const tree2 = frame([col("c", "dimension"), col("p", "dimension"), col("m1", "measure")], [["Dairy", "Milk", 5]]);
    const cases = {
        heatmap: heatmapModel(heat), funnel: funnelModel(cat), treemap: treemapModel(tree2), waterfall: waterfallModel(cat),
        scatter: scatterModel(two), combo: comboModel(two), gauge: gaugeModel(frame([col("m1", "measure")], [[7]]), { target: 10 }),
    };
    assert.deepEqual(Object.keys(cases).sort(), [...MORE_KINDS].sort());
    for (const [kind, model] of Object.entries(cases)) {
        const option = buildECharts({ kind, model, theme, fmt, view: {}, animate: false });
        assert.ok(option.series.length >= 1, kind);
        assert.equal(option.animation, false, kind);
    }
    assert.deepEqual(buildMore({ kind: "heatmap", model: heatmapModel(heat), theme, fmt, animate: true }).series[0].data[0], { value: [0, 0, 2], rowIndex: 0 });
    assert.equal(buildMore({ kind: "funnel", model: funnelModel(cat), theme, fmt, animate: true }).series[0].data[1].rowIndex, 1);
    const waterfall = buildMore({ kind: "waterfall", model: waterfallModel(cat), theme, fmt, animate: true, labels: { total: "Jami" } });
    assert.equal(waterfall.xAxis.data.at(-1), "Jami");
    assert.equal(waterfall.series[0].data.at(-1).rowIndex, null);
    const combo = buildMore({ kind: "combo", model: comboModel(two), theme, fmt, animate: true });
    assert.deepEqual(combo.series.map((s) => s.type), ["bar", "line"]);
    assert.equal(combo.yAxis.length, 2); // the line has an axis of its own
    assert.equal(buildMore({ kind: "scatter", model: scatterModel(two), theme, fmt, animate: true }).series[0].data[1].rowIndex, 1);
});

test("text from the data never becomes markup in a tooltip", () => {
    const cat = frame([col("p", "dimension"), col("m1", "measure")], [["<img src=x onerror=alert(1)>", 4]]);
    const option = buildMore({ kind: "funnel", model: funnelModel(cat), theme, fmt, animate: true });
    const html = option.tooltip.formatter({ name: "<img src=x onerror=alert(1)>", value: 4 });
    assert.ok(!html.includes("<img"), html);
    const scatter = buildMore({ kind: "scatter", model: scatterModel(frame([col("p", "dimension"), col("m1", "measure"), col("m2", "measure")], [["<b>x</b>", 1, 2]])), theme, fmt, animate: true });
    assert.ok(!scatter.tooltip.formatter({ name: "<b>x</b>", value: [1, 2] }).includes("<b>x"));
});
