"""Odoo-bound ``Catalog``: describes models and fields *as the current user may see them*."""
from odoo.exceptions import AccessError

from ..lib.catalog import FieldInfo, ModelInfo

_ATTRIBUTES = ["type", "string", "store", "groupable", "aggregator", "selection", "relation"]


class EnvCatalog:
    def __init__(self, env):
        self.env = env
        self._cache = {}

    def model(self, name):
        if name in self._cache:
            return self._cache[name]
        info = self._load(name)
        self._cache[name] = info
        return info

    def _load(self, name):
        if name not in self.env:
            return None
        model = self.env[name]
        label = model._description or name
        is_report = not model._auto
        if not model.has_access("read"):
            return ModelInfo(name, label, {}, is_report, accessible=False)
        try:
            described = model.fields_get(attributes=_ATTRIBUTES)  # already limited by field groups
        except AccessError:
            return ModelInfo(name, label, {}, is_report, accessible=False)
        fields = {
            fname: FieldInfo(
                name=fname,
                label=meta.get("string") or fname,
                type=meta["type"],
                store=bool(meta.get("store", True)),
                groupable=bool(meta.get("groupable", True)),
                aggregator=meta.get("aggregator"),
                selection=tuple(tuple(pair) for pair in meta.get("selection") or ()) if isinstance(meta.get("selection"), list) else (),
                relation=meta.get("relation"),
            )
            for fname, meta in described.items()
        }
        return ModelInfo(name, label, fields, is_report, accessible=True)
