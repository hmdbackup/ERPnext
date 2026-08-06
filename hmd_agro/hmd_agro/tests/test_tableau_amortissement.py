"""
TASK B3 — tests du Tableau d'amortissement consolidé + coût horaire équipement.

Covers:
  1. Rapport « Tableau Amortissement » sur un équipement 5 ans :
     durée 60 mois, cumul + reste = valeur brute, pas de date de sortie
  2. Le tracteur démo (FIN-S30), s'il est présent : 60 mois attendus
  3. Un actif cheptel repris (opening depreciation) : mois amortis =
     annuités courues × fréquence, cumul = amortissement d'ouverture
  4. Filtres : asset_category restreint, inclure_sortis=0 masque les sortis
  5. Résolveur cout_horaire : Asset.cout_horaire sinon défaut
     equipement_cout_horaire_defaut (25 DT/h)

Pré-requis site : socle_comptable + immobilisations.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_tableau_amortissement.run
"""
import traceback

import frappe
from frappe.utils import flt, get_last_day, getdate, today

from hmd_agro.hmd_agro.report.tableau_amortissement.tableau_amortissement import (
    execute as report_execute,
)
from hmd_agro.hmd_agro.utils import maintenance_utils
from hmd_agro.hmd_agro.utils.config import get_config
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

PREFIX = "TEST-AMORT-"
ITEM_EQUIP = f"EQUIP-{PREFIX}CAMION"
ITEM_CHEPTEL = f"CHEPTEL-{PREFIX}VACHE"
CAT_EQUIP = "Matériel de transport"      # 5 ans × 12 mois = 60
CAT_CHEPTEL = "Cheptel reproducteur"     # 5 ans × 12 mois = 60


def _cleanup():
    for item in (ITEM_EQUIP, ITEM_CHEPTEL):
        for asset in frappe.get_all("Asset", filters={"item_code": item},
                                    pluck="name"):
            frappe.db.sql(
                "DELETE FROM `tabGL Entry` WHERE against_voucher=%s OR voucher_no=%s",
                (asset, asset))
            for sched in frappe.get_all("Asset Depreciation Schedule",
                                        filters={"asset": asset}, pluck="name"):
                frappe.db.sql("DELETE FROM `tabDepreciation Schedule` WHERE parent=%s",
                              sched)
                frappe.db.sql("DELETE FROM `tabAsset Depreciation Schedule` WHERE name=%s",
                              sched)
            frappe.db.sql("DELETE FROM `tabAsset Finance Book` WHERE parent=%s", asset)
            frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
        frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent=%s", item)
        frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent=%s", item)
        frappe.db.sql("DELETE FROM `tabItem` WHERE name=%s", item)
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _make_item(item_code, item_name, category):
    if frappe.db.exists("Item", item_code):
        return
    frappe.get_doc({
        "doctype": "Item", "item_code": item_code, "item_name": item_name,
        "item_group": "All Item Groups", "stock_uom": "Unit",
        "is_stock_item": 0, "is_fixed_asset": 1, "asset_category": category,
    }).insert(ignore_permissions=True)


def _row_of(data, asset_name):
    return next((r for r in data if r["actif"] == asset_name), None)


