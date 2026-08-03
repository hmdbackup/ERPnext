"""
EPIC A — Socle comptable tunisien (FIN-S01 RG-FIN-01, FIN-S02 RG-FIN-40).

Aligns the blank ERPNext site on the HMD Agro finance foundation:
  1. Company "hmd-agro" (renamed from the setup-wizard "HMD Agro"), country
     Tunisia, currency TND — matches stock_utils.DEFAULT_COMPANY.
  2. Chart of Accounts SCE (plan_comptable_sce.CHART_SCE) replacing the
     default Canadian chart (only allowed while the ledger is empty).
  3. Fiscal Year, TVA templates (19/13/7/0%), default accounts on Company.
  4. Cost Centers ateliers + Accounting Dimensions Lot / Batiment.

Idempotent: every step checks before writing. Re-run safe.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.socle_comptable.setup_socle_comptable
"""
import frappe
from frappe.utils import nowdate, getdate

from hmd_agro.hmd_agro.setup.finance.plan_comptable_sce import CHART_SCE

COMPANY = "hmd-agro"
OLD_COMPANY = "HMD Agro"
CURRENCY = "TND"
COUNTRY = "Tunisia"

# FIN-S02 — ateliers analytiques (RG-FIN-40)
COST_CENTERS = [
    "Lait",
    "Élevage - Génisses",
    "Cultures - Fourrage",
    "Traction",
    "Frais Généraux",
]

# Accounting Dimensions on custom doctypes (Atelier = the Cost Center axis itself)
DIMENSIONS = ["Lot", "Batiment"]

# Comptes ajoutés au plan APRÈS le premier import du chart. `create_charts` ne
# rejoue pas sur un plan existant : ces comptes sont créés un par un sous la
# racine de leur root_type, idempotents.
# (account_number, nom, root_type, account_type)
EXTRA_ACCOUNTS = [
    # FIN-S42 — contrepartie des charges patronales de la paie
    ("453", "Organismes sociaux", "Liability", ""),
]

# (template title, rate %, tax account number)  — data seed, editable in UI after
SALES_TVA = [
    ("TVA collectée 19%", 19.0),
    ("TVA collectée 7%", 7.0),
    ("Exonéré de TVA (0%)", 0.0),
]
PURCHASE_TVA = [
    ("TVA déductible 19%", 19.0),
    ("TVA déductible 13%", 13.0),
    ("TVA déductible 7%", 7.0),
]

# Company default-account fields → SCE account_number
COMPANY_ACCOUNT_DEFAULTS = {
    "default_bank_account": "532",
    "default_cash_account": "54",
    "default_receivable_account": "411",
    "default_payable_account": "401",
    "default_expense_account": "605",
    "default_income_account": "701",
    "default_inventory_account": "32",
    "stock_adjustment_account": "603",
    "stock_received_but_not_billed": "408",
    "expenses_included_in_valuation": "608",
    "default_provisional_account": "4088",
    "round_off_account": "658",
    "exchange_gain_loss_account": "665",
    "unrealized_exchange_gain_loss_account": "665",
    "depreciation_expense_account": "681",
    "accumulated_depreciation_account": "288",
    "disposal_account": "736",
    "capital_work_in_progress_account": "23",
}
DEFAULT_COST_CENTER = "Frais Généraux"

# Exercices antérieurs ouverts en plus de l'exercice courant : la reprise
# d'historique (bascule, restauration de production) poste des mouvements
# datés d'avant l'année en cours.
EXERCICES_ANTERIEURS = 3


def _acc(number):
    """Account name for an SCE account_number on COMPANY (None if missing)."""
    return frappe.db.get_value(
        "Account", {"company": COMPANY, "account_number": number}
    )


@frappe.whitelist()
def setup_socle_comptable():
    print("\n" + "=" * 60)
    print("  EPIC A — Socle comptable tunisien (FIN-S01 / FIN-S02)")
    print("=" * 60)

    _ensure_currency()
    _ensure_company()
    _replace_chart()
    _ensure_extra_accounts()
    _ensure_fiscal_year()
    _ensure_cost_centers()
    _set_company_defaults()
    _ensure_tax_templates()
    _ensure_dimensions()
    _set_global_defaults()

    frappe.db.commit()
    print("\n  Socle comptable OK.\n" + "=" * 60 + "\n")


def _ensure_currency():
    if not frappe.db.get_value("Currency", CURRENCY, "enabled"):
        frappe.db.set_value("Currency", CURRENCY, "enabled", 1, update_modified=False)
        print(f"  [create] Currency {CURRENCY} activée")
    else:
        print(f"  [skip]   Currency {CURRENCY} déjà active")


