/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpcMessage } from "../core/board_data.js";
import { DrillPanel } from "../drill/drill_panel.js";
import { gridStyle, mobileOrder, placeWidgets } from "../lib/grid.js";
import { BoardWidget } from "../widgets/shell/board_widget.js";
import { defaultSizeOf } from "../widgets/widget_registry.js";

/** Full-screen dashboard page: the list of dashboards, and one dashboard with its widgets. */
export class BoardPage extends Component {
    static template = "levelix_board.BoardPage";
    static components = { BoardWidget, DrillPanel };
    static props = ["*"];

    setup() {
        this.data = useService("levelix_board.data");
        this.action = useService("action");
        this.theme = useService("levelix_board.theme");
        this.themeState = useState(this.theme.state);
        this.state = useState({ view: "list", boards: [], board: null, error: null, loading: true, reloadKey: 0, drill: null });
        onWillStart(async () => {
            await this.showList();
            const context = (this.props.action && this.props.action.context) || {};
            const params = (this.props.action && this.props.action.params) || {};
            const boardId = context.board_id || params.board_id;
            if (boardId) {
                await this.open(boardId);
            }
        });
    }

    async showList() {
        this.state.view = "list";
        this.state.board = null;
        this.state.drill = null;
        this.state.error = null;
        try {
            this.state.boards = await this.data.list();
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
        this.state.loading = false;
    }

    async open(boardId) {
        this.state.error = null;
        this.state.drill = null;
        try {
            this.state.board = await this.data.load(boardId);
            this.state.view = "board";
            this.state.reloadKey += 1;
        } catch (error) {
            this.state.error = rpcMessage(error);
        }
    }

    refresh() {
        this.state.reloadKey += 1;
    }

    /** Widgets with their grid cell and mobile reading order. */
    get cells() {
        const widgets = (this.state.board.spec.widgets || []);
        const cells = placeWidgets(widgets, defaultSizeOf);
        const order = new Map(mobileOrder(cells).map((cell, index) => [cell.id, index]));
        const byId = new Map(widgets.map((w) => [w.id, w]));
        return cells.map((cell) => ({ widget: byId.get(cell.id), style: gridStyle(cell, order.get(cell.id)) }));
    }

    openDrill(request) {
        this.state.drill = { ...request, key: `${request.widgetId}:${JSON.stringify(request.groupRef)}` };
    }

    manage() {
        this.action.doAction("levelix_board.action_levelix_board");
    }
}

registry.category("actions").add("levelix_board.board_page", BoardPage);
