/** @odoo-module **/
// Turns a server Frame into what widgets draw. Display shaping only: every number comes from the server.
import { DATE_PARTS, formatDateLabel, formatPart } from "./format.js";

export const OTHERS_REF = "__others__";

const dims = (frame) => frame.columns.filter((c) => c.role === "dimension");
const measures = (frame) => frame.columns.filter((c) => c.role === "measure");

/** No rows, or nothing but empty measure cells. */
export function isEmptyFrame(frame) {
    if (!frame || !frame.rows || frame.rows.length === 0) {
        return true;
    }
    const offset = dims(frame).length;
    return frame.rows.every((row) => row.slice(offset).every((v) => v === null || v === undefined));
}

/**
 * Chart model: categories on the axis, one series per measure (one dimension) or per
 * value of the second dimension (two). `rowIndex` maps a point back to its frame row,
 * which is how a click finds its `group_ref`.
 */
export function seriesModel(frame) {
    const dimCols = dims(frame);
    const measureCols = measures(frame);
    const offset = dimCols.length;
    const categories = [];
    const seriesList = [];
    const refs = (frame.meta && frame.meta.group_refs) || [];
    const othersRow = (i) => Boolean(refs[i] && refs[i].includes(OTHERS_REF));
    if (dimCols.length <= 1) {
        frame.rows.forEach((row) => categories.push(dimCols.length ? row[0] : ""));
        measureCols.forEach((m, j) => {
            seriesList.push({
                name: m.label, measureId: m.id, type: m.type,
                data: frame.rows.map((row) => row[offset + j]),
                rowIndex: frame.rows.map((_, i) => i),
                muted: frame.rows.map((_, i) => othersRow(i)),
            });
        });
    } else {
        const seen = new Map();
        const keys = [];
        frame.rows.forEach((row) => {
            if (!seen.has(row[0])) {
                seen.set(row[0], categories.length);
                categories.push(row[0]);
            }
            if (!keys.includes(row[1])) {
                keys.push(row[1]);
            }
        });
        measureCols.forEach((m, j) => {
            keys.forEach((key) => {
                seriesList.push({
                    name: measureCols.length > 1 ? `${m.label} · ${key}` : String(key),
                    measureId: m.id, type: m.type,
                    data: categories.map(() => null),
                    rowIndex: categories.map(() => null),
                    muted: categories.map(() => false),
                });
                const target = seriesList[seriesList.length - 1];
                frame.rows.forEach((row, i) => {
                    if (row[1] === key) {
                        const c = seen.get(row[0]);
                        target.data[c] = row[offset + j];
                        target.rowIndex[c] = i;
                    }
                });
            });
        });
    }
    return { categories, series: seriesList, granularity: dimCols[0] && dimCols[0].granularity, dimType: dimCols[0] && dimCols[0].type };
}

/** Change against the comparison period; `null` when there is nothing to compare with. */
export function deltaInfo(current, previous) {
    if (current === null || current === undefined || previous === null || previous === undefined) {
        return null;
    }
    const diff = current - previous;
    return {
        diff,
        pct: previous === 0 ? null : diff / Math.abs(previous),
        direction: diff > 0 ? "up" : diff < 0 ? "down" : "flat",
    };
}

/** KPI cards: the last row is the current value (a KPI with a date axis also gets a trend line). */
export function kpiModel(frame) {
    const offset = dims(frame).length;
    const last = frame.rows.length ? frame.rows[frame.rows.length - 1] : [];
    const compare = frame.compare_rows && frame.compare_rows.length ? frame.compare_rows[frame.compare_rows.length - 1] : null;
    return measures(frame).map((m, j) => ({
        id: m.id, label: m.label, type: m.type,
        value: last[offset + j] === undefined ? null : last[offset + j],
        delta: compare ? deltaInfo(last[offset + j], compare[offset + j]) : null,
        trend: offset ? frame.rows.map((row) => row[offset + j]) : null,
    }));
}

/** Table: columns, rows and the totals row (server-computed, only for additive measures). */
export function tableModel(frame) {
    const totals = frame.meta && frame.meta.totals;
    return {
        columns: frame.columns,
        rows: frame.rows,
        totals: totals ? frame.columns.map((c) => (c.role === "measure" && c.id in totals ? totals[c.id] : null)) : null,
    };
}

export function groupRefAt(frame, rowIndex) {
    const refs = frame.meta && frame.meta.group_refs;
    return refs && rowIndex !== null && rowIndex !== undefined && refs[rowIndex] ? refs[rowIndex] : null;
}

/** A row that stands for a real group (the "Others" sum is not one). */
export function isDrillableRow(frame, rowIndex) {
    const ref = groupRefAt(frame, rowIndex);
    return Boolean(ref) && !ref.includes(OTHERS_REF);
}

/** Options for `formatNumber` / `formatFull` of one measure column: money gets the frame's currency, percent a sign. */
export function numberOptionsFor(column, frame, lang) {
    return {
        lang,
        percent: column.type === "percent",
        currency: column.type === "monetary" && frame.meta ? frame.meta.currency : null,
    };
}


// -- the other chart types ---------------------------------------------------------------------------------------------

const isPart = (column) => Boolean(column && DATE_PARTS.includes(column.granularity));

/** What a value of a dimension column is called on screen: weekday names, hours, month names, dates, or the text itself. */
export function labelOf(value, column, lang = "en") {
    if (!column) {
        return String(value);
    }
    if (isPart(column)) {
        return formatPart(value, column.granularity, lang);
    }
    if (column.type === "date" || column.type === "datetime") {
        return formatDateLabel(value, column.granularity, lang);
    }
    return String(value);
}