def _ensure_company():
    if not frappe.db.exists("Company", COMPANY):
        if frappe.db.exists("Company", OLD_COMPANY):
            if frappe.db.count("GL Entry", {"company": OLD_COMPANY}):
                frappe.throw(
                    f"ERR-FIN-01 : des écritures GL existent sur '{OLD_COMPANY}' — "
                    "renommage/bascule interdits (RG-FIN-01)."
                )
            frappe.rename_doc("Company", OLD_COMPANY, COMPANY, force=True)
            print(f"  [rename] Company '{OLD_COMPANY}' → '{COMPANY}'")
        else:
            frappe.get_doc({
                "doctype": "Company",
                "company_name": COMPANY,
                "abbr": "HMD",
                "country": COUNTRY,
                "default_currency": CURRENCY,
            }).insert(ignore_permissions=True)
            print(f"  [create] Company '{COMPANY}'")
    else:
        print(f"  [skip]   Company '{COMPANY}' existe")

    company = frappe.get_doc("Company", COMPANY)
    changed = False
    if company.country != COUNTRY:
        company.country = COUNTRY
        changed = True
    if company.default_currency != CURRENCY:
        if frappe.db.count("GL Entry", {"company": COMPANY}):
            frappe.throw(
                "ERR-FIN-02 : impossible de changer la devise, écritures GL existantes."
            )
        # The wizard chart (CAD accounts) blocks the currency switch: default
        # account fields must match company currency, and any account created
        # later inherits it. Drop the old chart BEFORE switching, so the SCE
        # chart is born in TND.
        _drop_existing_chart()
        company.reload()
        company.country = COUNTRY
        company.default_currency = CURRENCY
        changed = True
    if changed:
        company.save(ignore_permissions=True)
        print(f"  [update] Company → country={COUNTRY}, currency={CURRENCY}")


def _drop_existing_chart():
    """Unhook + delete the current chart of the company (empty ledger only)."""
    from erpnext.accounts.doctype.chart_of_accounts_importer.chart_of_accounts_importer import (
        unset_existing_data,
    )

    for wh in frappe.get_all("Warehouse", filters={"company": COMPANY}, pluck="name"):
        frappe.db.set_value("Warehouse", wh, "account", "", update_modified=False)
    old_count = frappe.db.count("Account", {"company": COMPANY})
    if old_count:
        unset_existing_data(COMPANY)
        print(f"  [delete] Ancien plan comptable : {old_count} comptes supprimés")


def _replace_chart():
    """Swap the wizard chart for the SCE chart. Only runs while the ledger
    is empty; presence of account 101 is the 'already done' marker."""
    if _acc("101"):
        print("  [skip]   Plan comptable SCE déjà en place (compte 101 présent)")
        return
    if frappe.db.count("GL Entry", {"company": COMPANY}):
        frappe.throw("ERR-FIN-03 : écritures GL existantes — remplacement du plan interdit.")

    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import (
        create_charts,
    )

    _drop_existing_chart()
    create_charts(COMPANY, custom_chart=CHART_SCE)
    new_count = frappe.db.count("Account", {"company": COMPANY})
    print(f"  [create] Plan SCE : {new_count} comptes créés")


def _root_account(root_type):
    """Compte racine (groupe) du root_type — premier groupe dans l'ordre de
    l'arbre. (`parent_account` vaut NULL sur les racines : un filtre
    `["in", ["", None]]` ne les trouve pas, SQL `IN` ignorant NULL.)"""
    return frappe.db.get_value(
        "Account",
        {"company": COMPANY, "root_type": root_type, "is_group": 1},
        "name",
        order_by="lft asc",
    )


def _ensure_extra_accounts():
    """Crée les comptes ajoutés au plan après le premier import (EXTRA_ACCOUNTS).
    Un site déjà déployé ne rejoue pas `create_charts` — sans ça, les nouveaux
    comptes n'existeraient que sur les instances neuves."""
    for number, nom, root_type, account_type in EXTRA_ACCOUNTS:
        if _acc(number):
            print(f"  [skip]   Compte {number} {nom}")
            continue
        parent = _root_account(root_type)
        if not parent:
            print(f"  [warn]   Racine {root_type} introuvable — compte {number} ignoré")
            continue
        doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": nom,
            "account_number": number,
            "parent_account": parent,
            "company": COMPANY,
            "root_type": root_type,
            "is_group": 0,
        })
        if account_type:
            doc.account_type = account_type
        doc.insert(ignore_permissions=True)
        print(f"  [create] Compte {number} {nom} (sous {parent})")


