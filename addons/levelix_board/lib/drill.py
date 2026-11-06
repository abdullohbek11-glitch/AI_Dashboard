"""Drill-down: what happens when a reader clicks a point of a chart.

The browser never sends a domain. It names a group (the ``group_refs`` entry it
got with the frame), the server finds that group again by running the widget,
takes the domain Odoo itself built for the group (``__extra_domain``), renames
its fields for the model that will be opened (``map``) and reads the records
with the reader's own rights.

Everything here is pure; the database part lives in ``runner.py`` / ``engine.py``.
"""
import difflib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pytz

from . import domain as domain_lib
from .catalog import Catalog, ModelInfo
from .errors import BoardError
from .i18n import t

ACTIONS = ("drill", "cross_filter", "filter", "open_record", "none")
IMPLEMENTED_ACTIONS = ("drill", "cross_filter", "none")  # the rest is accepted by name but not built yet
OPEN_AS = ("side_table", "dialog", "odoo_list")
MAX_DRILL_ROWS = 80
MAX_COLUMNS = 12
INTERACT_KEYS = ("on_click",)
CLICK_KEYS = ("action", "open_as", "model", "map", "columns")
UNSHOWN_TYPES = ("one2many", "many2many", "binary", "html", "json", "properties", "properties_definition")


@dataclass(frozen=True)
class DrillConfig:
    model: str
    map: dict
    columns: tuple
    open_as: str = "side_table"


# -- reading the widget's interact block ----------------------------------------

def parse(interact: dict) -> Optional[DrillConfig]:
    """The drill configuration of a widget, or ``None`` when clicking does not drill.

    Assumes the block passed ``check``; only the shape needed to run is read here.
    """
    click = (interact or {}).get("on_click")
    if not click or click.get("action") != "drill":
        return None
    return DrillConfig(click["model"], dict(click.get("map") or {}), tuple(click["columns"]),
                       click.get("open_as") or "side_table")


def _suggest(name: str, candidates) -> str:
    close = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return " Did you mean '%s'?" % close[0] if close else ""


def check(widget, source: ModelInfo, catalog: Catalog, path: str) -> list:
    """Validate ``interact`` and dry-run the drill (the field renaming) without touching data."""
    interact = widget.interact
    if not interact:
        return []
    ipath = path + ".interact"
    errors = []
    unknown = [k for k in interact if k not in INTERACT_KEYS]
    if unknown:
        return [BoardError("UNKNOWN_KEY", ipath, "Unknown key '%s' in 'interact'. Allowed: %s." % (unknown[0], ", ".join(INTERACT_KEYS)))]
    click = interact["on_click"]
    cpath = ipath + ".on_click"
    if not isinstance(click, dict):
        return [BoardError("BAD_SPEC", cpath, "'on_click' must be an object.")]
    for key in click:
        if key not in CLICK_KEYS:
            return [BoardError("UNKNOWN_KEY", cpath, "Unknown key '%s' in 'on_click'. Allowed: %s." % (key, ", ".join(CLICK_KEYS)))]
    action = click.get("action")
    if action not in ACTIONS:
        return [BoardError("BAD_ACTION", cpath + ".action", "Unknown click action %r. Allowed: %s." % (action, ", ".join(ACTIONS)))]
    if action not in IMPLEMENTED_ACTIONS:
        return [BoardError("UNSUPPORTED", cpath + ".action", "The click action '%s' is not available yet." % action)]
    if action == "none":
        return []
    if action == "cross_filter":  # clicking narrows the other widgets of the same data; it needs no model or columns
        extra = sorted(set(click) - {"action"})
        return [BoardError("BAD_SPEC", cpath, "A cross-filter needs only 'action'; remove %s." % ", ".join("'%s'" % k for k in extra))] if extra else []
    if click.get("open_as", "side_table") not in OPEN_AS:
        errors.append(BoardError("BAD_ACTION", cpath + ".open_as", "'open_as' must be one of: %s." % ", ".join(OPEN_AS)))

    target = _target_model(click, catalog, cpath, errors)
    if target is None:
        return errors
    _check_columns(click, target, cpath, errors)
    mapping = _check_map(click, source, target, cpath, errors)
    if mapping is None:
        return errors
    _dry_run(widget, mapping, target, cpath, errors)
    return errors


def _target_model(click: dict, catalog: Catalog, cpath: str, errors: list) -> Optional[ModelInfo]:
    name = click.get("model")
    if not isinstance(name, str) or not name:
        errors.append(BoardError("BAD_SPEC", cpath + ".model", "A drill needs a 'model' to open (for example 'sale.order')."))
        return None
    target = catalog.model(name)
    if target is None:
        errors.append(BoardError("UNKNOWN_MODEL", cpath + ".model", "Model '%s' does not exist." % name))
        return None
    if not target.accessible:
        errors.append(BoardError("NO_ACCESS", cpath + ".model", "You are not allowed to read '%s'." % target.label))
        return None
    return target


