/** @odoo-module **/
// Turns a server Frame into what widgets draw. Display shaping only: every number comes from the server.

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
