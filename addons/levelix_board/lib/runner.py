"""The single place where a plan meets the database.

Everything runs with the *caller's* environment: no ``sudo``, so Odoo's access
rights and record rules decide what is counted. Each widget runs in its own
savepoint with a statement timeout, so one slow or failing widget cannot take
the others (or the whole request) down.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from psycopg2 import Error as PgError
from psycopg2 import errors as pg_errors

from odoo.exceptions import AccessError, UserError

from .errors import BoardError
from .i18n import t
from .planner import Plan

DEFAULT_TIMEOUT_MS = 8000


@dataclass
class RawResult:
    groups: list  # formatted_read_group rows
    total: Optional[dict] = None  # the same aggregates without grouping (for "Others")
    compare_groups: Optional[list] = None  # the same query over the earlier period (``compare``)


class Runner:
    def __init__(self, env, timeout_ms: int = DEFAULT_TIMEOUT_MS):
        self.env = env
        self.timeout_ms = timeout_ms

    def run(self, plan: Plan) -> RawResult:
        with self._guard():
            model = self._model(plan)
            groups = model.formatted_read_group(
                plan.domain, plan.groupby, plan.aggregates,
                having=plan.having, limit=plan.query_limit, order=plan.order,
            )
            total = None
            if plan.others or plan.totals or plan.auto_others:
                rows = model.formatted_read_group(plan.domain, [], plan.aggregates)
                total = rows[0] if rows else {}
            earlier = None
            if plan.compare is not None:
                earlier = model.formatted_read_group(
                    plan.compare.domain, plan.groupby, plan.aggregates,
                    having=plan.having, limit=plan.query_limit, order=plan.order,
                )
        return RawResult(groups, total, earlier)

    def currency_ids(self, plan: Plan) -> list:
        """Ids of the currencies that actually contribute to a monetary measure."""
        keys = [m.key for m in plan.measures if m.type == "monetary" and m.key]  # a calculated measure has no column of its own
        if not keys:
            return []
        with self._guard():
            rows = self._model(plan).formatted_read_group(plan.domain, ["currency_id"], keys)
        return [row["currency_id"][0] for row in rows
                if row.get("currency_id") and any(row.get(k) for k in keys)]

    def fetch(self, model_name: str, domain: list, fields: list, limit: int, tz: str = "UTC"):
        """``(rows, total)``: the first ``limit`` records as ``read()`` dicts, plus how many match."""
        with self._guard():
            model = self.env[model_name].with_context(tz=tz)
            total = model.search_count(domain)
            rows = model.search(domain, limit=limit).read(fields)
        return rows, total

    # -- internals ------------------------------------------------------------

    def _model(self, plan: Plan):
        if plan.model not in self.env:
            raise BoardError("UNKNOWN_MODEL", "data.source", "Model '%s' does not exist." % plan.model)
        return self.env[plan.model].with_context(tz=plan.tz)

    @contextmanager
    def _guard(self):
        cr = self.env.cr
        cr.execute("SELECT current_setting('statement_timeout')")
        previous = cr.fetchone()[0]
        try:
            with cr.savepoint():
                cr.execute("SELECT set_config('statement_timeout', %s, true)", [str(self.timeout_ms)])
                yield
            cr.execute("SELECT set_config('statement_timeout', %s, true)", [previous])
        except AccessError as error:
            raise BoardError("NO_ACCESS", "data", t("You are not allowed to see this data.")) from error
        except pg_errors.QueryCanceled as error:
            raise BoardError(
                "TIMEOUT", "data",
                t("The query took longer than %d seconds. Narrow the period or the filters.") % (self.timeout_ms // 1000),
            ) from error
        except (UserError, ValueError, KeyError, PgError) as error:
            if isinstance(error, BoardError):
                raise
            raise BoardError("QUERY_FAILED", "data", t("The data could not be read: %s") % error) from error
