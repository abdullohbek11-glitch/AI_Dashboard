/** @odoo-module **/
// Moving and resizing widgets on the 24-column grid while editing. Pure: tested without a browser.
// A cell is { id, x, y, w, h }. Whatever the reader drops a widget on is pushed out of the way, and gaps close upwards.
import { GRID_COLUMNS } from "./grid.js";

export const MIN_W = 3;
export const MIN_H = 3;

/** Size of one column step and one row step in pixels (a cell plus the gap after it). */
export function pitchOf(gridWidth, gap = 16, rowUnit = 40, columns = GRID_COLUMNS) {
    return { col: (gridWidth - (columns - 1) * gap) / columns + gap, row: rowUnit + gap };
}

/** A pointer movement in pixels as whole cells. */
export function cellsMoved(dxPx, dyPx, pitch) {
    return { dx: Math.round(dxPx / pitch.col) || 0, dy: Math.round(dyPx / pitch.row) || 0 }; // `|| 0` turns -0 into 0
}

const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/**
 * No overlaps, no gaps above. The `pinnedId` widget keeps exactly where it was put and the others give way (they are
 * placed top to bottom, each at the highest free row). Returns new cells in the same order.
 */
export function settle(cells, pinnedId = null) {
    const order = [...cells].sort((a, b) => (a.id === pinnedId ? -1 : b.id === pinnedId ? 1 : a.y - b.y || a.x - b.x));
    const placed = [];
    for (const cell of order) {
        const next = { ...cell };
        if (cell.id !== pinnedId) {
            next.y = 0;
            while (placed.some((other) => overlaps(other, next))) {
                next.y += 1;
            }
        }
        placed.push(next);
    }
    const byId = new Map(placed.map((c) => [c.id, c]));
    return cells.map((c) => byId.get(c.id));
}

/** The widget moved by whole cells (kept inside the page), the rest rearranged around it. */
export function moved(cells, id, dx, dy) {
    const next = cells.map((c) => {
        if (c.id !== id) {
            return c;
        }
        return { ...c, x: Math.min(GRID_COLUMNS - c.w, Math.max(0, c.x + dx)), y: Math.max(0, c.y + dy) };
    });
    return settle(next, id);
}

/** The widget made wider / taller by whole cells (never smaller than MIN_W x MIN_H, never past the page), the rest rearranged. */
export function resized(cells, id, dw, dh) {
    const next = cells.map((c) => {
        if (c.id !== id) {
            return c;
        }
        return { ...c, w: Math.min(GRID_COLUMNS - c.x, Math.max(MIN_W, c.w + dw)), h: Math.max(MIN_H, c.h + dh) };
    });
    return settle(next, id);
}

/** `{ id: {x, y, w, h} }`, the shape the server stores in each widget's `grid`. */
export function gridOf(cells) {
    return Object.fromEntries(cells.map((c) => [c.id, { x: c.x, y: c.y, w: c.w, h: c.h }]));
}

/** Where a new widget goes: at the end, in the first free row below everything, as wide as asked. */
export function appended(cells, id, size) {
    const bottom = cells.reduce((low, c) => Math.max(low, c.y + c.h), 0);
    return [...cells, { id, x: 0, y: bottom, w: Math.min(GRID_COLUMNS, size.w), h: size.h }];
}
