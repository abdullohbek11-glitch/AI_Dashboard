"""Everything the assistant can do, always as the current user: plain ORM calls, so access rights,
record rules and company rules apply unchanged. Other modules add tools by extending ``_tool_defs``
and writing a ``_tool_<name>`` method (and, when the result carries data, a ``_to_ai_<name>``)."""
import ast
import json
import re
from datetime import datetime

from odoo import api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

from ..lib import dates, privacy

# Technical or sensitive models the assistant never touches, whatever the ACLs say.
BLOCKED_PREFIXES = (
    "ir.", "bus.", "base.", "levelix.ai.", "res.config", "res.users.apikeys", "res.users.log",
    "auth.", "auth_", "iap.", "mail.", "fetchmail.", "payment.provider", "payment.token", "res.device",
    "change.password", "base_import.",
)
MAX_ROWS = 50
MAX_GROUPS = 200
MAX_GROUPBY = 2
MAX_AGGREGATES = 4
MAX_FIELDS = 90
MAX_CHOICES = 8
AGGREGATE_FUNCTIONS = ("sum", "avg", "min", "max", "count_distinct")
GRANULARITIES = ("day", "week", "month", "quarter", "year")
FIELD_ATTRIBUTES = ["string", "type", "relation", "selection", "store", "aggregator", "groupable", "required"]
HIDDEN_TYPES = ("binary", "json", "properties", "properties_definition", "html")

_STRING = {"type": "string"}
FIND_MODELS = {
    "name": "find_models",
    "description": "Find business objects by what the user calls them (e.g. 'invoices', 'leads', 'stock'). "
                   "Returns technical model names with their labels; reporting models (report: true) come first and are "
                   "usually the best source for totals. Call this first when unsure which model holds the data.",
    "parameters": {"type": "object", "properties": {"query": _STRING}, "required": ["query"]},
}
DESCRIBE_MODEL = {
    "name": "describe_model",
    "description": "List the stored fields of a model the current user can read: name, type, label, relation, selection "
                   "values and how a number may be aggregated. Call before filtering or grouping on a model you have not described yet.",
    "parameters": {"type": "object", "properties": {"model": _STRING}, "required": ["model"]},
}
SEARCH_RECORDS = {
    "name": "search_records",
    "description": "Read records. 'domain' is a JSON list of [field, operator, value] triples (prefix operators '|', '&', '!' allowed). "
                   "Set show=table to display the rows to the user as a table.",
    "parameters": {
        "type": "object",
        "properties": {
            "model": _STRING,
            "domain": {"type": "string", "description": "JSON list, e.g. [[\"state\",\"=\",\"sale\"]]. Use [] for all."},
            "fields": {"type": "array", "items": _STRING, "description": "Up to 8 field names."},
            "order": {"type": "string", "description": "e.g. 'amount_total desc'"},
            "limit": {"type": "integer", "description": "Max %d." % MAX_ROWS},
            "show": {"type": "string", "enum": ["none", "table"]},
            "title": {"type": "string", "description": "Short title of the table, in the user's language."},
        },
        "required": ["model", "domain"],
    },
}
AGGREGATE = {
    "name": "aggregate",
    "description": "Count, sum or average records, optionally grouped. Always prefer this over reading rows and adding them up. "
                   "groupby items are field names, with ':day|week|month|quarter|year' for dates. "
                   "aggregates are '__count' or 'field:sum|avg|min|max|count_distinct' (only fields marked summable can be summed). "
                   "show=chart draws the result, show=kpi shows one big number (no groupby), show=table lists the groups.",
    "parameters": {
        "type": "object",
        "properties": {
            "model": _STRING,
            "domain": {"type": "string", "description": "JSON list of triples. Use [] for all. Dates as YYYY-MM-DD."},
            "groupby": {"type": "array", "items": _STRING},
            "aggregates": {"type": "array", "items": _STRING},
            "order": {"type": "string", "description": "e.g. 'amount_total:sum desc'"},
            "limit": {"type": "integer"},
            "show": {"type": "string", "enum": ["none", "chart", "kpi", "table"]},
            "chart_type": {"type": "string", "enum": ["bar", "line", "pie"]},
            "title": {"type": "string", "description": "Short title, in the user's language."},
        },
        "required": ["model", "domain", "aggregates"],
    },
}
PICK_RECORD = {
    "name": "pick_record",
    "description": "Let the user choose one record by name (a customer, a product...) when you need its identity. The matches are shown "
                   "to the user only; you do not see them. Stop and wait: the user's next message tells you which record they chose.",
    "parameters": {"type": "object", "properties": {"model": _STRING, "query": _STRING}, "required": ["model", "query"]},
}
ASK_USER = {
    "name": "ask_user",
    "description": "Ask the user one short clarifying question with two to four answer buttons. Stop and wait for their reply.",
    "parameters": {
        "type": "object",
        "properties": {"question": _STRING, "options": {"type": "array", "items": _STRING}},
        "required": ["question", "options"],
    },
}


