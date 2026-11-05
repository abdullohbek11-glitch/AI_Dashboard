// Pure frontend logic. Run: node --test addons/levelix_board/tests/js
import assert from "node:assert/strict";
import test from "node:test";

import { buildChartJs, buildECharts, categoryLabels } from "../../static/src/lib/chart_options.js";
import { escapeHtml, formatDateLabel, formatFull, formatNumber, unitLanguage } from "../../static/src/lib/format.js";
import { deltaInfo, groupRefAt, isDrillableRow, isEmptyFrame, kpiModel, seriesModel, tableModel } from "../../static/src/lib/frame_model.js";
import { GRID_COLUMNS, clampCell, gridStyle, mobileOrder, placeWidgets } from "../../static/src/lib/grid.js";
import { createBatcher } from "../../static/src/lib/batcher.js";
import { FALLBACK_THEME, readTheme, withAlpha } from "../../static/src/lib/theme.js";

const fmt = { lang: "en", currency: { symbol: "UZS", position: "after" } };
const col = (id, role, type = "number", extra = {}) => ({ id, label: id.toUpperCase(), role, type, ...extra });

// -- numbers -----------------------------------------------------------------

test("small numbers stay whole, fractions get two decimals", () => {
    assert.equal(formatNumber(0, { lang: "en" }), "0");
    assert.equal(formatNumber(950, { lang: "en" }), "950");
    assert.equal(formatNumber(12.5, { lang: "en" }), "12.5");
    assert.equal(formatNumber(-42, { lang: "en" }), "-42");
});

test("compact units follow the language", () => {
    assert.equal(formatNumber(1200, { lang: "en" }), "1.2K");
    assert.equal(formatNumber(3_400_000, { lang: "en" }), "3.4M");
    assert.equal(formatNumber(2_000_000_000, { lang: "uz_UZ" }), "2 mlrd");
    assert.match(formatNumber(1_500_000, { lang: "uz" }), /^1[.,]5M$/); // the decimal sign follows the locale
    assert.match(formatNumber(2_000_000_000, { lang: "ru_RU" }), /млрд$/);
    assert.equal(formatNumber(1_000_000_000_000, { lang: "en" }), "1T");
});

test("rounding never prints 1000K", () => {
    assert.equal(formatNumber(999_960, { lang: "en" }), "1M");
});

test("currency goes before or after, and is left out when mixed or missing", () => {
    assert.equal(formatNumber(1200, { lang: "en", currency: { symbol: "UZS", position: "after" } }), "1.2K UZS");
    assert.equal(formatNumber(1200, { lang: "en", currency: { symbol: "$", position: "before" } }), "$1.2K");
    assert.equal(formatNumber(1200, { lang: "en", currency: { mixed: true } }), "1.2K");
    assert.equal(formatNumber(1200, { lang: "en", currency: null }), "1.2K");
});

test("missing values show a dash; percent adds a sign", () => {
    for (const v of [null, undefined, NaN]) {
        assert.equal(formatNumber(v), "—");
        assert.equal(formatFull(v), "—");
    }
    assert.equal(formatNumber(12, { percent: true }), "12%");
});

test("full format groups digits", () => {
    assert.equal(formatFull(1234567.891, { lang: "en" }), "1,234,567.89");
    assert.equal(formatFull(5, { lang: "en", currency: { symbol: "$", position: "before" } }), "$5");
});

test("unit language falls back to English", () => {
    assert.equal(unitLanguage("de_DE"), "en");
    assert.equal(unitLanguage("uz@Cyrl"), "uz");
    assert.equal(unitLanguage(undefined), "en");
});

// -- dates, text ---------------------------------------------------------------

test("date labels per granularity", () => {
    assert.equal(formatDateLabel("2026-10-07", "day", "en"), "Oct 7");
    assert.equal(formatDateLabel("2026-10-01", "month", "en"), "Oct 2026");
    assert.equal(formatDateLabel("2026-10-01", "quarter", "en"), "Q4 2026");
    assert.equal(formatDateLabel("2026-01-01", "year", "en"), "2026");
    assert.equal(formatDateLabel("Not set", "day", "en"), "Not set");
    assert.equal(formatDateLabel("2026-03-31", "day", "en"), "Mar 31"); // UTC maths: no day shift
});

