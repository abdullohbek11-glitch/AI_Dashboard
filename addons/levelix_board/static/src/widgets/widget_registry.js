/** @odoo-module **/
import { registry } from "@web/core/registry";

/**
 * A widget type is one folder under `widgets/` plus one entry here:
 *   registry.category("levelix_board_widgets").add("area", { component, defaultSize: {w, h}, adapter: (widget) => "chartjs" | "echarts" })
 * Nothing else has to change to add a type (the Python side lists its shape in `lib/spec.py`).
 */
export const widgetRegistry = registry.category("levelix_board_widgets");

export function definitionFor(type) {
    return widgetRegistry.contains(type) ? widgetRegistry.get(type) : null;
}

export function defaultSizeOf(widget) {
    const definition = definitionFor(widget.type);
    return definition ? definition.defaultSize : { w: 12, h: 8 };
}
