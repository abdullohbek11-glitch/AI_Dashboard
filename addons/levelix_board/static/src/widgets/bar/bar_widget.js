/** @odoo-module **/
import { ChartBody } from "../common/chart_body.js";
import { widgetRegistry } from "../widget_registry.js";

widgetRegistry.add("bar", { component: ChartBody, kind: "bar", defaultSize: { w: 12, h: 8 }, adapter: () => "chartjs" });
