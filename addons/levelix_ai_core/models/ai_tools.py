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

from ..lib import dates, parts, privacy

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
HIDDEN_TYPES = ("binary", "json", "properties", "properties_definition", "html", "one2many")
# Bookkeeping fields every record has; listing them only costs the model's attention (and the user's tokens).
NOISE_FIELDS = ("id", "create_uid", "write_uid", "write_date", "display_name", "pending_email_template_id")
NOISE_PREFIXES = ("message_", "activity_", "website_message_", "access_", "my_activity")

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
                   "values and how a number may be aggregated. Call it once, only for the model you will query, and only if you do not already know its fields.",
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
                   "groupby items are field names, with ':day|week|month|quarter|year' for dates, or a date part to group by weekday or hour "
                   "(':day_of_week' with Monday first, ':hour_number', ':month_number', ':quarter_number'). "
                   "aggregates are '__count' or 'field:sum|avg|min|max|count_distinct' (only fields marked summable can be summed). "
                   "show=chart draws the result, show=kpi shows one big number (no groupby), show=table lists the groups.",
    "parameters": {
        "type": "object",
        "properties": {
            "model": _STRING,
            "domain": {"type": "string", "description": "JSON list of triples. Use [] for all. Dates as YYYY-MM-DD."},
            "groupby": {"type": "array", "items": _STRING},
            "aggregates": {"type": "array", "items": _STRING},
            "labels": {"type": "array", "items": _STRING, "description": "What each measure is called for the user, in their language, "
                       "same order as aggregates, 1-3 words, plain text without quotes (Orders, Revenue). Always give them."},
            "order": {"type": "string", "description": "A groupby or aggregate as written above, then asc or desc: 'amount_total:sum desc', 'date:day asc'."},
            "limit": {"type": "integer"},
            "show": {"type": "string", "enum": ["none", "chart", "kpi", "table"]},
            "chart_type": {"type": "string", "enum": ["bar", "line", "pie"], "description": "Only these three. A heatmap, funnel, treemap, gauge, waterfall, scatter, combo, or a comparison with an earlier period is not drawn here: build a dashboard instead."},
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
    def _scope(self):
        """Which companies the numbers cover. Said only when the user belongs to several, so a total is never taken for "everything"."""
        if len(self.env.user.company_ids) < 2:
            return False
        return ", ".join(self.env.companies.mapped("name"))

    @api.model
    def _scope_note(self, scope):
        return self.env._("Company: %s", scope) if scope else False

    @api.model
    def _calendar_names(self):
        """Weekday names (Monday first) and month names in the reader's language; ``(None, None)`` falls back to English."""
        try:
            from babel import dates
            from odoo.tools.misc import babel_locale_parse
            locale = babel_locale_parse(self.env.lang or "en_US")
            days = dates.get_day_names("abbreviated", locale=locale)
            months = dates.get_month_names("abbreviated", locale=locale)
            return [days[i] for i in range(7)], [months[i] for i in range(1, 13)]
        except Exception:  # noqa: BLE001 - names are a nicety; English is fine
            return None, None

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
        if message and message.sudo().tool_call_ids.filtered(lambda call: call.name == "describe_model" and call.res_model == Model._name):
            return {"model": Model._name, "note": "Already described earlier in this answer; use that list."}, {"model": Model._name}
        fields = []
        for name, info in self._fields_info(Model).items():
            if not info.get("store") or info["type"] in HIDDEN_TYPES or name.startswith("__"):
                continue
            if name in NOISE_FIELDS or name.startswith(NOISE_PREFIXES) or name.endswith("_token"):
                continue
            entry = {"name": name, "type": info["type"], "label": info["string"]}
            if info.get("relation"):
                entry["relation"] = info["relation"]
            if info.get("selection"):
                entry["values"] = [list(pair) for pair in info["selection"]][:20]
            if info["type"] in ("integer", "float", "monetary") and info.get("aggregator") == "sum":
                entry["summable"] = True
            fields.append((not info.get("required"), name, entry))
        fields.sort(key=lambda f: f[:2])
        return {
            "model": Model._name, "label": self._label(Model._name), "report": self._is_report(Model),
            "fields": [f[2] for f in fields[:MAX_FIELDS]],
            "note": "Only stored fields are listed. A number without 'summable' (a price, a rate) can be averaged, not added up.",
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
        scope = self._scope()
        side = {
            "model": Model._name, "count": total,
            "explain": {"label": self._label(Model._name), "filters": self._describe_domain(Model, domain), "count": total, "spec": spec,
                        "companies": scope},
        }
        if args.get("show") == "table":
            side["block"] = {
                "type": "table", "title": args.get("title") or self._label(Model._name),
                "columns": columns, "rows": table, "ids": [row["id"] for row in rows], "total": total, "spec": spec,
                "scope": self._scope_note(scope),
            }
        result = {
            "total": total, "returned": len(rows), "columns": names,
            "rows": [[row["id"]] + line for row, line in zip(rows, table)],
            "note": "first value of each row is the record id",
        }
        if scope:
            result["companies"] = scope
        return result, side

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
            if granularity and (meta["type"] not in ("date", "datetime") or granularity not in GRANULARITIES + parts.DATE_PARTS):
                raise UserError(self.env._("'%(field)s' cannot be grouped by '%(granularity)s'.", field=meta["string"], granularity=granularity))
            if granularity in parts.HOUR_PARTS and meta["type"] != "datetime":
                raise UserError(self.env._("'%s' is a date without a time of day, so it cannot be grouped by hour or minute.", meta["string"]))

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
        try:
            order = parts.normalise_order(args.get("order"), groupby, aggregates)
        except parts.OrderError as error:
            raise UserError(str(error)) from error
        groups = Model.formatted_read_group(domain, groupby=groupby, aggregates=aggregates, limit=limit, order=order)
        if groupby and groupby[0].endswith(":day_of_week") and (not order or order.split()[0] == groupby[0]):
            # Monday first, as people read a week (Odoo counts Sunday as 0), also when the model asked for the weekday order itself
            groups.sort(key=lambda g: parts.monday_first(g.get(groupby[0]) or 0), reverse=bool(order) and order.split()[1] == "desc")
        warnings = []
        scope = self._scope()
        if self._mixed_currencies(Model, info, domain, aggregates):
            warnings.append(self.env._("The amounts are in different currencies and were added without conversion."))

        day_names, month_names = self._calendar_names()

        def group_label(value, spec):
            if spec.partition(":")[2] in parts.DATE_PARTS:
                return parts.label(value, spec.partition(":")[2], day_names, month_names)
            field = info.get(spec.split(":")[0].split(".")[0], {})
            if field.get("type") == "selection" and not isinstance(value, (list, tuple)):
                return dict(field.get("selection") or []).get(value, value) or self.env._("Not set")
            if isinstance(value, (list, tuple)):
                return value[1] if len(value) > 1 else str(value[0])
            if value is False or value is None:
                return self.env._("Not set")
            return value

        given = [str(x).strip(" \"'`")[:40] for x in (args.get("labels") or []) if isinstance(x, (str, int, float))]
        given = [x or "" for x in given]

        def measure_label(index, spec):
            """The model's own plain name when it gave one; else the field's label with a word for the function."""
            if index < len(given) and given[index]:
                return given[index]
            if spec == "__count":
                return self.env._("Count")
            field, _sep, function = spec.partition(":")
            label = info.get(field, {}).get("string", field)
            if function == "avg":
                return self.env._("Average %s", label)
            if function == "min":
                return self.env._("Smallest %s", label)
            if function == "max":
                return self.env._("Largest %s", label)
            if function == "count_distinct":
                return self.env._("Unique %s", label)
            return label

        measures = [measure_label(i, a) for i, a in enumerate(aggregates)]

        def group_title(spec):
            return info.get(spec.split(":")[0].split(".")[0], {}).get("string", spec)

        labels = [[group_label(g.get(spec), spec) for spec in groupby] for g in groups]
        values = [[g.get(spec) or 0 for spec in aggregates] for g in groups]
        money = any(info.get(a.partition(":")[0], {}).get("type") == "monetary" for a in aggregates)
        currency = self.env.company.currency_id
        spec = {"model": Model._name, "domain": domain, "groupby": groupby, "aggregates": aggregates}
        title = args.get("title") or self._label(Model._name)
        column_labels = [group_title(g) for g in groupby] + measures
        side = {
            "model": Model._name, "count": len(groups),
            "explain": {
                "label": self._label(Model._name), "filters": self._describe_domain(Model, domain),
                "grouped": [group_title(g) for g in groupby], "measures": measures, "spec": spec, "companies": scope,
            },
        }
        show = args.get("show")
        unit = {"symbol": currency.symbol, "position": currency.position} if money and not warnings else False
        if show == "kpi" and not groupby and groups:
            side["block"] = {"type": "kpi", "title": title, "spec": spec, "unit": unit,
                             "items": [{"label": measures[i], "value": values[0][i]} for i in range(len(aggregates))]}
        elif show == "chart" and groupby:
            side["block"] = {"type": "chart", "title": title, "chart": args.get("chart_type") or "bar", "spec": spec, "unit": unit,
                             "labels": [" · ".join(str(part) for part in row) for row in labels],
                             "datasets": [{"label": measures[i], "data": [row[i] for row in values]} for i in range(len(aggregates))]}
        elif show in ("table", "chart", "kpi"):
            side["block"] = {"type": "table", "title": title, "spec": spec, "total": len(groups), "ids": [],
                             "columns": [{"name": g, "label": group_title(g), "type": "char"} for g in groupby]
                             + [{"name": a, "label": measures[i], "type": "float"} for i, a in enumerate(aggregates)],
                             "rows": [row + value for row, value in zip(labels, values)]}
        if side.get("block"):
            side["block"]["scope"] = self._scope_note(scope)
            # what was asked, as it was asked (relative dates stay relative): another module may keep the result as a dashboard
            side["block"]["query"] = {
                "model": Model._name, "domain": self._json(args.get("domain"), (list, tuple), []), "groupby": groupby,
                "aggregates": aggregates, "labels": measures, "order": order,
                "limit": args["limit"] if isinstance(args.get("limit"), int) and not isinstance(args.get("limit"), bool) else None,
            }
            if warnings:
                side["block"]["warnings"] = warnings
        result = {
            "groupby": groupby, "aggregates": aggregates, "column_labels": column_labels,
            "groups": [row + value for row, value in zip(labels, values)],
            "truncated": len(groups) >= limit, "warnings": warnings,
        }
        if scope:
            result["companies"] = scope
        return result, side

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
            "type": "choices", "kind": "pick", "title": self.env._("Which %s do you mean?", label),
            "options": [{"label": display, "text": display, "mention": {"model": Model._name, "id": res_id}} for res_id, display in matches],
        }
        return {
            "status": "waiting_for_the_user",
            "note": "The user sees the matches and chooses. Stop now; their next message names the record.",
        }, {"model": Model._name, "count": len(matches), "block": block}

    def _tool_ask_user(self, args, message):
        if self._answered_a_question(message):
            raise UserError(self.env._(
                "The user has just answered your question. Do not ask another one: use their answer, choose a sensible default for anything "
                "else, and say in one sentence what you assumed."))
        options = [str(o)[:60] for o in (args.get("options") or []) if isinstance(o, (str, int, float))][:4]
        if len(options) < 2:
            raise UserError(self.env._("Give two to four answer options."))
        block = {"type": "choices", "kind": "question", "title": str(args.get("question") or "")[:200],
                 "options": [{"label": o, "text": o} for o in options]}
        return {"status": "waiting_for_the_user", "note": "Stop now; the user's next message is the answer."}, {"block": block}

    @api.model
    def _answered_a_question(self, message):
        """Is the question being answered now itself the pressed answer to one the assistant asked just before?

        One clarifying question per request is enough: a second one right after the user chose is a loop, not help."""
        if not message:
            return False
        earlier = message.conversation_id.message_ids.filtered(lambda m: m.id < message.id).sorted("id")
        if len(earlier) < 2 or earlier[-1].role != "user" or earlier[-2].role != "assistant":
            return False
        asked = [o.get("text") for b in earlier[-2].blocks or [] if b.get("type") == "choices" and b.get("kind") == "question" for o in b.get("options", [])]
        return earlier[-1].text in asked

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