def run():
    print("\n" + "=" * 70)
    print("  TASK B3 — Tableau d'amortissement + coût horaire équipement")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}
    finally:
        _cleanup()


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()
    annee = getdate(today()).year

    # ── 1. Équipement 5 ans → 60 mois
    _make_item(ITEM_EQUIP, "Camion test amortissement", CAT_EQUIP)
    equip = frappe.get_doc({
        "doctype": "Asset",
        "company": COMPANY,
        "item_code": ITEM_EQUIP,
        "asset_name": "Camion test amortissement",
        "location": "Ferme HMD",
        "is_existing_asset": 1,
        "gross_purchase_amount": 30000,
        "purchase_date": f"{annee}-01-01",
        "available_for_use_date": f"{annee}-01-01",
        "calculate_depreciation": 1,
        "finance_books": [{
            "depreciation_method": "Straight Line",
            "total_number_of_depreciations": 5,
            "frequency_of_depreciation": 12,
            "depreciation_start_date": str(get_last_day(f"{annee}-12-01")),
        }],
    })
    equip.insert(ignore_permissions=True)
    equip.submit()

    # ── 2. Cheptel repris : 2 annuités déjà courues sur 5
    animal = frappe.db.get_value("Animal", {"statut": "ACTIF"}, "name")
    _make_item(ITEM_CHEPTEL, "Vache test amortissement", CAT_CHEPTEL)
    cheptel = frappe.get_doc({
        "doctype": "Asset",
        "company": COMPANY,
        "item_code": ITEM_CHEPTEL,
        "asset_name": "Vache test amortissement",
        "location": "Ferme HMD",
        "id_animal": animal,
        "is_existing_asset": 1,
        "gross_purchase_amount": 15000,
        "opening_accumulated_depreciation": 6000,
        "opening_number_of_booked_depreciations": 2,
        "purchase_date": f"{annee - 2}-01-01",
        "available_for_use_date": f"{annee - 2}-01-01",
        "calculate_depreciation": 1,
        "finance_books": [{
            "depreciation_method": "Straight Line",
            "total_number_of_depreciations": 5,
            "frequency_of_depreciation": 12,
            "depreciation_start_date": str(get_last_day(today())),
        }],
    })
    cheptel.insert(ignore_permissions=True)
    cheptel.submit()
    frappe.db.commit()

    columns, data = report_execute({"inclure_sortis": 1})
    _check(len(columns) == 13, f"13 colonnes déclarées (got {len(columns)})", results)

    ligne = _row_of(data, equip.name)
    _check(bool(ligne), f"Équipement {equip.name} présent au tableau", results)
    if ligne:
        _check(ligne["duree_mois"] == 60,
               f"Durée équipement 5 ans = 60 mois (got {ligne['duree_mois']})",
               results)
        _check(ligne["mois_amortis"] == 0,
               f"Aucune dotation postée → 0 mois amorti (got {ligne['mois_amortis']})",
               results)
        _check(abs(flt(ligne["amortissement_cumule"]) + flt(ligne["reste_a_amortir"])
                   - 30000.0) < 0.01,
               "Cumul + reste = valeur brute (30 000)", results)
        _check(not ligne["date_sortie"], "Actif en service : date de sortie vide",
               results)
        _check(ligne["categorie"] == CAT_EQUIP,
               f"Catégorie = {CAT_EQUIP}", results)

    # ── Tracteur démo (FIN-S30), si le seed est passé
    tracteur = frappe.db.get_value(
        "Asset", {"asset_name": "Tracteur Démo", "docstatus": 1}, "name")
    if tracteur:
        ligne_t = _row_of(data, tracteur)
        _check(bool(ligne_t), f"Tracteur démo {tracteur} présent", results)
        if ligne_t:
            _check(ligne_t["duree_mois"] == 60,
                   f"Tracteur démo : 60 mois attendus (got {ligne_t['duree_mois']})",
                   results)
    else:
        print("  SKIP Tracteur Démo absent (seed_demo_finance non lancé)")

    # ── Cheptel : reprise d'existant
    ligne_c = _row_of(data, cheptel.name)
    _check(bool(ligne_c), f"Actif cheptel {cheptel.name} présent", results)
    if ligne_c:
        _check(ligne_c["duree_mois"] == 60,
               f"Durée cheptel 5 ans = 60 mois (got {ligne_c['duree_mois']})", results)
        _check(ligne_c["mois_amortis"] == 24,
               f"2 annuités courues × 12 = 24 mois amortis (got {ligne_c['mois_amortis']})",
               results)
        _check(abs(flt(ligne_c["amortissement_cumule"]) - 6000.0) < 0.01,
               f"Cumul = amortissement d'ouverture 6 000 "
               f"(got {ligne_c['amortissement_cumule']})", results)
        _check(abs(flt(ligne_c["reste_a_amortir"]) - 9000.0) < 0.01,
               f"Reste à amortir 9 000 (got {ligne_c['reste_a_amortir']})", results)
        if animal:
            _check(ligne_c["animal"] == animal,
                   f"Colonne Animal ← id_animal ({animal})", results)

    # ── 4. Filtres
    _, data_cat = report_execute({"asset_category": CAT_EQUIP, "inclure_sortis": 1})
    _check(bool(_row_of(data_cat, equip.name)) and not _row_of(data_cat, cheptel.name),
           "Filtre catégorie : équipement gardé, cheptel exclu", results)

    _, data_actifs = report_execute({"inclure_sortis": 0})
    _check(all(not r["date_sortie"] for r in data_actifs),
           "inclure_sortis=0 : aucune ligne avec date de sortie", results)

    # ── 5. Coût horaire : défaut config puis valeur de l'actif
    attendu = flt(get_config("equipement_cout_horaire_defaut", default=25)) or 25.0
    _check(abs(maintenance_utils.cout_horaire(equip.name) - attendu) < 0.001,
           f"cout_horaire vide → défaut config ({attendu} DT/h)", results)
    frappe.db.set_value("Asset", equip.name, "cout_horaire", 40,
                        update_modified=False)
    _check(abs(maintenance_utils.cout_horaire(equip.name) - 40.0) < 0.001,
           "cout_horaire renseigné (40) → prime sur le défaut", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
