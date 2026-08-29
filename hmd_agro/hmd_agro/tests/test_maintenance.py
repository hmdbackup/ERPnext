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

FIN-S96 — heures d'utilisation et coût mécanique (ERR-UTIL-01 → 05) :
  8. Validations de saisie : heures ≤ 0, heures > 24, équipement non soumis,
     date future, atelier groupe
  9. Calcul du coût : taux de la fiche équipement, puis repli sur le défaut
     de configuration (25 DT/h)
 10. `cout_utilisation` : agrégation par atelier et par équipement, et
     période vide = 0 honnête

SCRUM-11 — la fiche d'intervention saisie à l'écran (ERR-MNT-09 → 13) :
 11. `planifier_intervention` crée un brouillon Planned copiant équipement,
     type et atelier, sans coût ni date de fin ; date passée → ERR-MNT-11 ;
     l'équipement ne passe PAS « Out of Order » ; submit → ERR-MNT-13 ;
     `etat_fiche` ; salarié + prestataire → ERR-MNT-09 ; coût négatif →
     ERR-MNT-10 ; fiche Planned avec fin ou coût → ERR-MNT-12 ;
     `repair_cost` = pièces + M.O. (et inchangé sans ventilation)

Pré-requis site : socle comptable (dont « Fournisseur Divers »)
+ setup.finance.maintenance.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_maintenance.run
"""
import traceback

import frappe
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, today

from hmd_agro.hmd_agro.setup.finance.maintenance import setup_maintenance
from hmd_agro.hmd_agro.utils import finance_kpis, maintenance_utils
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    ETAT_A_VENIR, ETAT_TERMINEE, FOURNISSEUR_DEFAUT, HEURE_DEBUT_INTERVENTION,
    HEURE_FIN_INTERVENTION, STATUT_PLANIFIEE, STATUT_TERMINEE,
)

COMPANY = "hmd-agro"
ITEM_TEST = "ZZTEST-EQUIP"
ASSET_TEST = "ZZTEST Équipement"
ASSET_BROUILLON = "ZZTEST Équipement brouillon"
PREFIXE_REF = "ZZTEST_MNT"
PREFIXE_ASSET = "ZZTEST Équipement"
PREFIXE_PERSONNEL = "ZZTEST MNT"


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _cleanup():
    assets = frappe.get_all(
        "Asset", filters={"asset_name": ["like", f"{PREFIXE_ASSET}%"]}, pluck="name")
    # Par référence (fiches créées par `enregistrer_intervention`) ET par
    # équipement (fiches planifiées / saisies « à l'écran », sans référence).
    repairs = set(frappe.get_all(
        "Asset Repair", filters={"reference_hmd": ["like", f"{PREFIXE_REF}%"]},
        pluck="name"))
    if assets:
        repairs |= set(frappe.get_all(
            "Asset Repair", filters={"asset": ["in", assets]}, pluck="name"))
    for repair in repairs:
        je = frappe.db.get_value(
            "Journal Entry", {"user_remark": ["like", f"%MAINT_{repair}%"]}, "name")
        if je:
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
            frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
            frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
        frappe.db.sql("DELETE FROM `tabAsset Repair` WHERE name=%s", repair)
    for asset in assets:
        if frappe.db.table_exists("Utilisation Equipement"):
            frappe.db.sql(
                "DELETE FROM `tabUtilisation Equipement` WHERE equipement=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Log` WHERE asset_name=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Task` WHERE parent=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance` WHERE name=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Activity` WHERE asset=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
    # The test Item, once no Asset references it any more.
    if frappe.db.exists("Item", ITEM_TEST):
        frappe.delete_doc("Item", ITEM_TEST, force=1, ignore_permissions=True)
    for pers in frappe.get_all(
            "Personnel", filters={"nom_complet": ["like", f"{PREFIXE_PERSONNEL}%"]},
            pluck="name"):
        frappe.delete_doc("Personnel", pers, force=True, ignore_permissions=True)
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


def _asset_test(nom=ASSET_TEST, submit=True):
    if not frappe.db.exists("Item", ITEM_TEST):
        frappe.get_doc({
            "doctype": "Item", "item_code": ITEM_TEST, "item_name": "Équipement de test",
            "item_group": "All Item Groups", "stock_uom": "Unit",
            "is_stock_item": 0, "is_fixed_asset": 1,
            "asset_category": "Installations et Matériel",
        }).insert(ignore_permissions=True)
    asset = frappe.get_doc({
        "doctype": "Asset", "company": COMPANY, "item_code": ITEM_TEST,
        "asset_name": nom, "location": "Ferme HMD",
        "cost_center": f"Lait - {_abbr()}",
        "is_existing_asset": 1, "calculate_depreciation": 0,
        "gross_purchase_amount": 12000,
        "purchase_date": str(add_days(today(), -400)),
        "available_for_use_date": str(add_days(today(), -400)),
    })
    asset.insert(ignore_permissions=True)
    if submit:
        asset.submit()
    return asset.name


def _utilisation(equipement, heures, atelier, date=None, operateur=None):
    """FIN-S96 — une saisie d'heures d'utilisation (insert, pas de submit)."""
    doc = frappe.get_doc({
        "doctype": "Utilisation Equipement",
        "equipement": equipement,
        "date": date or today(),
        "heures": heures,
        "atelier": atelier,
        "operateur": operateur,
        "notes": "ZZTEST",
    })
    doc.insert(ignore_permissions=True)
    return doc


def _fiche(asset, description, statut=STATUT_TERMINEE, date=None, **champs):
    """SCRUM-11 — une fiche saisie « à l'écran » (insert, pas de submit)."""
    date = date or today()
    doc = frappe.get_doc({
        "doctype": "Asset Repair", "company": COMPANY, "asset": asset,
        "failure_date": f"{date} {HEURE_DEBUT_INTERVENTION}",
        "completion_date": (f"{date} {HEURE_FIN_INTERVENTION}"
                            if statut == STATUT_TERMINEE else None),
        "repair_status": statut, "description": description,
        "cost_center": f"Lait - {_abbr()}",
        **champs,
    })
    doc.insert(ignore_permissions=True)
    return doc