test("html is escaped", () => {
    assert.equal(escapeHtml(`<img src=x onerror="a()">&'`), "&lt;img src=x onerror=&quot;a()&quot;&gt;&amp;&#39;");
});

// -- grid ---------------------------------------------------------------------

test("a cell is clamped into the 24 columns", () => {
    assert.deepEqual(clampCell({ x: 20, y: 2, w: 10, h: 0 }), { x: 14, y: 2, w: 10, h: 1 });
    assert.deepEqual(clampCell({ x: -3, y: -1, w: 99, h: 5 }), { x: 0, y: 0, w: 24, h: 5 });
    assert.deepEqual(clampCell(undefined), { x: 0, y: 0, w: 12, h: 8 });
});

test("widgets without a grid flow below the placed ones and wrap at 24 columns", () => {
    const widgets = [
        { id: "a", grid: { x: 0, y: 0, w: 16, h: 8 } },
        { id: "b" }, { id: "c" }, { id: "d" },
    ];
    const cells = Object.fromEntries(placeWidgets(widgets, () => ({ w: 12, h: 4 })).map((c) => [c.id, c]));
    assert.deepEqual(cells.a, { id: "a", x: 0, y: 0, w: 16, h: 8 });
    assert.deepEqual([cells.b.x, cells.b.y], [0, 8]);
    assert.deepEqual([cells.c.x, cells.c.y], [12, 8]);
    assert.deepEqual([cells.d.x, cells.d.y], [0, 12]); // wrapped
    for (const c of Object.values(cells)) {
        assert.ok(c.x + c.w <= GRID_COLUMNS);
    }
});

test("mobile order is top to bottom, then left to right", () => {
    const order = mobileOrder([{ id: "r", x: 12, y: 0 }, { id: "l", x: 0, y: 0 }, { id: "low", x: 0, y: 8 }]).map((c) => c.id);
    assert.deepEqual(order, ["l", "r", "low"]);
});

test("grid style is one-based CSS variables", () => {
    assert.equal(gridStyle({ x: 0, y: 0, w: 16, h: 8 }, 2), "--lxb-x: 1; --lxb-y: 1; --lxb-w: 16; --lxb-h: 8; --lxb-order: 2;");
});

// -- frame model ------------------------------------------------------------------

const daily = {
    columns: [col("date", "dimension", "date", { granularity: "day", label: "Date" }), col("m1", "measure", "monetary", { label: "Revenue" })],
    rows: [["2026-10-07", 100], ["2026-10-08", 0], ["2026-10-09", 50]],
    meta: { group_refs: [["2026-10-06 19:00:00"], ["2026-10-07 19:00:00"], ["2026-10-08 19:00:00"]], currency: fmt.currency },
};

test("emptiness", () => {
    assert.equal(isEmptyFrame(daily), false);
    assert.equal(isEmptyFrame({ ...daily, rows: [] }), true);
    assert.equal(isEmptyFrame({ ...daily, rows: [["2026-10-07", null]] }), true);
    assert.equal(isEmptyFrame(null), true);
});

test("one axis: one series per measure and every point maps to its row", () => {
    const model = seriesModel(daily);
    assert.deepEqual(model.categories, ["2026-10-07", "2026-10-08", "2026-10-09"]);
    assert.equal(model.series.length, 1);
    assert.deepEqual(model.series[0].data, [100, 0, 50]);
    assert.deepEqual(model.series[0].rowIndex, [0, 1, 2]);
    assert.equal(model.granularity, "day");
});

