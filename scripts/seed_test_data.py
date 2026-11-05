# Seed data for the AI Dashboard work. Run inside the dev container:
#
#   docker exec -i levelix-aidash odoo shell -d aidash --no-http < scripts/seed_test_data.py
#
# Repeatable: everything created here is tagged with the "SEED-" order reference
# and the "seed_" xml ids. A second run first removes its own data, then
# re-creates it with the same random seed, so the numbers stay the same
# (dates move with "today", amounts do not).
#
# What it builds:
#   - company currency UZS, USD enabled with a rate
#   - second company "Filial MChJ"
#   - users: sotuvchi (own sales only), omborchi (no sales access)
#   - 12 products, 15 customers
#   - ~230 sale orders over the last 60 days: draft / sale / done / cancel,
#     some in USD, some in the second company
import random
from datetime import timedelta

from odoo import fields

SEED_REF = "SEED-"
MODULE = "seed_aidash"
USD_PER_UZS_RATE = 1.0 / 12700.0  # res.currency.rate: units of USD per 1 company currency

PRODUCTS = [
    ("Mineral water 1.5L", 4000), ("Cola 1L", 9000), ("Milk 1L", 12000),
    ("Yogurt 500g", 15000), ("Cheese 1kg", 85000), ("Butter 200g", 32000),
    ("Bread", 5000), ("Rice 1kg", 22000), ("Sugar 1kg", 14000),
    ("Tea 100 bags", 28000), ("Coffee 250g", 65000), ("Sunflower oil 1L", 24000),
]
CUSTOMERS = [
    "Anor market", "Bahor savdo", "Chorsu do'koni", "Dilshod MChJ", "Eco food",
    "Fargona trade", "Gulzor", "Hamkor", "Istiqlol market", "Jahon savdo",
    "Kamalak", "Lochin", "Mehr do'koni", "Navro'z", "Orzu market",
]


def xmlid(name):
    return "%s.%s" % (MODULE, name)


def get_or_create(env, model, name, vals):
    rec = env.ref(xmlid(name), raise_if_not_found=False)
    if rec:
        return rec
    rec = env[model].create(vals)
    env["ir.model.data"].create({
        "name": name, "module": MODULE, "model": model, "res_id": rec.id,
        "noupdate": True,
    })
    return rec


def remove_old_orders(env):
    orders = env["sale.order"].with_context(active_test=False).sudo().search(
        [("client_order_ref", "=like", SEED_REF + "%")])
    if orders:
        print("removing %d old seeded orders" % len(orders))
        orders.filtered(lambda o: o.state in ("sale", "done")).action_unlock()
        orders.action_cancel()
        orders.unlink()


def setup_currencies(env):
    uzs = env.ref("base.UZS")
    usd = env.ref("base.USD")
    uzs.active = True
    usd.active = True
    uzs.symbol = "UZS"  # Odoo ships a Bulgarian-lev symbol for UZS
    uzs.position = "after"
    company = env.ref("base.main_company")
    if company.currency_id != uzs:
        company.currency_id = uzs
    today = fields.Date.today()
    for cur, rate in ((usd, USD_PER_UZS_RATE), (uzs, 1.0)):
        existing = env["res.currency.rate"].search([
            ("currency_id", "=", cur.id), ("company_id", "=", company.id)])
        if not existing:
            env["res.currency.rate"].create({
                "currency_id": cur.id, "company_id": company.id,
                "name": today - timedelta(days=90), "rate": rate,
            })
    return uzs, usd


def setup_company2(env, uzs):
    return get_or_create(env, "res.company", "company2", {
        "name": "Filial MChJ", "currency_id": uzs.id,
    })


def setup_users(env, company1, company2):
    group_user = env.ref("base.group_user")
    group_salesman = env.ref("sales_team.group_sale_salesman")
    admin = env.ref("base.user_admin")
    admin.company_ids = [(4, company2.id)]

    def make_user(name, login, groups):
        return get_or_create(env, "res.users", login, {
            "name": name, "login": login, "password": login,
            "company_id": company1.id, "company_ids": [(6, 0, [company1.id])],
            "group_ids": [(6, 0, [g.id for g in groups])],
        })

    sotuvchi = make_user("Sotuvchi", "sotuvchi", [group_user, group_salesman])
    omborchi = make_user("Omborchi", "omborchi", [group_user])
    return admin, sotuvchi, omborchi


