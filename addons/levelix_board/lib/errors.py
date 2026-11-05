from dataclasses import dataclass

from odoo.exceptions import UserError


class BoardError(UserError):
    """One problem in a spec, located by ``path`` (e.g. ``widgets[1].data.measures[0]``).

    ``code`` is a stable machine-readable identifier (see the guardrail table in
    the technical document); ``message`` is a plain sentence. The self-repair loop
    of the AI layer relies on ``code`` and ``path``.
    """

    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code = code
        self.path = path
        self.detail = message

    def to_dict(self) -> dict:
        return {"path": self.path, "code": self.code, "message": self.detail}


class SpecInvalid(UserError):
    """Raised by ``ValidationResult.raise_if_invalid``; carries every error."""

    def __init__(self, errors):
        super().__init__("; ".join("%s: %s" % (e.path or "-", e.detail) for e in errors))
        self.errors = list(errors)


@dataclass(frozen=True)
class BoardWarning:
    """A problem that does not block execution but is shown to the user."""

    code: str
    path: str
    text: str

    def to_dict(self) -> dict:
        return {"path": self.path, "code": self.code, "text": self.text}


@dataclass
class ValidationResult:
    errors: list
    warnings: list

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_invalid(self):
        if self.errors:
            raise SpecInvalid(self.errors)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }
