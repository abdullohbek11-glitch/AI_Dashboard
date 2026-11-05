/** @odoo-module **/
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { formatFull } from "../../lib/format.js";
import { isDrillableRow, numberOptionsFor, tableModel } from "../../lib/frame_model.js";
import { widgetRegistry } from "../widget_registry.js";

export class TableWidget extends Component {
    static template = "levelix_board.TableWidget";
    static props = { frame: Object, widget: Object, kind: { type: String, optional: true }, adapter: { type: String, optional: true }, onRowClick: { type: Function, optional: true } };

    get model() {
        return tableModel(this.props.frame);
    }

    get totalLabel() {
        return _t("Total");
    }

    cell(column, value) {
        if (column.role === "dimension") {
            return value === null || value === undefined ? "" : String(value);
        }
        return formatFull(value, numberOptionsFor(column, this.props.frame, user.lang || "en"));
    }

    totalCell(column, value, index) {
        if (index === 0) {
            return this.totalLabel;
        }
        return value === null ? "" : this.cell(column, value);
    }

    isNumeric(column) {
        return column.role === "measure";
    }

    canOpen(rowIndex) {
        return Boolean(this.props.onRowClick) && isDrillableRow(this.props.frame, rowIndex);
    }

    onKey(event, rowIndex) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.open(rowIndex);
        }
    }

    open(rowIndex) {
        if (this.canOpen(rowIndex)) {
            this.props.onRowClick(rowIndex);
        }
    }
}

widgetRegistry.add("table", { component: TableWidget, defaultSize: { w: 12, h: 10 }, adapter: () => "chartjs" });