CATEGORIES = {"Drinks": (0, 1, 9, 10), "Dairy": (2, 3, 4, 5), "Grocery": (6, 7, 8, 11)}
COUNTRY_BY_PARTNER = {13: "base.kz", 14: "base.kg", 7: "base.tj", 11: "base.kz"}  # the rest: Uzbekistan


def setup_catalog(env):
    products = [
        get_or_create(env, "product.product", "product_%d" % i, {
            "name": name, "list_price": price, "type": "consu",
            "company_id": False,
        })
        for i, (name, price) in enumerate(PRODUCTS)
    ]
    partners = [
        get_or_create(env, "res.partner", "partner_%d" % i, {
            "name": name, "company_id": False,
        })
        for i, name in enumerate(CUSTOMERS)
    ]
    for cat_name, idx in CATEGORIES.items():
        categ = get_or_create(env, "product.category", "categ_" + cat_name.lower(), {"name": cat_name})
        for i in idx:
            products[i].categ_id = categ
    for i, partner in enumerate(partners):
        partner.country_id = env.ref(COUNTRY_BY_PARTNER.get(i, "base.uz"))
    return products, partners


def setup_pricelists(env, company1, company2, uzs, usd):
    """The order currency follows the pricelist, so each currency needs one."""
    def make(name, company, currency):
        return get_or_create(env, "product.pricelist", name, {
            "name": "Seed %s %s" % (currency.name, company.name),
            "company_id": company.id, "currency_id": currency.id,
        })
    return {
        (company1.id, uzs.id): make("pl_c1_uzs", company1, uzs),
        (company1.id, usd.id): make("pl_c1_usd", company1, usd),
        (company2.id, uzs.id): make("pl_c2_uzs", company2, uzs),
    }


def create_orders(env, rnd, products, partners, sellers, company1, company2, usd, pricelists):
    today = fields.Date.today()
    stats = {}
    for n in range(230):
        days_ago = int(rnd.triangular(0, 59, 5))  # more recent orders are more frequent
        hour = rnd.choice([9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
        when = fields.Datetime.to_datetime(today - timedelta(days=days_ago)).replace(
            hour=hour, minute=rnd.randint(0, 59))
        company = company2 if rnd.random() < 0.12 else company1
        seller = sellers[0] if company == company2 else rnd.choice(sellers)
        in_usd = company == company1 and rnd.random() < 0.15
        currency = usd if in_usd else company.currency_id
        lines = []
        for _ in range(rnd.randint(1, 4)):
            product = rnd.choice(products)
            qty = rnd.choice([1, 2, 3, 5, 10, 20])
            price = product.list_price / 12700.0 if in_usd else product.list_price
            lines.append((0, 0, {
                "product_id": product.id, "product_uom_qty": qty,
                "price_unit": round(price, 2),
            }))
        order = env["sale.order"].with_company(company).with_user(1).create({
            "partner_id": rnd.choice(partners).id,
            "company_id": company.id,
            "user_id": seller.id,
            "date_order": when,
            "client_order_ref": "%s%03d" % (SEED_REF, n),
            "pricelist_id": pricelists[(company.id, currency.id)].id,
            "currency_id": currency.id,
            "order_line": lines,
        })
        roll = rnd.random()
        if roll < 0.12:
            state = "draft"
        elif roll < 0.20:
            state = "cancel"
            order.action_cancel()
        else:
            order.action_confirm()
            order.date_order = when  # action_confirm stamps "now"; put the date back
            state = "sale"
            if roll > 0.80:
                order.action_lock()
                state = "done"
        stats[state] = stats.get(state, 0) + 1
    return stats


remove_old_orders(env)
rnd = random.Random(42)
uzs, usd = setup_currencies(env)
company1 = env.ref("base.main_company")
company2 = setup_company2(env, uzs)
admin, sotuvchi, omborchi = setup_users(env, company1, company2)
products, partners = setup_catalog(env)
pricelists = setup_pricelists(env, company1, company2, uzs, usd)
stats = create_orders(env, rnd, products, partners, [admin, sotuvchi], company1, company2, usd, pricelists)
env.cr.commit()
print("SEED DONE:", stats)
