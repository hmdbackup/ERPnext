"""
EPIC D — Immobilisations & amortissements (FIN-S30, RC-FIN-53).

Seeds the ERPNext Asset module on the SCE chart:
  • Asset Categories (durées par défaut modifiables en UI — pas de code) :
      Constructions                20 ans   222 / 282
      Installations & Matériel     10 ans   223 / 283
      Matériel de transport         5 ans   224 / 284
      Cheptel reproducteur          5 ans   225 / 285   (FIN-S31 : option
        « actif biologique amortissable » — paramétrée, décision client en attente)
      Autres immobilisations       10 ans   228 / 288
    Dotation → 681, CWIP → 23. Amortissement linéaire, fréquence 12 mois.
  • Location « Ferme HMD » (requise par Asset).
  • Custom Field `Asset-id_batiment` (Link → Batiment) — RC-FIN-53, exporté
    par nom dans hooks.py (pattern Stock Entry-id_lot).
  • Accounts Settings : booking automatique des dotations.

EPIC E (FIN-S40) : les comptes de charges (606/61x/62x/64x), les modèles TVA
achat et les Cost Centers existent depuis le socle — seed ici du Supplier
générique et des comptes par Mode of Payment (Cash→54, Bank→532).

Idempotent — re-run safe.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.immobilisations.setup_immobilisations
"""
import frappe

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

LOCATION = "Ferme HMD"

# (name, années, compte immo, compte amortissements)
ASSET_CATEGORIES = [
    ("Constructions", 20, "222", "282"),
    ("Installations et Matériel", 10, "223", "283"),
    ("Matériel de transport", 5, "224", "284"),
    ("Cheptel reproducteur", 5, "225", "285"),
    ("Autres immobilisations", 10, "228", "288"),
]

SUPPLIERS = ["Fournisseur Divers"]

# Mode of Payment → compte SCE
MODE_OF_PAYMENT_ACCOUNTS = {
    "Cash": "54",
    "Bank Draft": "532",
    "Wire Transfer": "532",
    "Cheque": "532",
}


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


@frappe.whitelist()
def setup_immobilisations():
    print("\n" + "=" * 60)
    print("  EPIC D/E — Immobilisations & charges (FIN-S30 / FIN-S40)")
    print("=" * 60)

    _ensure_location()
    _ensure_asset_categories()
    _ensure_asset_batiment_field()
    _ensure_asset_animal_field()
    _ensure_auto_depreciation()
    _ensure_suppliers()
    _ensure_mode_of_payment_accounts()

    frappe.db.commit()
    print("\n  Immobilisations & charges OK.\n" + "=" * 60 + "\n")


def _ensure_location():
    if frappe.db.exists("Location", LOCATION):
        print(f"  [skip]   Location {LOCATION}")
        return
    frappe.get_doc({"doctype": "Location", "location_name": LOCATION}).insert(
        ignore_permissions=True)
    print(f"  [create] Location {LOCATION}")


def _ensure_asset_categories():
    dotation = _acc("681")
    cwip = _acc("23")
    for name, annees, immo_num, amort_num in ASSET_CATEGORIES:
        if frappe.db.exists("Asset Category", name):
            print(f"  [skip]   Asset Category {name}")
            continue
        frappe.get_doc({
            "doctype": "Asset Category",
            "asset_category_name": name,
            "enable_cwip_accounting": 0,
            "finance_books": [{
                "depreciation_method": "Straight Line",
                "total_number_of_depreciations": annees,
                "frequency_of_depreciation": 12,
            }],
            "accounts": [{
                "company_name": COMPANY,
                "fixed_asset_account": _acc(immo_num),
                "accumulated_depreciation_account": _acc(amort_num),
                "depreciation_expense_account": dotation,
                "capital_work_in_progress_account": cwip,
            }],
        }).insert(ignore_permissions=True)
        print(f"  [create] Asset Category {name} ({annees} ans, {immo_num}/{amort_num})")


def _ensure_asset_batiment_field():
    """RC-FIN-53 — relie l'actif au Batiment HMD. Fixture exportée par nom
    dans hooks.py (Custom Field sur DocType core, pattern SCRUM-123)."""
    if frappe.db.exists("Custom Field", "Asset-id_batiment"):
        print("  [skip]   Custom Field Asset-id_batiment")
        return
    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Asset",
        "fieldname": "id_batiment",
        "label": "Bâtiment HMD",
        "fieldtype": "Link",
        "options": "Batiment",
        "insert_after": "location",
    }).insert(ignore_permissions=True)
    print("  [create] Custom Field Asset-id_batiment (Link → Batiment)")


def _ensure_asset_animal_field():
    """FIN-S31 (RC-FIN-55) — relie l'immobilisation à la vache qu'elle
    représente. C'est la clé d'idempotence de `cheptel_valorisation` : une
    vache, une Asset. Fixture exportée par nom dans hooks.py."""
    if frappe.db.exists("Custom Field", "Asset-id_animal"):
        print("  [skip]   Custom Field Asset-id_animal")
        return
    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Asset",
        "fieldname": "id_animal",
        "label": "Animal HMD",
        "fieldtype": "Link",
        "options": "Animal",
        "read_only": 1,
        "description": "Vache reproductrice immobilisée (FIN-S31).",
        "insert_after": "id_batiment",
    }).insert(ignore_permissions=True)
    print("  [create] Custom Field Asset-id_animal (Link → Animal)")


def _ensure_auto_depreciation():
    current = frappe.db.get_single_value(
        "Accounts Settings", "book_asset_depreciation_entry_automatically")
    if current:
        print("  [skip]   Dotations automatiques déjà actives")
        return
    frappe.db.set_single_value(
        "Accounts Settings", "book_asset_depreciation_entry_automatically", 1)
    print("  [update] Accounts Settings → dotations automatiques actives")


def _ensure_suppliers():
    for name in SUPPLIERS:
        if frappe.db.exists("Supplier", name):
            print(f"  [skip]   Supplier {name}")
            continue
        frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": name,
            "supplier_type": "Company",
        }).insert(ignore_permissions=True)
        print(f"  [create] Supplier {name}")


def _ensure_mode_of_payment_accounts():
    for mop, number in MODE_OF_PAYMENT_ACCOUNTS.items():
        if not frappe.db.exists("Mode of Payment", mop):
            continue
        account = _acc(number)
        if not account:
            continue
        existing = frappe.db.get_value(
            "Mode of Payment Account", {"parent": mop, "company": COMPANY},
            ["name", "default_account"], as_dict=True)
        if existing and existing.default_account == account:
            print(f"  [skip]   Mode of Payment {mop} → {number}")
            continue
        if existing:
            frappe.db.set_value("Mode of Payment Account", existing.name,
                                "default_account", account, update_modified=False)
            print(f"  [update] Mode of Payment {mop} → {number}")
        else:
            doc = frappe.get_doc("Mode of Payment", mop)
            doc.append("accounts", {"company": COMPANY, "default_account": account})
            doc.save(ignore_permissions=True)
            print(f"  [create] Mode of Payment {mop} → {number}")
