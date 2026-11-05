"""Shared set-up for the integration tests of the dashboard record and drill-down."""
from odoo.tests.common import TransactionCase, new_test_user

TZ = "Asia/Tashkent"  # UTC+5


def widget(wid, wtype, source="sale.order", interact=None, **data):
    out = {"id": wid, "type": wtype, "data": dict({"source": source}, **data)}
    if interact is not None:
        out["interact"] = interact
    return out


def order_spec(partners):
    """Orders of two test customers: by day, by customer, a total, and a widget on contacts."""
    ids = [p.id for p in partners]
    base = [["state", "=", "sale"], ["partner_id", "in", ids]]
    drill = {"on_click": {"action": "drill", "model": "sale.order", "columns": ["name", "partner_id", "state", "date_order"]}}
    count = [{"id": "m1", "agg": "count"}]
    return {"v": 1, "title": "Orders", "widgets": [
        widget("w1", "area", domain=base, dimensions=[{"field": "date_order", "granularity": "day"}], measures=count, interact=drill),
        widget("w2", "bar", domain=base, dimensions=[{"field": "partner_id"}], measures=count, interact=drill),
        widget("w3", "kpi", domain=base, measures=count, interact=drill),
        widget("w4", "kpi", source="res.partner", domain=[["id", "in", ids]], measures=count),
    ]}


class BoardCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.admin = env.ref("base.user_admin")  # the test env itself is the superuser, which skips record rules
        cls.salesman = new_test_user(env, "lx_seller", groups="base.group_user,sales_team.group_sale_salesman")
        cls.warehouse = new_test_user(env, "lx_keeper", groups="base.group_user")
        cls.partner_a = env["res.partner"].create({"name": "Levelix drill customer A"})
        cls.partner_b = env["res.partner"].create({"name": "Levelix drill customer B"})
        cls.partners = cls.partner_a + cls.partner_b
        cls.product = env["product.product"].create({"name": "Levelix drill product", "list_price": 10, "type": "consu"})
        # two admin orders on 10 March (A, B) ... one seller order on 11 March (A); 10:00 UTC is 15:00 in Tashkent
        cls.order_1 = cls._order(cls.partner_a, "2024-03-10 10:00:00")
        cls.order_2 = cls._order(cls.partner_b, "2024-03-10 11:00:00")
        cls.order_3 = cls._order(cls.partner_a, "2024-03-11 10:00:00", seller=cls.salesman)
        cls._order(cls.partner_a, "2024-03-12 10:00:00", confirm=False)  # a quotation: never counted

    @classmethod
    def _order(cls, partner, when, seller=None, confirm=True):
        order = cls.env["sale.order"].create({
            "partner_id": partner.id,
            "user_id": (seller or cls.admin).id,
            "date_order": when,
            "order_line": [(0, 0, {"product_id": cls.product.id, "product_uom_qty": 1, "price_unit": 10})],
        })
        if confirm:
            order.action_confirm()
            order.date_order = when
        return order

    def as_user(self, user):
        return self.env["levelix.board"].with_user(user).with_context(tz=TZ)

    def make_board(self, spec=None, **vals):
        return self.env["levelix.board"].with_user(self.admin).with_context(tz=TZ).create(dict(
            {"name": "Orders board", "spec": spec or order_spec(self.partners)}, **vals))
