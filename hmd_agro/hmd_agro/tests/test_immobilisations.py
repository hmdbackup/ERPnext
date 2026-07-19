"""
EPIC D/E — tests immobilisations & main-d'œuvre (FIN-S30/S41, RC-FIN-53).

Covers:
  1. Asset Categories seedées avec les comptes SCE (22x/28x/681)
  2. Un Asset soumis génère son calendrier d'amortissement linéaire
     (Asset Depreciation Schedule) et porte le CF id_batiment → Batiment
  3. post_salaires : Journal Entry ventilée par atelier (640/421), équilibrée,
     idempotente

Pré-requis site : socle_comptable + immobilisations.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_immobilisations.run
"""
import traceback

import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.utils import charges_utils
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

PREFIX = "TEST-IMMO-"
ITEM = f"EQUIP-{PREFIX}TANK"
BATIMENT = f"{PREFIX}Etable"
# période dans l'exercice courant (les GL exigent un Fiscal Year actif)
PERIODE_MO = f"{getdate(today()).year}-03"


def _cleanup():
    for asset in frappe.get_all("Asset", filters={"item_code": ITEM}, pluck="name"):
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE against_voucher=%s OR voucher_no=%s",
                      (asset, asset))
        for sched in frappe.get_all("Asset Depreciation Schedule",
                                    filters={"asset": asset}, pluck="name"):
            frappe.db.sql("DELETE FROM `tabDepreciation Schedule` WHERE parent=%s", sched)
            frappe.db.sql("DELETE FROM `tabAsset Depreciation Schedule` WHERE name=%s", sched)
        frappe.db.sql("DELETE FROM `tabAsset Finance Book` WHERE parent=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
    frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent=%s", ITEM)
    frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent=%s", ITEM)
    frappe.db.sql("DELETE FROM `tabItem` WHERE name=%s", ITEM)
    frappe.db.sql("DELETE FROM `tabBatiment` WHERE name=%s", BATIMENT)
    je = charges_utils.existing_entry(PERIODE_MO)
    if je:
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  EPIC D/E — Immobilisations & MO (FIN-S30/S41)")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()

    # ── 1. Catégories seedées avec comptes SCE
    cat = "Installations et Matériel"
    acc = frappe.db.get_value(
        "Asset Category Account", {"parent": cat, "company_name": COMPANY},
        ["fixed_asset_account", "accumulated_depreciation_account",
         "depreciation_expense_account"], as_dict=True)
    _check(acc and acc.fixed_asset_account.startswith("223"),
           f"Catégorie '{cat}' → immo {acc.fixed_asset_account if acc else None}",
           results)
    _check(acc and acc.accumulated_depreciation_account.startswith("283"),
           "Amortissements sur 283", results)
    _check(acc and acc.depreciation_expense_account.startswith("681"),
           "Dotation sur 681", results)

    # ── 2. Asset → calendrier d'amortissement + CF bâtiment
    frappe.get_doc({
        "doctype": "Batiment", "nom_batiment": BATIMENT,
        "type_batiment": "PRODUCTION",
    }).insert(ignore_permissions=True)
    frappe.get_doc({
        "doctype": "Item", "item_code": ITEM, "item_name": "Tank à lait test",
        "item_group": "All Item Groups", "stock_uom": "Unit",
        "is_stock_item": 0, "is_fixed_asset": 1, "asset_category": cat,
    }).insert(ignore_permissions=True)
    asset = frappe.get_doc({
        "doctype": "Asset",
        "company": COMPANY,
        "item_code": ITEM,
        "asset_name": "Tank à lait test",
        "location": "Ferme HMD",
        "id_batiment": BATIMENT,
        "is_existing_asset": 1,
        "gross_purchase_amount": 12000,
        "purchase_date": "2026-01-01",
        "available_for_use_date": "2026-01-01",
        "calculate_depreciation": 1,
        "finance_books": [{
            "depreciation_method": "Straight Line",
            "total_number_of_depreciations": 10,
            "frequency_of_depreciation": 12,
            "depreciation_start_date": "2026-12-31",
        }],
    })
    asset.insert(ignore_permissions=True)
    asset.submit()
    frappe.db.commit()
    _check(asset.docstatus == 1, f"Asset {asset.name} soumis", results)
    _check(frappe.db.get_value("Asset", asset.name, "id_batiment") == BATIMENT,
           f"CF id_batiment → {BATIMENT} (RC-FIN-53)", results)
    sched = frappe.db.get_value("Asset Depreciation Schedule",
                                {"asset": asset.name, "docstatus": 1}, "name")
    _check(bool(sched), f"Calendrier d'amortissement généré ({sched})", results)
    if sched:
        rows = frappe.get_all("Depreciation Schedule",
                              filters={"parent": sched},
                              fields=["schedule_date", "depreciation_amount"],
                              order_by="idx")
        _check(len(rows) == 10, f"10 dotations annuelles (got {len(rows)})", results)
        if rows:
            _check(abs(float(rows[0].depreciation_amount) - 1200.0) < 0.01,
                   f"Dotation linéaire 12000/10 = {rows[0].depreciation_amount}",
                   results)

    # ── 3. Main-d'œuvre ventilée
    je_name = charges_utils.post_salaires(
        PERIODE_MO, {"Lait": 3000, "Traction": 1000})
    _check(bool(je_name), f"JE salaires créée ({je_name})", results)
    if je_name:
        je = frappe.get_doc("Journal Entry", je_name)
        _check(je.docstatus == 1, "JE soumise", results)
        _check(abs(je.total_debit - 4000.0) < 0.01,
               f"Total ventilé = {je.total_debit} (attendu 4000)", results)
        ccs = {a.cost_center for a in je.accounts if a.debit_in_account_currency}
        _check(any(c.startswith("Lait") for c in ccs)
               and any(c.startswith("Traction") for c in ccs),
               f"Débits 640 ventilés par atelier ({sorted(ccs)})", results)
    again = charges_utils.post_salaires(PERIODE_MO, {"Lait": 999})
    _check(again == je_name, "Re-run → même JE (idempotent)", results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