class LevelixAiTools(models.AbstractModel):
    _name = "levelix.ai.tools"
    _description = "Levelix AI Tools"

    # ------------------------------------------------------------------
    # The registry
    # ------------------------------------------------------------------
    @api.model
    def _tool_defs(self):
        """Every tool this installation has. Modules extend: ``return super()._tool_defs() + [MY_TOOL]``."""
        return [FIND_MODELS, DESCRIBE_MODEL, SEARCH_RECORDS, AGGREGATE, PICK_RECORD, ASK_USER]

    @api.model
    def _available_tools(self):
        """The tools offered to the model: all of them, minus what the privacy mode forbids."""
        defs = self._tool_defs()
        allowed = privacy.tools_for(self.env["levelix.ai.engine"]._privacy(), [d["name"] for d in defs])
        return [d for d in defs if d["name"] in allowed]

    @api.model
    def _run(self, name, args, message):
        """Execute one tool. Returns ``(result for the screen, side effects)``; side effects may carry
        ``block``, ``explain``, ``model`` and ``count``. Only registered, offered tools can run."""
        if name not in [d["name"] for d in self._available_tools()]:
            raise UserError(self.env._("Unknown tool: %s", name))
        handler = getattr(self, "_tool_%s" % name, None)
        if not handler:
            raise UserError(self.env._("Unknown tool: %s", name))
        if not isinstance(args, dict):
            raise UserError(self.env._("The tool arguments must be an object."))
        return handler(args, message)

    @api.model
    def _to_ai(self, name, result):
        """The result as the model may read it (privacy mode). A module may define ``_to_ai_<name>``."""
        shaper = getattr(self, "_to_ai_%s" % name, None)
        if shaper:
            return shaper(result)
        return privacy.to_ai(name, result, self.env["levelix.ai.engine"]._privacy())

    # ------------------------------------------------------------------
    # Guards and helpers
    # ------------------------------------------------------------------
    @api.model
    def _model(self, name, operation="read"):
        if not isinstance(name, str) or name not in self.env or name.startswith(BLOCKED_PREFIXES):
            raise UserError(self.env._("Unknown model: %s", name))
        Model = self.env[name]
        if Model._abstract or Model._transient:
            raise UserError(self.env._("Unknown model: %s", name))
        Model.check_access(operation)
        return Model

    @api.model
    def _label(self, name):
        return self.env["ir.model"]._get(name).name or self.env[name]._description or name

    @api.model
    def _is_report(self, Model):
        return not Model._auto and Model._name.endswith(".report")

    @api.model
    def _json(self, value, expected, fallback):
        if value in (None, "", False):
            return fallback
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                try:
                    value = ast.literal_eval(value)
                except (ValueError, SyntaxError) as error:
                    raise UserError(self.env._("Not valid JSON: %s", value[:120])) from error
        if not isinstance(value, expected):
            raise UserError(self.env._("Unexpected value: %s", str(value)[:120]))
        return value

    @api.model
    def _fields_info(self, Model):
        return Model.fields_get(attributes=FIELD_ATTRIBUTES)

    @api.model
    def _tz(self):
        return self.env.context.get("tz") or self.env.user.tz or "UTC"

    @api.model
    def _domain(self, Model, value, info=None):
        """A domain from the model's JSON, with day-only dates on datetime fields turned into whole local days."""
        domain = self._json(value, (list, tuple), [])
        info = info or self._fields_info(Model)
        try:
            return dates.resolve_domain(domain, lambda name: (info.get(name) or {}).get("type"), self._tz(), datetime.utcnow())
        except ValueError as error:
            raise UserError(self.env._("A date in the filter cannot be read: %s", error)) from error

    @api.model
    def _cell(self, value, info):
        """A value as the user would read it."""
        kind = info.get("type")
        if value is False or value is None:
            return False if kind == "boolean" else ""
        if kind == "many2one":
            return value[1] if isinstance(value, (list, tuple)) else value
        if kind in ("one2many", "many2many"):
            return len(value)
        if kind == "selection":
            return dict(info.get("selection") or []).get(value, value)
        if kind == "html":
            value = html2plaintext(value)
        if isinstance(value, str) and len(value) > 200:
            return value[:200] + "…"
        return value

    @api.model
    def _describe_domain(self, Model, domain):
        """Filters in the user's words, for the "how I got this" section."""
        info = self._fields_info(Model)
        parts = []
        for leaf in domain:
            if not isinstance(leaf, (list, tuple)) or len(leaf) != 3:
                continue
            field, operator, value = leaf
            root = str(field).split(".")[0]
            label = info.get(root, {}).get("string", field)
            if info.get(root, {}).get("type") == "selection" and not isinstance(value, (list, tuple)):
                value = dict(info[root].get("selection") or []).get(value, value)
            parts.append(f"{label} {operator} {value}")
        return parts

    # ------------------------------------------------------------------
    # Read tools
    # ------------------------------------------------------------------
    def _tool_find_models(self, args, message):
        words = [w for w in re.split(r"\W+", str(args.get("query") or "").lower()) if len(w) > 1]
        found = []
        for name in self.env.registry:
            Model = self.env[name]
            if Model._abstract or Model._transient or name.startswith(BLOCKED_PREFIXES):
                continue
            label = self._label(name)
            haystack = f"{label} {name} {Model._description}".lower()
            score = sum(1 for w in words if w in haystack or w.rstrip("s") in haystack)  # crude stemming: "invoices" finds "invoice"
            if score and Model.has_access("read"):
                report = self._is_report(Model)
                found.append((not report, -score, len(name), name, label, report))
        found.sort()
        return {"models": [{"model": n, "label": l, "report": r} for _x, _s, _l, n, l, r in found[:15]]}, {}

    def _tool_describe_model(self, args, message):
        Model = self._model(args.get("model"))
        fields = []
        for name, info in self._fields_info(Model).items():
            if not info.get("store") or info["type"] in HIDDEN_TYPES or name.startswith("__"):
                continue
            entry = {"name": name, "type": info["type"], "label": info["string"]}
            if info.get("relation"):
                entry["relation"] = info["relation"]
            if info.get("selection"):
                entry["values"] = [list(pair) for pair in info["selection"]][:20]
            if info["type"] in ("integer", "float", "monetary"):
                entry["summable"] = info.get("aggregator") == "sum"
            fields.append((not info.get("required"), name, entry))
        fields.sort(key=lambda f: f[:2])
        return {
            "model": Model._name, "label": self._label(Model._name), "report": self._is_report(Model),
            "fields": [f[2] for f in fields[:MAX_FIELDS]],
            "note": "Only stored fields are listed; 'summable: false' numbers (prices, rates) can be averaged, not added up.",
        }, {"model": Model._name}

    def _tool_search_records(self, args, message):
        Model = self._model(args.get("model"))
        info = self._fields_info(Model)
        domain = self._domain(Model, args.get("domain"), info)
        names = [f for f in (args.get("fields") or []) if isinstance(f, str) and f in info and info[f]["type"] not in HIDDEN_TYPES][:8]
        names = names or ["display_name"]
        limit = max(1, min(int(args.get("limit") or 20), MAX_ROWS))
        rows = Model.search_read(domain, names, limit=limit, order=args.get("order") or None)
        total = len(rows) if len(rows) < limit else Model.search_count(domain)
        table = [[self._cell(row.get(f), info.get(f, {})) for f in names] for row in rows]
        columns = [{"name": f, "label": info.get(f, {}).get("string", f), "type": info.get(f, {}).get("type", "char")} for f in names]
        spec = {"model": Model._name, "domain": domain}
        side = {
            "model": Model._name, "count": total,
            "explain": {"label": self._label(Model._name), "filters": self._describe_domain(Model, domain), "count": total, "spec": spec},
        }
        if args.get("show") == "table":
            side["block"] = {
                "type": "table", "title": args.get("title") or self._label(Model._name),
                "columns": columns, "rows": table, "ids": [row["id"] for row in rows], "total": total, "spec": spec,
            }
        return {
            "total": total, "returned": len(rows), "columns": names,
            "rows": [[row["id"]] + line for row, line in zip(rows, table)],
            "note": "first value of each row is the record id",
        }, side

    def _check_aggregates(self, Model, info, aggregates):
        """Every measure must make sense for its field, or the number would be silently wrong."""
        for spec in aggregates:
            if spec == "__count":
                continue
            field, _sep, function = spec.partition(":")
            meta = info.get(field)
            if not meta or not meta.get("store"):
                raise UserError(self.env._("Model %(model)s has no stored field '%(field)s'.", model=Model._name, field=field))
            if function not in AGGREGATE_FUNCTIONS:
                raise UserError(self.env._("Use '%(field)s:' with one of: %(options)s.", field=field, options=", ".join(AGGREGATE_FUNCTIONS)))
            if function == "sum" and meta.get("aggregator") != "sum":
                raise UserError(self.env._("'%s' cannot be added up (it holds a price or a rate). Use avg, min or max.", meta["string"]))
            if function in ("avg", "min", "max") and meta["type"] not in ("integer", "float", "monetary", "date", "datetime"):
                raise UserError(self.env._("'%(field)s' is not a number; '%(function)s' does not apply.", field=meta["string"], function=function))

    def _check_groupby(self, Model, info, groupby):
        for spec in groupby:
            field, _sep, granularity = spec.partition(":")
            meta = info.get(field.split(".")[0])
            if not meta or not meta.get("store") or meta.get("groupable") is False:
                raise UserError(self.env._("Cannot group %(model)s by '%(field)s'.", model=Model._name, field=field))
            if granularity and (meta["type"] not in ("date", "datetime") or granularity not in GRANULARITIES):
                raise UserError(self.env._("'%(field)s' cannot be grouped by '%(granularity)s'.", field=meta["string"], granularity=granularity))

    def _mixed_currencies(self, Model, info, domain, aggregates):
        """True when a money total of an ordinary model adds up several currencies (reporting models convert already)."""
        if self._is_report(Model) or "currency_id" not in info:
            return False
        if not any(info.get(a.partition(":")[0], {}).get("type") == "monetary" for a in aggregates):
            return False
        rows = Model.formatted_read_group(domain, groupby=["currency_id"], aggregates=["__count"], limit=2)
        return len(rows) > 1

    def _tool_aggregate(self, args, message):
        Model = self._model(args.get("model")).with_context(tz=self._tz())
        info = self._fields_info(Model)
        domain = self._domain(Model, args.get("domain"), info)
        groupby = [g for g in (args.get("groupby") or []) if isinstance(g, str)][:MAX_GROUPBY]
        aggregates = [a for a in (args.get("aggregates") or []) if isinstance(a, str)][:MAX_AGGREGATES] or ["__count"]
        self._check_groupby(Model, info, groupby)
        self._check_aggregates(Model, info, aggregates)
        limit = max(1, min(int(args.get("limit") or MAX_GROUPS), MAX_GROUPS))
        groups = Model.formatted_read_group(domain, groupby=groupby, aggregates=aggregates, limit=limit, order=args.get("order") or None)
        warnings = []
        if self._mixed_currencies(Model, info, domain, aggregates):
            warnings.append(self.env._("The amounts are in different currencies and were added without conversion."))

        def group_label(value, spec):
            field = info.get(spec.split(":")[0].split(".")[0], {})
            if field.get("type") == "selection" and not isinstance(value, (list, tuple)):
                return dict(field.get("selection") or []).get(value, value) or self.env._("Not set")
            if isinstance(value, (list, tuple)):
                return value[1] if len(value) > 1 else str(value[0])
            if value is False or value is None:
                return self.env._("Not set")
            return value

        def aggregate_label(spec):
            if spec == "__count":
                return self.env._("Count")
            field, _sep, function = spec.partition(":")
            label = info.get(field, {}).get("string", field)
            return label if function == "sum" else f"{label} ({function})"

        def group_title(spec):
            return info.get(spec.split(":")[0].split(".")[0], {}).get("string", spec)

        labels = [[group_label(g.get(spec), spec) for spec in groupby] for g in groups]
        values = [[g.get(spec) or 0 for spec in aggregates] for g in groups]
        money = any(info.get(a.partition(":")[0], {}).get("type") == "monetary" for a in aggregates)
        currency = self.env.company.currency_id
        spec = {"model": Model._name, "domain": domain, "groupby": groupby, "aggregates": aggregates}
        title = args.get("title") or self._label(Model._name)
        column_labels = [group_title(g) for g in groupby] + [aggregate_label(a) for a in aggregates]
        side = {
            "model": Model._name, "count": len(groups),
            "explain": {
                "label": self._label(Model._name), "filters": self._describe_domain(Model, domain),
                "grouped": [group_title(g) for g in groupby], "measures": [aggregate_label(a) for a in aggregates], "spec": spec,
            },
        }
        show = args.get("show")
        unit = {"symbol": currency.symbol, "position": currency.position} if money and not warnings else False
        if show == "kpi" and not groupby and groups:
            side["block"] = {"type": "kpi", "title": title, "spec": spec, "unit": unit,
                             "items": [{"label": aggregate_label(a), "value": values[0][i]} for i, a in enumerate(aggregates)]}
        elif show == "chart" and groupby:
            side["block"] = {"type": "chart", "title": title, "chart": args.get("chart_type") or "bar", "spec": spec, "unit": unit,
                             "labels": [" · ".join(str(part) for part in row) for row in labels],
                             "datasets": [{"label": aggregate_label(a), "data": [row[i] for row in values]} for i, a in enumerate(aggregates)]}
        elif show in ("table", "chart", "kpi"):
            side["block"] = {"type": "table", "title": title, "spec": spec, "total": len(groups), "ids": [],
                             "columns": [{"name": g, "label": group_title(g), "type": "char"} for g in groupby]
                             + [{"name": a, "label": aggregate_label(a), "type": "float"} for a in aggregates],
                             "rows": [row + value for row, value in zip(labels, values)]}
        if side.get("block") and warnings:
            side["block"]["warnings"] = warnings
        return {
            "groupby": groupby, "aggregates": aggregates, "column_labels": column_labels,
            "groups": [row + value for row, value in zip(labels, values)],
            "truncated": len(groups) >= limit, "warnings": warnings,
        }, side

    # ------------------------------------------------------------------
    # Tools that talk to the user on screen
    # ------------------------------------------------------------------
    def _tool_pick_record(self, args, message):
        Model = self._model(args.get("model"))
        query = str(args.get("query") or "")[:60]
        matches = Model.name_search(query, limit=MAX_CHOICES)
        label = self._label(Model._name)
        if not matches:
            return {"found": 0, "note": "No record matched. Ask the user for another spelling."}, {"model": Model._name}
        block = {
            "type": "choices", "title": self.env._("Which %s do you mean?", label),
            "options": [{"label": display, "text": display, "mention": {"model": Model._name, "id": res_id}} for res_id, display in matches],
        }
        return {
            "status": "waiting_for_the_user",
            "note": "The user sees the matches and chooses. Stop now; their next message names the record.",
        }, {"model": Model._name, "count": len(matches), "block": block}

    def _tool_ask_user(self, args, message):
        options = [str(o)[:60] for o in (args.get("options") or []) if isinstance(o, (str, int, float))][:4]
        if len(options) < 2:
            raise UserError(self.env._("Give two to four answer options."))
        block = {"type": "choices", "title": str(args.get("question") or "")[:200], "options": [{"label": o, "text": o} for o in options]}
        return {"status": "waiting_for_the_user", "note": "Stop now; the user's next message is the answer."}, {"block": block}

    # ------------------------------------------------------------------
    # Suggested questions (no model call: instant and free)
    # ------------------------------------------------------------------
    @api.model
    def _suggestions(self, context):
        _ = self.env._
        name = context.get("model")
        try:
            Model = self._model(name) if name else None
        except (AccessError, UserError):
            Model = None
        if Model is not None:
            label = self._label(Model._name)
            info = self._fields_info(Model)
            if context.get("res_id") and Model.browse(int(context["res_id"])).exists():
                return [_("Summarise this %s", label), _("What needs my attention on this record?")]
            out = [_("How many %s were created this month?", label)]
            stage = next((f for f in ("stage_id", "state") if f in info and info[f].get("store")), None)
            if stage:
                out.append(_("%(label)s by %(field)s", label=label, field=info[stage]["string"]))
            amount = next((f for f, i in info.items() if i["type"] == "monetary" and i.get("store") and "total" in f), None)
            if amount:
                out.append(_("Top 5 %(label)s by %(field)s", label=label, field=info[amount]["string"]))
            return out[:4]
        catalogue = [
            ("sale.order", _("How many sales orders are there this month?")),
            ("sale.order", _("Who are my top 5 customers?")),
            ("account.move", _("Which customer invoices are overdue?")),
            ("crm.lead", _("Pipeline value by stage")),
            ("purchase.order", _("Purchases by vendor this quarter")),
            ("project.task", _("Overdue tasks by project")),
            ("res.partner", _("New customers this month")),
        ]
        return [text for model, text in catalogue if model in self.env and self.env[model].has_access("read")][:4]
