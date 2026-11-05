// Only the chart types and components the dashboard uses (see technical document, section 5.2).
import * as echarts from "echarts/core";
import { BarChart, CustomChart, FunnelChart, GaugeChart, HeatmapChart, LineChart, PieChart, ScatterChart, TreemapChart } from "echarts/charts";
import { AriaComponent, DatasetComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
    BarChart, CustomChart, FunnelChart, GaugeChart, HeatmapChart, LineChart, PieChart, ScatterChart, TreemapChart,
    AriaComponent, DatasetComponent, GridComponent, LegendComponent, MarkLineComponent, TitleComponent, TooltipComponent, VisualMapComponent,
    CanvasRenderer,
]);
window.echarts = echarts;