test("the Others row is marked as muted", () => {
    const frame = {
        columns: [col("p", "dimension", "many2one"), col("m1", "measure")],
        rows: [["A", 5], ["Others", 9]], meta: { group_refs: [[1], ["__others__"]] },
    };
    assert.deepEqual(seriesModel(frame).series[0].muted, [false, true]);
    const config = buildChartJs({ kind: "bar", model: seriesModel(frame), theme: readTheme(() => ""), fmt });
    assert.equal(config.data.datasets[0].backgroundColor[0], FALLBACK_THEME.palette[0]);
    assert.notEqual(config.data.datasets[0].backgroundColor[1], FALLBACK_THEME.palette[0]);
    assert.equal(config.options.scales.x.ticks.autoSkip, false); // group names are not skipped
});

test("two axes: one series per value of the second, missing points stay empty", () => {
    const frame = {
        columns: [col("date", "dimension", "date", { granularity: "month" }), col("state", "dimension", "selection"), col("m1", "measure")],
        rows: [["2026-01-01", "Sale", 5], ["2026-01-01", "Draft", 2], ["2026-02-01", "Sale", 7]],
        meta: {},
    };
    const model = seriesModel(frame);
    assert.deepEqual(model.categories, ["2026-01-01", "2026-02-01"]);
    assert.deepEqual(model.series.map((s) => s.name), ["Sale", "Draft"]);
    assert.deepEqual(model.series[0].data, [5, 7]);
    assert.deepEqual(model.series[1].data, [2, null]);
    assert.deepEqual(model.series[1].rowIndex, [1, null]);
});

test("kpi: last row is the value; the comparison gives a delta", () => {
    const frame = {
        columns: [col("m1", "measure", "monetary"), col("m2", "measure")],
        rows: [[200, 4]], compare_rows: [[100, 4]], meta: {},
    };
    const [a, b] = kpiModel(frame);
    assert.equal(a.value, 200);
    assert.deepEqual(a.delta, { diff: 100, pct: 1, direction: "up" });
    assert.equal(b.delta.direction, "flat");
    assert.equal(a.trend, null);
    assert.deepEqual(kpiModel({ ...daily, compare_rows: undefined })[0].trend, [100, 0, 50]);
    assert.equal(kpiModel({ columns: [col("m1", "measure")], rows: [], meta: {} })[0].value, null);
});

test("delta edge cases", () => {
    assert.equal(deltaInfo(5, null), null);
    assert.equal(deltaInfo(null, 5), null);
    assert.deepEqual(deltaInfo(5, 0), { diff: 5, pct: null, direction: "up" });
    assert.deepEqual(deltaInfo(50, 100), { diff: -50, pct: -0.5, direction: "down" });
});

test("table totals line up with columns; only server totals are used", () => {
    const frame = {
        columns: [col("partner", "dimension", "many2one"), col("m1", "measure"), col("m2", "measure")],
        rows: [["A", 1, 2]], meta: { totals: { m1: 10 } },
    };
    assert.deepEqual(tableModel(frame).totals, [null, 10, null]);
    assert.equal(tableModel({ ...frame, meta: {} }).totals, null);
});

test("group refs: Others and unknown rows are not drillable", () => {
    const frame = { meta: { group_refs: [[7], ["__others__"], [null]] } };
    assert.deepEqual(groupRefAt(frame, 0), [7]);
    assert.equal(isDrillableRow(frame, 0), true);
    assert.equal(isDrillableRow(frame, 1), false);
    assert.equal(isDrillableRow(frame, 2), true); // "Not set" is a real group
    assert.equal(isDrillableRow(frame, 5), false);
    assert.equal(isDrillableRow(frame, null), false);
});

// -- theme and chart options ---------------------------------------------------------------

test("the theme is read from tokens, with fallbacks", () => {
    const theme = readTheme((name) => ({ "--lxb-text": " #111111 ", "--lxb-cat-2": "#222222" })[name]);
    assert.equal(theme.text, "#111111");
    assert.equal(theme.palette[1], "#222222");
    assert.equal(theme.palette[0], FALLBACK_THEME.palette[0]);
    assert.equal(theme.palette.length, 8);
    assert.equal(withAlpha("#0072b2", 0.5), "rgba(0, 114, 178, 0.5)");
    assert.equal(withAlpha("red", 0.5), "red");
});

