"""
EPIC C — Recettes : référentiel de vente (FIN-S20 RG-FIN-10, FIN-S23).

Seeds the selling masters used by the revenue flows:
  • Item Groups « Produits » (Lait / Fumier / Animaux) — sales-only items,
    non-stock : le volume lait vit dans Traite/BLJ, le cheptel dans Animal.
  • Items LAIT-CRU, FUMIER, ANIMAL-VENTE avec comptes de produits SCE
    (701 / 708 / 702) et cost centers ateliers par défaut.
  • Customers « Centrale Laitière » (lait) et « Client Divers ».
  • Item Price LAIT-CRU sur « Standard Selling » (passée en TND) au prix
    de référence config `prix_reference_lait` — aucun prix en dur.

Idempotent — re-run safe.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.recettes.setup_recettes
"""
import frappe

from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

PRICE_LIST = "Standard Selling"

ITEM_GROUPS = [
    ("Produits", "All Item Groups", 1),
    ("Produits Laitiers", "Produits", 0),
    ("Produits Divers", "Produits", 0),
    ("Animaux", "Produits", 0),
]

# (item_code, item_name, group, uom, income account_number, cost center)
ITEMS = [
    ("LAIT-CRU", "Lait cru", "Produits Laitiers", "Litre", "701", "Lait"),
    ("FUMIER", "Fumier", "Produits Divers", "Tonne", "708", "Cultures - Fourrage"),
    ("ANIMAL-VENTE", "Vente d'animal", "Animaux", "Unit", "702", "Élevage - Génisses"),
]

CUSTOMERS = ["Centrale Laitière", "Client Divers"]


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


@frappe.whitelist()
def setup_recettes():
    print("\n" + "=" * 60)
    print("  EPIC C — Référentiel recettes (FIN-S20 / FIN-S23)")
    print("=" * 60)

    _ensure_price_list()
    _ensure_item_groups()
    _ensure_items()
    _ensure_customers()
    _ensure_lait_price()

    frappe.db.commit()
    print("\n  Référentiel recettes OK.\n" + "=" * 60 + "\n")


def _ensure_price_list():
    """The wizard created Standard Selling in the old currency — align on TND."""
    currency = frappe.db.get_value("Price List", PRICE_LIST, "currency")
    company_currency = frappe.db.get_value("Company", COMPANY, "default_currency")
    if currency != company_currency:
        frappe.db.set_value("Price List", PRICE_LIST, "currency", company_currency,
                            update_modified=False)
        print(f"  [update] Price List '{PRICE_LIST}' → {company_currency}")
    else:
        print(f"  [skip]   Price List '{PRICE_LIST}' déjà en {company_currency}")


def _ensure_item_groups():
    for name, parent, is_group in ITEM_GROUPS:
        if frappe.db.exists("Item Group", name):
            print(f"  [skip]   Item Group {name}")
            continue
        frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": name,
            "parent_item_group": parent,
            "is_group": is_group,
        }).insert(ignore_permissions=True)
        print(f"  [create] Item Group {name}")


def _ensure_items():
    abbr = _abbr()
    for code, name, group, uom, income_number, cc in ITEMS:
        if not frappe.db.exists("UOM", uom):
            frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(
                ignore_permissions=True)
            print(f"  [create] UOM {uom}")
        if frappe.db.exists("Item", code):
            print(f"  [skip]   Item {code}")
            continue
        frappe.get_doc({
            "doctype": "Item",
            "item_code": code,
            "item_name": name,
            "item_group": group,
            "stock_uom": uom,
            "is_stock_item": 0,
            "is_sales_item": 1,
            "is_purchase_item": 0,
            "item_defaults": [{
                "company": COMPANY,
                "income_account": _acc(income_number),
                "selling_cost_center": f"{cc} - {abbr}",
            }],
        }).insert(ignore_permissions=True)
        print(f"  [create] Item {code} (701→{income_number}, atelier {cc})")


def _ensure_customers():
    for name in CUSTOMERS:
        if frappe.db.exists("Customer", name):
            print(f"  [skip]   Customer {name}")
            continue
        frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Company",
        }).insert(ignore_permissions=True)
        print(f"  [create] Customer {name}")


def _ensure_lait_price():
    """Item Price LAIT-CRU au prix de référence config (RG-FIN-10 : le prix
    vit dans Item Price / HMD Configuration, jamais dans le code)."""
    if frappe.db.exists("Item Price",
                        {"item_code": "LAIT-CRU", "price_list": PRICE_LIST}):
        print("  [skip]   Item Price LAIT-CRU existe")
        return
    prix = float(get_config("prix_reference_lait", default=1.6))
    frappe.get_doc({
        "doctype": "Item Price",
        "item_code": "LAIT-CRU",
        "price_list": PRICE_LIST,
        "price_list_rate": prix,
    }).insert(ignore_permissions=True)
    print(f"  [create] Item Price LAIT-CRU @ {prix} TND/L (config prix_reference_lait)")
