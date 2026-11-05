/** @odoo-module **/
// 24-column grid maths. Pure.

export const GRID_COLUMNS = 24;
export const ROW_UNIT_PX = 40;
export const MOBILE_BREAKPOINT_PX = 768;
export const DEFAULT_SIZE = { w: 12, h: 8 };

const toInt = (value, fallback) => (Number.isFinite(value) ? Math.round(value) : fallback);

/** A usable cell: whole numbers, inside the 24 columns, at least 1 high. */
export function clampCell(cell, fallback = DEFAULT_SIZE) {
    const w = Math.min(GRID_COLUMNS, Math.max(1, toInt(cell && cell.w, fallback.w)));
    const h = Math.max(1, toInt(cell && cell.h, fallback.h));
    const x = Math.min(GRID_COLUMNS - w, Math.max(0, toInt(cell && cell.x, 0)));
    const y = Math.max(0, toInt(cell && cell.y, 0));
    return { x, y, w, h };
}

/**
 * Cell of every widget. A widget with a `grid` keeps it; the others flow left to right
 * below everything placed so far (wrapping at 24 columns), in spec order.
 * `sizeOf(widget)` gives the default size of a widget type.
 */
export function placeWidgets(widgets, sizeOf = () => DEFAULT_SIZE) {
    const placed = new Map();
    let bottom = 0;
    for (const widget of widgets) {
        if (widget.grid) {
            const cell = clampCell(widget.grid, sizeOf(widget));
            placed.set(widget.id, cell);
            bottom = Math.max(bottom, cell.y + cell.h);
        }
    }
    let x = 0;
    let rowTop = bottom;
    let rowHeight = 0;
    for (const widget of widgets) {
        if (widget.grid) {
            continue;
        }
        const size = clampCell({ ...sizeOf(widget), x: 0, y: 0 }, DEFAULT_SIZE);
        if (x + size.w > GRID_COLUMNS) {
            x = 0;
            rowTop += rowHeight;
            rowHeight = 0;
        }
        placed.set(widget.id, { x, y: rowTop, w: size.w, h: size.h });
        x += size.w;
        rowHeight = Math.max(rowHeight, size.h);
    }
    return widgets.map((widget) => ({ id: widget.id, ...placed.get(widget.id) }));
}

/** Reading order for a single column: top to bottom, then left to right. */
export function mobileOrder(cells) {
    return [...cells].sort((a, b) => a.y - b.y || a.x - b.x);
}

/** Custom properties, not grid-column/row: the stylesheet uses them on wide screens and ignores them on one column. */
export function gridStyle(cell, order = 0) {
    return `--lxb-x: ${cell.x + 1}; --lxb-y: ${cell.y + 1}; --lxb-w: ${cell.w}; --lxb-h: ${cell.h}; --lxb-order: ${order};`;
}
