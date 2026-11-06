"""A fake model catalog so the pure logic can be tested without a database."""
from ..lib.catalog import FieldInfo, ModelInfo


def field(name, ftype, label=None, **kw):
    return FieldInfo(name, label or name.replace("_", " ").title(), ftype, **kw)


def model(name, label, fields, **kw):
    return ModelInfo(name, label, {f.name: f for f in fields}, **kw)


STATES = (("draft", "Quotation"), ("sale", "Sales Order"), ("cancel", "Cancelled"))

SALE_REPORT = model("sale.report", "Sales Analysis Report", [
    field("date", "datetime", "Order Date"),
    field("state", "selection", "Status", selection=STATES),
    field("product_id", "many2one", "Product", relation="product.product"),
    field("partner_id", "many2one", "Customer", relation="res.partner"),
    field("price_subtotal", "monetary", "Untaxed Total", aggregator="sum"),
    field("price_total", "monetary", "Total", aggregator="sum"),
    field("product_uom_qty", "float", "Qty Ordered", aggregator="sum"),
    field("price_unit", "float", "Unit Price", aggregator="avg"),
    field("name", "char", "Order Reference"),
    field("currency_id", "many2one", "Currency", relation="res.currency"),
    field("create_date", "datetime", "Created on"),
    field("is_paid", "boolean", "Paid"),
    field("user_id", "many2one", "Salesperson", relation="res.users"),
    field("company_id", "many2one", "Company", relation="res.company"),
    field("categ_id", "many2one", "Product Category", relation="product.category"),
    field("computed_total", "float", "Computed", store=False),
], is_report=True)

SALE_ORDER = model("sale.order", "Sales Order", [
    field("name", "char", "Order Reference"),
    field("date_order", "datetime", "Order Date"),
    field("state", "selection", "Status", selection=STATES),
    field("partner_id", "many2one", "Customer", relation="res.partner"),
    field("amount_total", "monetary", "Total", aggregator="sum"),
    field("order_line", "one2many", "Order Lines", relation="sale.order.line"),
    field("note", "html", "Notes"),
])

PARTNER = model("res.partner", "Contact", [
    field("name", "char", "Name"),
    field("country_id", "many2one", "Country", relation="res.country"),
    field("create_date", "datetime", "Created on"),
    field("birthday", "date", "Birthday"),
])

COUNTRY = model("res.country", "Country", [field("name", "char", "Country Name")])

SECRET = ModelInfo("secret.model", "Secret", {}, accessible=False)


class FakeCatalog:
    def __init__(self, *models):
        self.models = {m.name: m for m in models}

    def model(self, name):
        return self.models.get(name)


def catalog():
    return FakeCatalog(SALE_REPORT, SALE_ORDER, PARTNER, COUNTRY, SECRET)


def sample_spec():
    """The example of the technical document (T5), with the Odoo 19 state filter."""
    return {
        "v": 1,
        "title": "Sales analysis",
        "assumptions": ["Sales = confirmed orders"],
        "widgets": [
            {
                "id": "w1", "type": "area", "title": "Daily sales",
                "grid": {"x": 0, "y": 0, "w": 16, "h": 8},
                "data": {
                    "source": "sale.report",
                    "domain": [["state", "=", "sale"]],
                    "dimensions": [{"field": "date", "granularity": "day"}],
                    "measures": [{"id": "m1", "field": "price_subtotal", "agg": "sum", "label": "Revenue"}],
                    "order": {"by": "date", "dir": "asc"},
                    "fill_gaps": True,
                },
                "view": {"smooth": True},
                "interact": {"on_click": {"action": "drill", "open_as": "side_table", "model": "sale.order",
                                          "map": {"date": "date_order"}, "columns": ["name", "partner_id"]}},
            },
            {
                "id": "w2", "type": "bar", "title": "Top 10 products",
                "data": {
                    "source": "sale.report",
                    "domain": [["state", "=", "sale"]],
                    "dimensions": [{"field": "product_id"}],
                    "measures": [{"id": "m1", "field": "product_uom_qty", "agg": "sum", "label": "Quantity"}],
                    "order": {"by": "m1", "dir": "desc"},
                    "limit": 10, "others": True,
                },
            },
        ],
    }