def _personnel_test():
    return frappe.get_doc({
        "doctype": "Personnel", "nom_complet": f"{PREFIXE_PERSONNEL} Mécanicien",
        "role_personnel": "MAINTENANCE", "date_embauche": "2024-01-01",
        "statut": "ACTIF", "salaire_brut_mensuel": 900,
        "atelier": f"Lait - {_abbr()}",
    }).insert(ignore_permissions=True)


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

    # ── 8. FIN-S96 — garde-fous de la saisie des heures
    lait = f"Lait - {_abbr()}"
    traction = (f"Traction - {_abbr()}"
                if frappe.db.exists("Cost Center", f"Traction - {_abbr()}") else lait)
    groupe = frappe.db.get_value(
        "Cost Center", {"company": COMPANY, "is_group": 1}, "name")

    _throws(lambda: _utilisation(asset, 0, lait),
            "ERR-UTIL-01", "Heures nulles refusées", results)
    _throws(lambda: _utilisation(asset, -3, lait),
            "ERR-UTIL-01", "Heures négatives refusées", results)
    _throws(lambda: _utilisation(asset, 30, lait),
            "ERR-UTIL-02", "Plus de 24 h sur une journée refusé", results)
    brouillon = _asset_test(ASSET_BROUILLON, submit=False)
    _throws(lambda: _utilisation(brouillon, 2, lait),
            "ERR-UTIL-03", "Équipement non soumis refusé", results)
    _throws(lambda: _utilisation(asset, 2, lait, date=add_days(today(), 3)),
            "ERR-UTIL-04", "Date d'utilisation future refusée", results)
    if groupe:
        _throws(lambda: _utilisation(asset, 2, groupe),
                "ERR-UTIL-05", "Atelier groupe refusé", results)

    # ── 9. FIN-S96 — coût mécanique : repli config puis taux de la fiche
    base_util = maintenance_utils.cout_utilisation(debut, fin)
    frappe.db.set_value("Asset", asset, "cout_horaire", 0, update_modified=False)
    _check(abs(maintenance_utils.cout_horaire(asset) - 25) < 0.001,
           "Sans taux sur la fiche → défaut de configuration (25 DT/h)", results)
    u1 = _utilisation(asset, 4, lait)
    _check(abs(u1.cout_horaire_applique - 25) < 0.001 and abs(u1.cout_total - 100) < 0.001,
           f"4 h × 25 DT/h = 100 TND ({u1.cout_total})", results)

    frappe.db.set_value("Asset", asset, "cout_horaire", 40, update_modified=False)
    _check(abs(maintenance_utils.cout_horaire(asset) - 40) < 0.001,
           "Taux de la fiche équipement prioritaire (40 DT/h)", results)
    u2 = _utilisation(asset, 2, traction)
    u3 = _utilisation(asset, 1, lait)
    _check(abs(u2.cout_total - 80) < 0.001 and abs(u3.cout_total - 40) < 0.001,
           f"2 h et 1 h × 40 DT/h = 80 et 40 TND ({u2.cout_total}, {u3.cout_total})",
           results)
    _check(abs(frappe.db.get_value("Utilisation Equipement", u1.name,
                                   "cout_total") - 100) < 0.001,
           "Taux figé à la saisie : changer la fiche ne réécrit pas le passé",
           results)

    # ── 10. FIN-S96 — agrégations et période vide
    util = maintenance_utils.cout_utilisation(debut, fin)
    _check(abs((util["total"] - base_util["total"]) - 220) < 0.01,
           f"cout_utilisation = 100 + 80 + 40 = 220 TND "
           f"({util['total'] - base_util['total']:.2f})", results)
    _check(abs((util["heures"] - base_util["heures"]) - 7) < 0.01,
           f"7 h cumulées sur la période ({util['heures'] - base_util['heures']:.2f})",
           results)
    par_eq = util["par_equipement"].get(asset, {})
    _check(abs(par_eq.get("heures", 0) - 7) < 0.01
           and abs(par_eq.get("cout", 0) - 220) < 0.01,
           f"Par équipement : 7 h / 220 TND ({par_eq})", results)
    delta_lait = (util["par_atelier"].get(lait, 0)
                  - base_util["par_atelier"].get(lait, 0))
    delta_traction = (util["par_atelier"].get(traction, 0)
                      - base_util["par_atelier"].get(traction, 0))
    if traction == lait:
        _check(abs(delta_lait - 220) < 0.01,
               f"Par atelier : 220 TND sur {lait} (atelier Traction absent)", results)
    else:
        _check(abs(delta_lait - 140) < 0.01 and abs(delta_traction - 80) < 0.01,
               f"Par atelier : 140 TND Lait / 80 TND Traction "
               f"({delta_lait:.2f} / {delta_traction:.2f})", results)

    vide = maintenance_utils.cout_utilisation("2000-01-01", "2000-01-31")
    _check(vide["total"] == 0 and vide["heures"] == 0
           and vide["par_atelier"] == {} and vide["par_equipement"] == {},
           "Période sans saisie → 0 honnête, aucun atelier inventé", results)

    # ── 11. SCRUM-11 — la fiche d'intervention saisie à l'écran
    # En dernier : ces fiches portent un coût sans écriture 615, ce qui
    # déplacerait `cout_maintenance` sous les pieds des contrôles 5 et 7.
    _test_fiche_intervention(asset, res["asset_repair"], results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results


def _test_fiche_intervention(asset, source, results):
    """SCRUM-11 — `planifier_intervention`, ERR-MNT-09 → 13, coût = pièces + M.O.

    `source` : la fiche Terminée et soumise du contrôle 1 (remplacement
    roulement, CURATIVE, 450 TND, atelier Lait).
    """
    origine = frappe.get_doc("Asset Repair", source)

    # ── Planifier la prochaine : un brouillon « À venir » qui copie la fiche
    statut_avant = frappe.db.get_value("Asset", asset, "status")
    date_prevue = add_days(today(), 15)
    nom = maintenance_utils.planifier_intervention(source, date_prevue)
    fiche = frappe.get_doc("Asset Repair", nom)
    _check(fiche.docstatus == 0 and fiche.repair_status == STATUT_PLANIFIEE,
           f"planifier_intervention crée un brouillon Planned ({nom})", results)
    _check(fiche.asset == asset and fiche.type_intervention == origine.type_intervention
           and fiche.cost_center == origine.cost_center,
           "Équipement, type et atelier copiés de la fiche source", results)
    _check(getdate(fiche.failure_date) == getdate(date_prevue)
           and not fiche.completion_date and not flt(fiche.repair_cost),
           "Datée au jour prévu, sans date de fin ni coût", results)
    _check(fiche.description == f"Prochaine : {origine.description}",
           "Libellé par défaut « Prochaine : … »", results)
    _check(maintenance_utils.etat_fiche(fiche) == ETAT_A_VENIR
           and maintenance_utils.etat_fiche(origine) == ETAT_TERMINEE,
           "etat_fiche : Planned → A_VENIR, Completed → TERMINEE", results)
    statut_apres = frappe.db.get_value("Asset", asset, "status")
    _check(statut_avant != "Out of Order" and statut_apres == statut_avant,
           f"Une fiche Planned ne passe PAS l'équipement « Out of Order » "
           f"(statut {statut_avant} → {statut_apres})", results)
    _throws(lambda: fiche.submit(),
            "ERR-MNT-13", "Valider une fiche Planned refusé", results)
    _throws(lambda: maintenance_utils.planifier_intervention(source, today()),
            "ERR-MNT-11", "Planifier à aujourd'hui refusé", results)
    _throws(lambda: maintenance_utils.planifier_intervention(
        source, add_days(today(), -1)),
        "ERR-MNT-11", "Planifier dans le passé refusé", results)
    nom_libelle = maintenance_utils.planifier_intervention(
        source, add_days(today(), 20), description="ZZTEST Révision 500 h")
    _check(frappe.db.get_value("Asset Repair", nom_libelle, "description")
           == "ZZTEST Révision 500 h",
           "Un libellé explicite remplace le libellé par défaut", results)

    # ── Garde-fous de saisie
    pers = _personnel_test()
    _throws(lambda: _fiche(asset, "ZZTEST deux intervenants",
                           personnel=pers.name, prestataire=FOURNISSEUR_DEFAUT),
            "ERR-MNT-09", "Salarié ET prestataire refusés", results)
    _throws(lambda: _fiche(asset, "ZZTEST coût négatif", cout_pieces=-5),
            "ERR-MNT-10", "Coût négatif refusé", results)
    _throws(lambda: _fiche(asset, "ZZTEST planifiée déjà finie",
                           statut=STATUT_PLANIFIEE, date=add_days(today(), 5),
                           completion_date=f"{add_days(today(), 5)} "
                                           f"{HEURE_FIN_INTERVENTION}"),
            "ERR-MNT-12", "Fiche Planned avec date de fin refusée", results)
    _throws(lambda: _fiche(asset, "ZZTEST planifiée chiffrée",
                           statut=STATUT_PLANIFIEE, date=add_days(today(), 5),
                           cout_main_oeuvre=40),
            "ERR-MNT-12", "Fiche Planned avec coût refusée", results)
    _throws(lambda: _fiche(asset, "ZZTEST planifiée hier",
                           statut=STATUT_PLANIFIEE, date=add_days(today(), -1)),
            "ERR-MNT-11", "Fiche Planned datée dans le passé refusée", results)

    # ── Coût de réparation = pièces + main-d'œuvre (sans facture rattachée)
    ventilee = _fiche(asset, "ZZTEST pièces + M.O.", cout_pieces=120,
                      cout_main_oeuvre=80, personnel=pers.name)
    _check(abs(ventilee.repair_cost - 200) < 0.001
           and abs(ventilee.total_repair_cost - 200) < 0.001,
           f"repair_cost = 120 + 80 = 200 ({ventilee.repair_cost})", results)
    pieces_seules = _fiche(asset, "ZZTEST pièces seules", cout_pieces=120)
    _check(abs(pieces_seules.repair_cost - 120) < 0.001,
           "Pièces seules → repair_cost = 120", results)
    _check(abs(frappe.get_doc("Asset Repair", source).repair_cost - 450) < 0.001,
           "Sans ventilation, le coût saisi en bloc (450) reste tel quel", results)

    # ── Miroir : une fiche Pending (panne déclarée), elle, met l'équipement
    # « Out of Order » — c'est ce qui rend le contrôle Planned discriminant.
    panne = _fiche(asset, "ZZTEST panne déclarée", statut="Pending")
    _check(frappe.db.get_value("Asset", asset, "status") == "Out of Order",
           "Une fiche Pending ouverte passe l'équipement « Out of Order »", results)
    frappe.delete_doc("Asset Repair", panne.name, force=1, ignore_permissions=True)
    frappe.db.set_value("Asset", asset, "status", statut_avant, update_modified=False)
