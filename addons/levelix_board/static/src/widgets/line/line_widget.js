/** @odoo-module **/
import { ChartBody } from "../common/chart_body.js";
import { widgetRegistry } from "../widget_registry.js";

// "line" and "area" share one body; smooth lines are drawn by ECharts, plain ones by Chart.js.
const adapter = (widget) => (widget.view && widget.view.smooth ? "echarts" : "chartjs");
widgetRegistry.add("line", { component: ChartBody, kind: "line", defaultSize: { w: 12, h: 8 }, adapter });
widgetRegistry.add("area", { component: ChartBody, kind: "area", defaultSize: { w: 12, h: 8 }, adapter });
