/** @odoo-module **/
// The web client picks an error dialog by the exact class name. Our own errors are user
// messages (a bad spec, a missing dashboard), so show them as a normal warning, not "Oops".
import { registry } from "@web/core/registry";
import { WarningDialog, odooExceptionTitleMap } from "@web/core/errors/error_dialogs";
import { _t } from "@web/core/l10n/translation";

const ERRORS = [
    "odoo.addons.levelix_board.lib.errors.BoardError",
    "odoo.addons.levelix_board.lib.errors.SpecInvalid",
];
for (const name of ERRORS) {
    registry.category("error_dialogs").add(name, WarningDialog);
    odooExceptionTitleMap.set(name, _t("Invalid Operation"));
}
