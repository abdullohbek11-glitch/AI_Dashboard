/** @odoo-module **/
import { loadBundle, loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { buildChartJs, buildECharts } from "../lib/chart_options.js";
import { MORE_KINDS } from "../lib/chart_options_more.js";

/**
 * What every chart library adapter provides. Widgets know only this interface.
 *   mount(el, spec)   draw into `el`;  spec = { kind, model, theme, fmt, view, animate }
 *   update(spec)      redraw with new data or theme
 *   onPointClick(cb)  cb({ seriesIndex, pointIndex }) when a point (or its column) is clicked, or cb({ rowIndex }) when the
 *                     chart knows the frame row itself (heat map cells, funnel stages ...)
 *   resize(), dispose()
 */
export class ChartAdapter {
    async mount() {}
    update() {}
    onPointClick(callback) {
        this.clickCallback = callback;
    }
    resize() {}
    dispose() {}
}

export class ChartJsAdapter extends ChartAdapter {
    async mount(el, spec) {
        await loadBundle("web.chartjs_lib");
        this.canvas = document.createElement("canvas");
        el.appendChild(this.canvas);
        this.draw(spec);
    }

    draw(spec) {
        this.chart?.destroy();
        const config = buildChartJs(spec);
        const axis = config.options.indexAxis === "y" ? "y" : "x";
        const slices = config.type === "pie" || config.type === "doughnut";
        config.options.onClick = (event, _elements, chart) => {
            // the nearest point of the clicked column, even when the pointer is not exactly on it; a slice must be hit itself
            const hits = chart.getElementsAtEventForMode(event, "nearest", { intersect: slices, axis }, false);
            if (hits.length && this.clickCallback) {
                this.clickCallback({ seriesIndex: hits[0].datasetIndex, pointIndex: hits[0].index });
            }
        };
        this.chart = new window.Chart(this.canvas, config);
    }

    update(spec) {
        this.draw(spec);
    }

    resize() {
        this.chart?.resize();
    }

    dispose() {
        this.chart?.destroy();
        this.canvas?.remove();
        this.chart = this.canvas = null;
    }
}

export class EChartsAdapter extends ChartAdapter {
    async mount(el, spec) {
        await loadJS("/levelix_board/static/lib/echarts/echarts.min.js");
        this.chart = window.echarts.init(el, null, { renderer: "canvas" });
        this.byDatum = MORE_KINDS.includes(spec.kind);
        if (this.byDatum) { // every datum of these types carries its frame row
            this.chart.on("click", (event) => {
                const rowIndex = event.data && event.data.rowIndex;
                if (this.clickCallback && rowIndex !== undefined && rowIndex !== null) {
                    this.clickCallback({ rowIndex });
                }
            });
        } else {
            this.chart.getZr().on("click", (event) => this.handleClick(event));
        }
        this.update(spec);
    }

    update(spec) {
        this.model = spec.model;
        this.chart.setOption(buildECharts(spec), true);
    }

    handleClick(event) {
        const point = [event.offsetX, event.offsetY];
        if (!this.clickCallback || !this.chart.containPixel("grid", point)) {
            return;
        }
        const pointIndex = Math.round(this.chart.convertFromPixel({ gridIndex: 0 }, point)[0]);
        if (pointIndex < 0 || pointIndex >= this.model.categories.length) {
            return;
        }
        // several series: the one whose point is closest to the pointer vertically
        let seriesIndex = 0;
        let best = Infinity;
        this.model.series.forEach((series, index) => {
            const value = series.data[pointIndex];
            if (value === null || value === undefined) {
                return;
            }
            const distance = Math.abs(this.chart.convertToPixel({ gridIndex: 0 }, [pointIndex, value])[1] - point[1]);
            if (distance < best) {
                best = distance;
                seriesIndex = index;
            }
        });
        this.clickCallback({ seriesIndex, pointIndex });
    }

    resize() {
        this.chart?.resize();
    }

    dispose() {
        this.chart?.dispose();
        this.chart = null;
    }
}

const charts = registry.category("levelix_board_charts");
charts.add("chartjs", ChartJsAdapter);
charts.add("echarts", EChartsAdapter);