const weekdayFirst = (value) => (Number(value) + 6) % 7; // Monday first: Odoo's Sunday (0) goes last

function ordered(values, column) {
    const list = [...new Set(values)];
    if (list.every((v) => typeof v === "number")) {
        return list.sort((a, b) => (column && column.granularity === "day_of_week" ? weekdayFirst(a) - weekdayFirst(b) : a - b));
    }
    return list;
}

/** Heat map: two dimensions, one measure. `cells` are `[xIndex, yIndex, value, rowIndex]`. */
export function heatmapModel(frame, lang = "en") {
    const [dimX, dimY] = dims(frame);
    const [measure] = measures(frame);
    const xs = ordered(frame.rows.map((r) => r[0]), dimX);
    const ys = ordered(frame.rows.map((r) => r[1]), dimY);
    const cells = frame.rows.map((row, i) => [xs.indexOf(row[0]), ys.indexOf(row[1]), row[2], i]);
    const values = cells.map((c) => c[2]).filter((v) => typeof v === "number");
    return {
        xs: xs.map((v) => labelOf(v, dimX, lang)),
        ys: ys.map((v) => labelOf(v, dimY, lang)),
        cells, min: values.length ? Math.min(0, ...values) : 0, max: values.length ? Math.max(...values) : 0,
        measure, xLabel: dimX.label, yLabel: dimY.label,
    };
}

/** One bar per stage / group, in the order the rows arrive (largest first unless the widget orders them). */
export function funnelModel(frame, lang = "en") {
    const [dim] = dims(frame);
    const [measure] = measures(frame);
    const refs = (frame.meta && frame.meta.group_refs) || [];
    return {
        measure,
        items: frame.rows.map((row, i) => ({
            name: labelOf(row[0], dim, lang), value: row[1] || 0, rowIndex: i, muted: Boolean(refs[i] && refs[i].includes(OTHERS_REF)),
        })),
    };
}

/** Treemap: one dimension gives rectangles; two give rectangles inside rectangles (rows of the same first value share a parent). */
export function treemapModel(frame, lang = "en") {
    const dimCols = dims(frame);
    const [measure] = measures(frame);
    const offset = dimCols.length;
    const refs = (frame.meta && frame.meta.group_refs) || [];
    const leaf = (row, i, nameAt) => ({
        name: labelOf(row[nameAt], dimCols[nameAt], lang), value: row[offset] || 0, rowIndex: i,
        muted: Boolean(refs[i] && refs[i].includes(OTHERS_REF)),
    });
    if (dimCols.length === 1) {
        return { measure, nodes: frame.rows.map((row, i) => leaf(row, i, 0)) };
    }
    const parents = new Map();
    frame.rows.forEach((row, i) => {
        const key = row[0];
        if (!parents.has(key)) {
            parents.set(key, { name: labelOf(key, dimCols[0], lang), children: [] });
        }
        parents.get(key).children.push(leaf(row, i, 1));
    });
    return { measure, nodes: [...parents.values()].map((p) => ({ ...p, value: p.children.reduce((sum, c) => sum + c.value, 0) })) };
}

/**
 * Waterfall: every row is a step up or down from where the last one ended; the final bar is the total.
 * `steps` are `{name, from, to, delta, rowIndex}`; the total has `rowIndex: null` (it is not a group).
 */
export function waterfallModel(frame, lang = "en") {
    const [dim] = dims(frame);
    const [measure] = measures(frame);
    let running = 0;
    const steps = frame.rows.map((row, i) => {
        const delta = row[1] || 0;
        const step = { name: labelOf(row[0], dim, lang), from: running, to: running + delta, delta, rowIndex: i, total: false };
        running += delta;
        return step;
    });
    steps.push({ name: null, from: 0, to: running, delta: running, rowIndex: null, total: true });
    return { measure, steps };
}

/** Scatter: one point per group; the first measure is the horizontal axis, the second the vertical one. */
export function scatterModel(frame, lang = "en") {
    const [dim] = dims(frame);
    const [xMeasure, yMeasure] = measures(frame);
    return {
        xMeasure, yMeasure,
        points: frame.rows.map((row, i) => ({ name: labelOf(row[0], dim, lang), x: row[1], y: row[2], rowIndex: i })),
    };
}

/** Columns and a line on a second axis: the measure named by `view.line` (the last one by default) is the line. */
export function comboModel(frame, view = {}, lang = "en") {
    const [dim] = dims(frame);
    const cols = measures(frame);
    const lineId = view.line || cols[cols.length - 1].id;
    const make = (m, j) => ({ name: m.label, measureId: m.id, type: m.type, data: frame.rows.map((row) => row[1 + j]) });
    const all = cols.map(make);
    return {
        categories: frame.rows.map((row) => labelOf(row[0], dim, lang)),
        rowIndex: frame.rows.map((_, i) => i),
        columns: all.filter((s) => s.measureId !== lineId),
        line: all.find((s) => s.measureId === lineId),
    };
}

/** Gauge: the value against `view.target`. */
export function gaugeModel(frame, view = {}) {
    const [measure] = measures(frame);
    const value = frame.rows.length ? frame.rows[0][0] : null;
    const target = Number(view.target) || 0;
    return { measure, value, target, share: target > 0 && value !== null ? value / target : null, max: Math.max(target, value || 0) || 1 };
}

/** The earlier period as dashed series, aligned bucket by bucket with the current one (a comparison has at most one axis). */
export function compareSeries(frame, nameOf = (label) => label) {
    if (!frame.compare_rows) {
        return [];
    }
    const offset = dims(frame).length;
    return measures(frame).map((m, j) => ({
        name: nameOf(m.label), measureId: m.id, type: m.type, data: frame.compare_rows.map((row) => row[offset + j]),
    }));
}
