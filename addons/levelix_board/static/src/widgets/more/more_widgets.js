/** @odoo-module **/
import { ChartBody } from "../common/chart_body.js";
import { widgetRegistry } from "../widget_registry.js";

// The remaining chart types share the chart body. A pie is drawn by Chart.js, the others by ECharts (technical document 5.2).
const chartjs = () => "chartjs";
const echarts = () => "echarts";
const add = (type, size, adapter) => widgetRegistry.add(type, { component: ChartBody, kind: type, defaultSize: size, adapter });

add("pie", { w: 8, h: 8 }, chartjs);
add("heatmap", { w: 12, h: 8 }, echarts);
add("funnel", { w: 8, h: 8 }, echarts);
add("treemap", { w: 12, h: 8 }, echarts);
add("gauge", { w: 6, h: 7 }, echarts);
add("waterfall", { w: 12, h: 8 }, echarts);
add("scatter", { w: 12, h: 8 }, echarts);
add("combo", { w: 12, h: 8 }, echarts);
