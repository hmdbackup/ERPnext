"""
FIN-S32 — tests des interventions et de la maintenance des équipements
(RG-FIN-30/31, RC-FIN-54, CF-FIN-31).

Couvre :
  1. `enregistrer_intervention` : Asset Repair de suivi + écriture de charge
     615 ventilée sur l'atelier de l'équipement
  2. Les trois modes de règlement (fournisseur avec tiers, caisse, banque)
  3. Intervention interne (coût 0) → suivi sans écriture
  4. Idempotence par `reference`, garde-fous ERR-MNT-01/02/04
  5. `cout_maintenance` et `gl_sums['entretien']` lisent bien le 615
  6. `planifier_maintenance` : tâches périodiques + Asset Maintenance Log
     datés (échéances réellement calculées)
  7. `annuler_intervention` : annulation symétrique document + écriture

Pré-requis site : socle comptable + setup.finance.maintenance.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_maintenance.run
"""
import traceback

import frappe
from frappe.utils import add_days, get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.setup.finance.maintenance import setup_maintenance
from hmd_agro.hmd_agro.utils import finance_kpis, maintenance_utils

COMPANY = "hmd-agro"
ITEM_TEST = "ZZTEST-EQUIP"
ASSET_TEST = "ZZTEST Équipement"
PREFIXE_REF = "ZZTEST_MNT"


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _cleanup():
    for repair in frappe.get_all(
            "Asset Repair", filters={"reference_hmd": ["like", f"{PREFIXE_REF}%"]},
            pluck="name"):
        je = frappe.db.get_value(
            "Journal Entry", {"user_remark": ["like", f"%MAINT_{repair}%"]}, "name")
        if je:
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
            frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
            frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
        frappe.db.sql("DELETE FROM `tabAsset Repair` WHERE name=%s", repair)
    for asset in frappe.get_all("Asset", filters={"asset_name": ASSET_TEST}, pluck="name"):
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Log` WHERE asset_name=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Task` WHERE parent=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance` WHERE name=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Activity` WHERE asset=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _throws(fn, code, msg, results):
    try:
        fn()
        _check(False, f"{msg} (aucune exception)", results)
    except Exception as exc:
        _check(code in str(exc), f"{msg} → {code}", results)


def _asset_test():
    if not frappe.db.exists("Item", ITEM_TEST):
        frappe.get_doc({
            "doctype": "Item", "item_code": ITEM_TEST, "item_name": "Équipement de test",
            "item_group": "All Item Groups", "stock_uom": "Unit",
            "is_stock_item": 0, "is_fixed_asset": 1,
            "asset_category": "Installations et Matériel",
        }).insert(ignore_permissions=True)
    asset = frappe.get_doc({
        "doctype": "Asset", "company": COMPANY, "item_code": ITEM_TEST,
        "asset_name": ASSET_TEST, "location": "Ferme HMD",
        "cost_center": f"Lait - {_abbr()}",
        "is_existing_asset": 1, "calculate_depreciation": 0,
        "gross_purchase_amount": 12000,
        "purchase_date": str(add_days(today(), -400)),
        "available_for_use_date": str(add_days(today(), -400)),
    })
    asset.insert(ignore_permissions=True)
    asset.submit()
    return asset.name


def _numeros(je_name):
    """{account_number: (debit, credit, cost_center)} d'une écriture."""
    out = {}
    for ligne in frappe.get_doc("Journal Entry", je_name).accounts:
        numero = frappe.db.get_value("Account", ligne.account, "account_number")
        out[numero] = (ligne.debit_in_account_currency or 0,
                       ligne.credit_in_account_currency or 0,
                       ligne.cost_center, ligne.party)
    return out