const theme = readTheme(() => "");

test("Chart.js line / area / bar configs", () => {
    const model = seriesModel(daily);
    const area = buildChartJs({ kind: "area", model, theme, fmt, view: { smooth: true } });
    assert.equal(area.type, "line");
    assert.equal(area.data.datasets[0].fill, true);
    assert.equal(area.data.datasets[0].tension, 0.35);
    assert.deepEqual(area.data.labels, ["Oct 7", "Oct 8", "Oct 9"]);
    assert.equal(area.options.plugins.legend.display, false);
    const label = area.options.plugins.tooltip.callbacks.label({ datasetIndex: 0, dataset: { label: "Revenue" }, parsed: { y: 1234.5 } });
    assert.equal(label, "Revenue: 1,234.5 UZS");
    assert.equal(area.options.scales.y.ticks.callback(2500), "2.5K UZS");

    const bar = buildChartJs({ kind: "bar", model, theme, fmt, view: { orientation: "horizontal", stacked: true } });
    assert.equal(bar.type, "bar");
    assert.equal(bar.options.indexAxis, "y");
    assert.equal(bar.options.scales.x.ticks.maxTicksLimit, 6); // long labels must not run into each other
    assert.equal(bar.options.scales.x.stacked, true);
    assert.equal(bar.data.datasets[0].backgroundColor, theme.palette[0]);
});

test("a sparkline has no axes, legend or tooltip", () => {
    const spark = buildChartJs({ kind: "area", model: seriesModel(daily), theme, fmt, sparkline: true });
    assert.equal(spark.options.scales.x.display, false);
    assert.equal(spark.options.plugins.legend.display, false);
    assert.equal(spark.options.plugins.tooltip.enabled, false);
    assert.equal(spark.data.datasets[0].pointRadius, 0);
});

test("ECharts option escapes text and shares the palette", () => {
    const model = seriesModel(daily);
    const option = buildECharts({ kind: "area", model, theme, fmt, view: { smooth: true } });
    assert.deepEqual(option.color, theme.palette);
    assert.equal(option.series[0].smooth, true);
    assert.ok(option.series[0].areaStyle);
    assert.deepEqual(option.xAxis.data, ["Oct 7", "Oct 8", "Oct 9"]);
    const html = option.tooltip.formatter([{ axisValueLabel: "<b>x</b>", seriesName: "<script>", seriesIndex: 0, value: 5, marker: "<i></i>" }]);
    assert.ok(!html.includes("<script>") && !html.includes("<b>x</b>"));
    assert.ok(html.includes("&lt;script&gt;"));
});

test("category labels: non-time axes are plain text", () => {
    const frame = { columns: [col("p", "dimension", "many2one"), col("m1", "measure")], rows: [["Ali", 1], ["Not set", 2]], meta: {} };
    assert.deepEqual(categoryLabels(seriesModel(frame), "en"), ["Ali", "Not set"]);
});

// -- batching ----------------------------------------------------------------------------

test("requests within the window share one call, duplicates share the answer", async () => {
    const calls = [];
    const batch = createBatcher(async (keys) => {
        calls.push(keys);
        return Object.fromEntries(keys.map((k) => [k, k.toUpperCase()]));
    }, 5);
    const results = await Promise.all([batch.request("a"), batch.request("b"), batch.request("a")]);
    assert.deepEqual(results, ["A", "B", "A"]);
    assert.deepEqual(calls, [["a", "b"]]);
    assert.equal(await batch.request("c"), "C");
    assert.equal(calls.length, 2);
});

test("a failing call rejects every waiter", async () => {
    const batch = createBatcher(async () => {
        throw new Error("boom");
    }, 1);
    await assert.rejects(Promise.all([batch.request("a"), batch.request("b")]), /boom/);
});
