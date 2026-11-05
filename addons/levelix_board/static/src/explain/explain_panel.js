/** @odoo-module **/
import { Component, useState } from "@odoo/owl";

/** The "how was this calculated" lines. The text is written by the server from the query that really ran. */
export class ExplainPanel extends Component {
    static template = "levelix_board.ExplainPanel";
    static props = { lines: Array, onClose: Function };

    setup() {
        this.state = useState({ showDetails: false });
    }

    get important() {
        return this.props.lines.filter((line) => !line.detail);
    }

    get details() {
        return this.props.lines.filter((line) => line.detail);
    }
}