def run():
    print("\n" + "=" * 70)
    print("  FIN-S32 — Interventions & maintenance des équipements")
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
    setup_maintenance()

    debut, fin = str(get_first_day(today())), str(get_last_day(today()))
    base_cout = maintenance_utils.cout_maintenance(debut, fin)["cout"]
    base_gl = finance_kpis.gl_sums(debut, fin)["entretien"]
    asset = _asset_test()

    # ── 1. Intervention curative avec charge fournisseur
    res = maintenance_utils.enregistrer_intervention(
        asset=asset, description="ZZTEST — remplacement roulement", cout=450,
        type_intervention="CURATIVE", arret="6 h",
        reference=f"{PREFIXE_REF}_1")
    _check(bool(res["asset_repair"]), f"Asset Repair créé ({res['asset_repair']})", results)
    repair = frappe.get_doc("Asset Repair", res["asset_repair"])
    _check(repair.docstatus == 1 and repair.repair_status == "Completed",
           "Intervention soumise et marquée Completed", results)
    _check(repair.type_intervention == "CURATIVE" and repair.downtime == "6 h",
           "Type d'intervention et durée d'arrêt enregistrés", results)
    _check(repair.cost_center == f"Lait - {_abbr()}",
           f"Atelier hérité de l'équipement ({repair.cost_center})", results)

    _check(bool(res["journal_entry"]),
           f"Écriture de charge postée ({res['journal_entry']})", results)
    lignes = _numeros(res["journal_entry"])
    _check("615" in lignes and abs(lignes["615"][0] - 450) < 0.01,
           "615 Entretien et réparations débité de 450 TND", results)
    _check(lignes["615"][2] == f"Lait - {_abbr()}",
           "Charge d'entretien imputée à l'atelier (RG-FIN-40)", results)
    _check("401" in lignes and abs(lignes["401"][1] - 450) < 0.01
           and lignes["401"][3] == "Fournisseur Divers",
           "401 Fournisseurs crédité avec le tiers renseigné", results)

    # ── 2. Autres modes de règlement
    res_caisse = maintenance_utils.enregistrer_intervention(
        asset=asset, description="ZZTEST — petite fourniture", cout=60,
        mode_reglement="CAISSE", reference=f"{PREFIXE_REF}_2")
    _check("54" in _numeros(res_caisse["journal_entry"]),
           "Mode CAISSE → crédit du compte 54", results)
    res_banque = maintenance_utils.enregistrer_intervention(
        asset=asset, description="ZZTEST — révision atelier", cout=90,
        mode_reglement="BANQUE", reference=f"{PREFIXE_REF}_3")
    _check("532" in _numeros(res_banque["journal_entry"]),
           "Mode BANQUE → crédit du compte 532", results)

    # ── 3. Intervention interne : suivi sans écriture
    res_interne = maintenance_utils.enregistrer_intervention(
        asset=asset, description="ZZTEST — nettoyage interne", cout=0,
        reference=f"{PREFIXE_REF}_4")
    _check(res_interne["journal_entry"] is None,
           "Intervention à coût nul → aucune écriture comptable", results)

    # ── 4. Idempotence et garde-fous
    rejoue = maintenance_utils.enregistrer_intervention(
        asset=asset, description="ZZTEST — remplacement roulement", cout=450,
        reference=f"{PREFIXE_REF}_1")
    _check(rejoue["asset_repair"] == res["asset_repair"],
           "Même référence → aucune intervention en double", results)
    _throws(lambda: maintenance_utils.enregistrer_intervention(
        asset="ZZ-INEXISTANT", description="x", cout=10),
        "ERR-MNT-01", "Équipement inconnu refusé", results)
    _throws(lambda: maintenance_utils.enregistrer_intervention(
        asset=asset, description="x", cout=10, mode_reglement="TROC",
        reference=f"{PREFIXE_REF}_9"),
        "ERR-MNT-04", "Mode de règlement inconnu refusé", results)

    # ── 5. Lectures
    cout = maintenance_utils.cout_maintenance(debut, fin)
    _check(abs((cout["cout"] - base_cout) - 600) < 0.01,
           f"cout_maintenance = 450 + 60 + 90 = 600 TND "
           f"({cout['cout'] - base_cout:.2f})", results)
    _check(cout["interventions"] >= 4 and asset in cout["par_equipement"],
           f"{cout['interventions']} interventions comptées, équipement listé", results)
    gl = finance_kpis.gl_sums(debut, fin)
    _check(abs((gl["entretien"] - base_gl) - 600) < 0.01,
           "gl_sums['entretien'] agrège le compte 615", results)

    # ── 6. Maintenance préventive
    plan = maintenance_utils.planifier_maintenance(asset, [
        {"tache": "ZZTEST Vidange", "periodicite": "Half-yearly",
         "date_debut": str(today())},
        {"tache": "ZZTEST Contrôle", "periodicite": "Yearly",
         "date_debut": str(today())},
    ])
    _check(bool(plan), f"Plan de maintenance créé ({plan})", results)
    _check(frappe.db.get_value("Asset", asset, "maintenance_required") == 1,
           "Équipement marqué « maintenance requise »", results)
    logs = frappe.get_all("Asset Maintenance Log",
                          filters={"asset_maintenance": plan},
                          fields=["task_name", "due_date", "maintenance_status"])
    _check(len(logs) == 2, f"{len(logs)} échéances générées par ERPNext", results)
    _check(all(l.due_date for l in logs),
           "Chaque échéance porte une date (calcul de périodicité)", results)
    semestre = next((l for l in logs if l.task_name == "ZZTEST Vidange"), None)
    _check(semestre and 150 < (getdate(semestre.due_date) - getdate(today())).days < 200,
           "Périodicité semestrielle → échéance à ~6 mois", results)
    _check(maintenance_utils.planifier_maintenance(asset, [
        {"tache": "ZZTEST Vidange", "periodicite": "Half-yearly"}]) == plan,
        "Re-planifier une tâche connue = no-op", results)

    # ── 7. Annulation symétrique (CF-FIN-31)
    je_annule = maintenance_utils.annuler_intervention(res_banque["asset_repair"])
    _check(frappe.db.get_value("Asset Repair", res_banque["asset_repair"],
                               "docstatus") == 2,
           "Intervention annulée", results)
    _check(frappe.db.get_value("Journal Entry", je_annule, "docstatus") == 2,
           "Écriture de charge annulée avec elle", results)
    apres = maintenance_utils.cout_maintenance(debut, fin)
    _check(abs((apres["cout"] - base_cout) - 510) < 0.01,
           f"Coût d'entretien ramené à 510 TND après annulation "
           f"({apres['cout'] - base_cout:.2f})", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
