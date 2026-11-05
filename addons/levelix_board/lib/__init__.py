"""Pure logic of the board: spec, validation, planning, framing.

Nothing in this package talks to the database except ``runner`` (the one
Odoo-bound place). Everything else works on plain data and a ``Catalog``
(model/field metadata), so it is unit-testable without an Odoo environment.
"""
