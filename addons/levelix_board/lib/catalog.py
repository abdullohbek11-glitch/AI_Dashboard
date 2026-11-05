"""Model/field metadata the validator and planner need, independent of Odoo.

The Odoo-bound implementation lives in ``models/env_catalog.py`` and returns
only what the *current user* may read, so an unreadable field is simply
"unknown" to everything downstream.
"""
from dataclasses import dataclass, field
from typing import Optional, Protocol

NUMERIC_TYPES = ("integer", "float", "monetary")
TEMPORAL_TYPES = ("date", "datetime")


@dataclass(frozen=True)
class FieldInfo:
    name: str
    label: str
    type: str
    store: bool = True
    groupable: bool = True
    aggregator: Optional[str] = None  # the field's default Odoo aggregator ("sum", "avg", ...)
    selection: tuple = ()  # ((value, label), ...)
    relation: Optional[str] = None

    @property
    def selection_labels(self) -> dict:
        return dict(self.selection)

    @property
    def is_temporal(self) -> bool:
        return self.type in TEMPORAL_TYPES

    @property
    def is_numeric(self) -> bool:
        return self.type in NUMERIC_TYPES


@dataclass
class ModelInfo:
    name: str
    label: str
    fields: dict = field(default_factory=dict)  # name -> FieldInfo
    is_report: bool = False  # SQL-view model (_auto = False)
    accessible: bool = True  # may the user read the model at all

    def field(self, name: str) -> Optional[FieldInfo]:
        return self.fields.get(name)


class Catalog(Protocol):
    def model(self, name: str) -> Optional[ModelInfo]:
        """``None`` when the model does not exist."""