def _check_columns(click: dict, target: ModelInfo, cpath: str, errors: list):
    columns = click.get("columns")
    if not isinstance(columns, list) or not columns or not all(isinstance(c, str) for c in columns):
        errors.append(BoardError("BAD_SPEC", cpath + ".columns", "'columns' must be a non-empty list of field names."))
        return
    if len(columns) > MAX_COLUMNS or len(set(columns)) != len(columns):
        errors.append(BoardError("BAD_SPEC", cpath + ".columns", "Use between 1 and %d different columns." % MAX_COLUMNS))
    for name in columns:
        info = target.field(name)
        if info is None:
            errors.append(BoardError("UNKNOWN_FIELD", cpath + ".columns",
                                     "Model '%s' has no field '%s'.%s" % (target.name, name, _suggest(name, target.fields))))
        elif info.type in UNSHOWN_TYPES:
            errors.append(BoardError("DRILL_BAD_COLUMN", cpath + ".columns",
                                     "The field '%s' (%s) cannot be shown as a table column." % (info.label, info.type)))


def _check_map(click: dict, source: ModelInfo, target: ModelInfo, cpath: str, errors: list) -> Optional[dict]:
    mapping = click.get("map", {})
    if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
        errors.append(BoardError("BAD_SPEC", cpath + ".map", "'map' must be an object {source field: field of the opened model}."))
        return None
    for src, dst in mapping.items():
        if source.field(src.split(".")[0]) is None:
            errors.append(BoardError("UNKNOWN_FIELD", cpath + ".map",
                                     "Model '%s' has no field '%s'.%s" % (source.name, src, _suggest(src, source.fields))))
        if target.field(dst.split(".")[0]) is None:
            errors.append(BoardError("UNKNOWN_FIELD", cpath + ".map",
                                     "Model '%s' has no field '%s'.%s" % (target.name, dst, _suggest(dst, target.fields))))
    return mapping


def _dry_run(widget, mapping: dict, target: ModelInfo, cpath: str, errors: list):
    """Every field the drill domain can contain must have a counterpart in the opened model."""
    names = [d.field for d in widget.data.dimensions]
    try:
        names += [leaf[0] for leaf in domain_lib.leaves(domain_lib.parse(widget.data.domain))]
    except BoardError:
        return  # the domain itself is reported by the validator
    for name in dict.fromkeys(names):
        if translate_name(name, mapping, target) is None:
            errors.append(_unmapped(name, target, cpath + ".map"))


# -- renaming the domain ------------------------------------------------------------

def translate_name(name: str, mapping: dict, target: ModelInfo) -> Optional[str]:
    """The name of ``name`` in the opened model: via ``map``, or the same name if it exists there."""
    if name in mapping:
        return mapping[name]
    base, dot, rest = name.partition(".")
    if base in mapping:
        return mapping[base] + dot + rest  # keeps date parts: date.day_of_week -> date_order.day_of_week
    if target.field(base) is not None:
        return name
    return None


def _unmapped(name: str, target: ModelInfo, path: str) -> BoardError:
    return BoardError(
        "DRILL_UNMAPPED", path,
        "The field '%s' has no counterpart in '%s'. Add it to 'map', for example {\"%s\": \"<field of %s>\"}."
        % (name, target.name, name, target.name))


def translate_domain(domain, mapping: dict, target: ModelInfo, path: str = "interact.on_click.map") -> list:
    out = []
    for item in domain:
        if not domain_lib.is_leaf(item):
            out.append(item)
            continue
        name = translate_name(item[0], mapping, target)
        if name is None:
            raise _unmapped(item[0], target, path)
        out.append([name, item[1], item[2]])
    return out


# -- finding the clicked group ---------------------------------------------------------

def find_group(groups: list, dims: list, group_ref, dim_ref) -> dict:
    """The raw group a client's ``group_ref`` points at. The client never supplies a domain, only a choice among real groups."""
    if not isinstance(group_ref, (list, tuple)) or len(group_ref) != len(dims):
        raise BoardError("DRILL_BAD_REF", "group_ref", t("The clicked point does not match this widget."))
    wanted = list(group_ref)
    if any(isinstance(v, (list, tuple, dict)) for v in wanted):
        raise BoardError("DRILL_BAD_REF", "group_ref", t("The clicked point does not match this widget."))
    for group in groups:
        if [dim_ref(group.get(d.key)) for d in dims] == wanted:
            return group
    raise BoardError("DRILL_BAD_REF", "group_ref", t("This group no longer exists. Refresh the dashboard."))


# -- showing the records -----------------------------------------------------------------

def format_cell(info, value, tz: str):
    """A record value as the table shows it (names, labels, local time)."""
    if info.type == "boolean":
        return t("Yes") if value else t("No")
    if value is False or value is None:
        return ""
    if info.type == "many2one":
        return value[1]
    if info.type == "selection":
        return info.selection_labels.get(value, value)
    if info.type == "datetime" and isinstance(value, datetime):
        return pytz.utc.localize(value).astimezone(pytz.timezone(tz or "UTC")).strftime("%Y-%m-%d %H:%M")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def columns_meta(config: DrillConfig, target: ModelInfo) -> list:
    return [{"id": c, "label": target.field(c).label, "type": target.field(c).type} for c in config.columns]


def empty_result(config: DrillConfig, target: ModelInfo) -> dict:
    """What clicking a point with no records behind it (a filled-in empty day) opens."""
    return {
        "model": config.model, "open_as": config.open_as, "columns": columns_meta(config, target),
        "rows": [], "ids": [], "total": 0, "truncated": False,
        "action": {"type": "ir.actions.act_window", "name": target.label, "res_model": config.model,
                   "views": [[False, "list"], [False, "form"]], "domain": [["id", "=", False]], "target": "current"},
    }