def _ensure_fiscal_year():
    """Exercice courant + les EXERCICES_ANTERIEURS précédents.

    Les années passées ne sont pas un luxe : depuis FIN-S11 toute sortie de
    stock poste au Grand Livre, donc reprendre un historique (restauration de
    production, import de mouvements antérieurs) échoue avec un
    « Date … is not in any active Fiscal Year » si l'exercice manque."""
    annee_courante = getdate(nowdate()).year
    for annee in range(annee_courante - EXERCICES_ANTERIEURS, annee_courante + 1):
        couvert = frappe.db.exists("Fiscal Year", {
            "year_start_date": ("<=", f"{annee}-12-31"),
            "year_end_date": (">=", f"{annee}-01-01"),
        })
        if couvert:
            print(f"  [skip]   Fiscal Year {annee} couvert ({couvert})")
            continue
        frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": str(annee),
            "year_start_date": f"{annee}-01-01",
            "year_end_date": f"{annee}-12-31",
        }).insert(ignore_permissions=True)
        print(f"  [create] Fiscal Year {annee}")


def _root_cost_center():
    return frappe.db.get_value(
        "Cost Center",
        {"company": COMPANY, "is_group": 1},
        "name",
        order_by="lft asc",
    )


def _ensure_cost_centers():
    parent = _root_cost_center()
    if not parent:
        frappe.throw("ERR-FIN-04 : aucun Cost Center racine pour la company.")
    for cc in COST_CENTERS:
        abbr = frappe.db.get_value("Company", COMPANY, "abbr")
        full = f"{cc} - {abbr}"
        if frappe.db.exists("Cost Center", full):
            print(f"  [skip]   Cost Center {full}")
            continue
        frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": cc,
            "parent_cost_center": parent,
            "company": COMPANY,
            "is_group": 0,
        }).insert(ignore_permissions=True)
        print(f"  [create] Cost Center {full}")


def _set_company_defaults():
    meta = frappe.get_meta("Company")
    values = {}
    for field, number in COMPANY_ACCOUNT_DEFAULTS.items():
        if not meta.has_field(field):
            continue
        account = _acc(number)
        if account and frappe.db.get_value("Company", COMPANY, field) != account:
            values[field] = account
    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    cc = f"{DEFAULT_COST_CENTER} - {abbr}"
    if frappe.db.exists("Cost Center", cc):
        for field in ("cost_center", "round_off_cost_center", "depreciation_cost_center"):
            if meta.has_field(field) and frappe.db.get_value("Company", COMPANY, field) != cc:
                values[field] = cc
    if values:
        frappe.db.set_value("Company", COMPANY, values)
        frappe.clear_cache()
        print(f"  [update] Company : {len(values)} comptes/CC par défaut posés")
    else:
        print("  [skip]   Comptes par défaut Company déjà posés")


def _ensure_tax_templates():
    tva_collectee, tva_deductible = _acc("4367"), _acc("4366")
    for title, rate in SALES_TVA:
        _make_tax_template(
            "Sales Taxes and Charges Template", title, rate, tva_collectee
        )
    for title, rate in PURCHASE_TVA:
        _make_tax_template(
            "Purchase Taxes and Charges Template", title, rate, tva_deductible
        )


def _make_tax_template(doctype, title, rate, account):
    if frappe.db.exists(doctype, {"title": title, "company": COMPANY}):
        print(f"  [skip]   {title}")
        return
    doc = frappe.get_doc({
        "doctype": doctype,
        "title": title,
        "company": COMPANY,
        "taxes": [{
            "charge_type": "On Net Total",
            "account_head": account,
            "description": title,
            "rate": rate,
        }],
    })
    if doctype == "Purchase Taxes and Charges Template":
        doc.taxes[0].category = "Total"
        doc.taxes[0].add_deduct_tax = "Add"
    doc.insert(ignore_permissions=True)
    print(f"  [create] {title} ({rate}%)")


def _ensure_dimensions():
    for dt in DIMENSIONS:
        if frappe.db.exists("Accounting Dimension", {"document_type": dt}):
            print(f"  [skip]   Accounting Dimension {dt}")
            continue
        frappe.get_doc({
            "doctype": "Accounting Dimension",
            "document_type": dt,
        }).insert(ignore_permissions=True)
        print(f"  [create] Accounting Dimension {dt}")


def _set_global_defaults():
    gd = frappe.get_doc("Global Defaults")
    changed = False
    if gd.default_currency != CURRENCY:
        gd.default_currency = CURRENCY
        changed = True
    if gd.default_company != COMPANY:
        gd.default_company = COMPANY
        changed = True
    if changed:
        gd.save(ignore_permissions=True)
        print(f"  [update] Global Defaults → {COMPANY} / {CURRENCY}")
    else:
        print("  [skip]   Global Defaults déjà alignés")
