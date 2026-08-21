"""
SCRUM-11 — tests du Rapport Interventions.

Couvre :
  1. Structure : les 9 colonnes typées, les 3 sections présentes
  2. Une intervention saisie apparaît en ligne (équipement, atelier, coût)
     et le TOTAL compte les interventions ET les équipements distincts
  3. Un Asset Repair en BROUILLON n'est pas une intervention → exclu
  4. Rapprochement — une intervention saisie normalement ne crée AUCUN écart
     (elle alimente le 615 et la liste du même montant)
  5. Rapprochement — une charge 615 passée SANS Asset Repair crée un écart
     positif du montant exact : c'est la raison d'être du bloc
  6. Un équipement VENDU / REBUT reste visible pour ses interventions
     antérieures (STATUTS_ASSET_BLOQUANTS bloque la SAISIE, pas la LECTURE)
  7. Une intervention sans atelier est signalée dans le libellé, et la
     colonne Link reste vide (pas de lien mort vers « Frais Généraux »)
  8. Un filtre Équipement ou Atelier MASQUE le rapprochement — le confronter
     à un Grand Livre non filtré produirait un écart faux
  9. Une période entièrement future renvoie le message INFO

Fixtures isolées sur mai 2025, préfixe ZZTEST_RINT. Le choix du mois n'est pas
libre : il doit tomber dans un exercice comptable ACTIF (sans quoi le submit
d'une écriture lève FiscalYearError) tout en restant vierge de données réelles.

Pré-requis site : socle comptable + setup.finance.maintenance.

Run: bench --site hmd.agro execute \
        hmd_agro.hmd_agro.tests.test_rapport_interventions.run
"""
import traceback

import frappe
from frappe.utils import add_days, getdate, today

from hmd_agro.hmd_agro.report.rapport_interventions.rapport_interventions import (
    COLUMNS, execute,
)
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    enregistrer_intervention, planifier_maintenance,
)

COMPANY = "hmd-agro"
ITEM_TEST = "ZZTEST-EQUIP-RINT"
PREFIXE_REF = "ZZTEST_RINT"
PREFIXE_ASSET = "ZZTEST Interv"

# Mai 2025 : exercice comptable ACTIF (obligatoire — une écriture hors exercice
# lève FiscalYearError au submit) et mois vierge de toute intervention comme de
# toute écriture 615 sur le site réel, ce qui rend les totaux absolus fiables.
MOIS_DATE = "2025-05-15"          # mai 2025 → 01/05 - 31/05
INTERV_DATE = "2025-05-10"

FILTRES_MOIS = {"periode": "Mois", "date": MOIS_DATE}


def _abbr():
    return frappe.db.get_value("Company", COMPANY, "abbr")


def _acc(number):
    return frappe.db.get_value("Account",
                               {"company": COMPANY, "account_number": number})


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _cleanup():
    for je in frappe.get_all(
            "Journal Entry",
            filters={"user_remark": ["like", f"%{PREFIXE_REF}%"]}, pluck="name"):
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
        frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)
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
    for asset in frappe.get_all(
            "Asset", filters={"asset_name": ["like", f"{PREFIXE_ASSET}%"]},
            pluck="name"):
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Log` WHERE asset_name=%s",
                      asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Task` WHERE parent=%s",
                      asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance` WHERE name=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Activity` WHERE asset=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
    frappe.db.commit()


# ─── Fixtures ───

def _asset_test(nom):
    if not frappe.db.exists("Item", ITEM_TEST):
        frappe.get_doc({
            "doctype": "Item", "item_code": ITEM_TEST,
            "item_name": "Équipement de test (interventions)",
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
        "purchase_date": str(add_days(today(), -800)),
        "available_for_use_date": str(add_days(today(), -800)),
    })
    asset.insert(ignore_permissions=True)
    asset.submit()
    return asset.name


def _charge_615_directe(montant, date):
    """Une facture d'entretien passée au 615 SANS Asset Repair.

    Le cas réel qui crée l'écart : la comptable saisit la facture du
    garagiste, personne ne crée l'intervention côté équipement.
    """
    cc = f"Lait - {_abbr()}"
    je = frappe.get_doc({
        "doctype": "Journal Entry", "company": COMPANY,
        "voucher_type": "Journal Entry", "posting_date": date,
        "user_remark": f"{PREFIXE_REF}_DIRECT",
        "accounts": [
            {"account": _acc("615"), "debit_in_account_currency": montant,
             "cost_center": cc},
            {"account": _acc("54"), "credit_in_account_currency": montant,
             "cost_center": cc},
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


# ─── Lectures ───

def _rows(filtres=None):
    return execute(filtres or dict(FILTRES_MOIS))[1]


def _section(rows, prefixe):
    return [r for r in rows if r["section"].startswith(prefixe)]


def _ligne(rows, libelle_contient):
    return next((r for r in rows if r["libelle"]
                 and libelle_contient in r["libelle"]), None)


def _ecart(rows):
    ligne = _ligne(rows, "Écart —")
    return ligne["cout"] if ligne else None


# ─── Tests ───

def _test_structure(results):
    print("\n[1] Structure")
    rows = _rows()
    attendus = ["section", "date", "equipement", "designation", "type",
                "libelle", "atelier", "intervenant", "cout",
                "nb_interventions", "nb_equipements"]
    _check([c["fieldname"] for c in COLUMNS] == attendus,
           "les 11 colonnes attendues, dans l'ordre", results)
    types = {c["fieldname"]: c["fieldtype"] for c in COLUMNS}
    _check(types.get("nb_interventions") == "Int"
           and types.get("nb_equipements") == "Int",
           "les deux compteurs sont des entiers (triables, exportables)",
           results)
    _check(_section(rows, "Réalisées"), "section « Réalisées » présente", results)
    _check(_section(rows, "Préventif"), "section « Préventif » présente", results)
    _check(_section(rows, "Rapprochement"),
           "section « Rapprochement » présente", results)
    # Le libellé du préventif doit dire « à ce jour » : il n'est PAS borné par
    # la période, et le cacher induirait en erreur sur un mois passé.
    prev = _section(rows, "Préventif")
    _check(prev and "à ce jour" in prev[0]["section"],
           "la section Préventif annonce qu'elle n'est pas bornée par la période",
           results)


def _test_mois_vide_affiche_zero(results):
    """Critère 5 — un mois sans intervention affiche ZÉRO, pas une erreur.

    Appelé AVANT toute création : mai 2025 est encore vierge à ce moment-là,
    ce qui rend le total absolu (0) déterministe plutôt que « au moins ».
    """
    print("\n[1b] Un mois sans intervention affiche zéro")
    rows = _rows()
    realisees = _section(rows, "Réalisées")
    _check(_ligne(realisees, "Aucune intervention saisie") is not None,
           "la phrase « aucune intervention » est affichée", results)
    total = _ligne(realisees, "TOTAL —")
    _check(total is not None, "une ligne TOTAL est présente malgré le vide",
           results)
    if total:
        _check(total["cout"] == 0 and total["nb_interventions"] == 0
               and total["nb_equipements"] == 0,
               "le TOTAL vaut 0 DT / 0 intervention / 0 équipement", results)
    # Et surtout : pas d'erreur, le rapport reste complet.
    _check(_section(rows, "Rapprochement") != [],
           "le rapprochement reste calculé sur un mois vide", results)


def _test_periode_en_cours_annoncee(results):
    """Le mois EN COURS s'arrête à aujourd'hui — le rapport doit le dire.

    Sans cet avertissement, le TOTAL d'un mois entamé se lit comme celui du
    mois entier, et l'écart au 615 paraît anormalement négatif.
    """
    print("\n[10b] Le mois en cours annonce qu'il est tronqué")
    aujourdhui = getdate(today())
    rows = execute({"periode": "Mois", "date": str(aujourdhui)})[1]
    info = _ligne(rows, "Période en cours")
    dernier_jour = _fin_de_mois(aujourdhui)
    if aujourdhui < dernier_jour:
        _check(info is not None,
               "un mois entamé annonce que les chiffres sont arrêtés à ce jour",
               results)
        if info:
            _check(aujourdhui.strftime("%d/%m/%Y") in info["libelle"],
                   "l'avertissement cite la date d'arrêt", results)
    else:
        # Dernier jour du mois : il n'y a rien à tronquer, donc rien à annoncer.
        _check(info is None,
               "le dernier jour du mois, aucun avertissement n'est affiché",
               results)


def _fin_de_mois(date):
    from calendar import monthrange
    return getdate(f"{date.year}-{date.month:02d}-"
                   f"{monthrange(date.year, date.month)[1]}")


def _test_ligne_et_total(asset, results):
    print("\n[2] Une intervention saisie apparaît, et le total compte juste")
    enregistrer_intervention(
        asset=asset, description="ZZTEST Vidange moteur", cout=300,
        date=INTERV_DATE, type_intervention="PREVENTIVE",
        mode_reglement="CAISSE", reference=f"{PREFIXE_REF}_A")
    rows = _rows()
    ligne = _ligne(rows, "ZZTEST Vidange moteur")
    _check(ligne is not None, "l'intervention est listée", results)
    if ligne:
        _check(ligne["equipement"] == asset, "elle porte son équipement", results)
        _check(ligne["cout"] == 300, "elle porte son coût (300 DT)", results)
        _check(ligne["atelier"] == f"Lait - {_abbr()}",
               "elle porte l'atelier de l'équipement", results)
        _check(ligne["type"] == "PREVENTIVE", "elle porte son type", results)
    total = _ligne(rows, "TOTAL —")
    # Montant exact, pas « au moins » : mai 2025 est vierge, le total est
    # parfaitement déterministe. Et libellé comparé en entier — « 1 » est une
    # sous-chaîne de « 11 », un `in` laisserait passer une régression.
    _check(total is not None and total["cout"] == 300,
           "la ligne TOTAL vaut exactement 300 DT", results)
    _check(total is not None
           and total["libelle"] == "TOTAL — 1 intervention(s), 1 équipement(s)",
           "le TOTAL compte 1 intervention sur 1 équipement", results)
    # Critère 2 — les compteurs doivent être des NOMBRES, pas seulement du texte
    # dans le libellé : c'est ce qui les rend triables et exportables.
    _check(total is not None and total["nb_interventions"] == 1
           and total["nb_equipements"] == 1,
           "le TOTAL porte les compteurs en colonnes chiffrées (1 et 1)",
           results)
    detail = _ligne(rows, "ZZTEST Vidange moteur")
    _check(detail is not None and detail["nb_interventions"] is None
           and detail["nb_equipements"] is None,
           "les lignes de détail laissent les compteurs vides (pas de double "
           "comptage à l'export)", results)


def _test_brouillon_exclu(asset, results):
    print("\n[3] Un Asset Repair en brouillon n'est pas une intervention")
    enregistrer_intervention(
        asset=asset, description="ZZTEST Brouillon à ignorer", cout=999,
        date=INTERV_DATE, mode_reglement="CAISSE",
        reference=f"{PREFIXE_REF}_DRAFT", submit=False)
    rows = _rows()
    _check(_ligne(rows, "ZZTEST Brouillon à ignorer") is None,
           "le brouillon est absent du rapport (docstatus = 1 exigé)", results)
    total = _ligne(rows, "TOTAL —")
    _check(total is not None
           and total["libelle"] == "TOTAL — 1 intervention(s), 1 équipement(s)"
           and total["cout"] == 300,
           "le TOTAL n'a pas bougé", results)


def _test_rapprochement_sans_ecart(results):
    print("\n[4] Une intervention normale ne crée aucun écart")
    rows = _rows()
    gl = _ligne(rows, "Grand Livre (compte 615)")
    saisi = _ligne(rows, "Somme des interventions saisies")
    _check(gl is not None and saisi is not None,
           "les deux montants du rapprochement sont affichés", results)
    _check(_ecart(rows) == 0,
           "écart nul : le 615 et la liste ont bougé du même montant", results)
    ligne_ecart = _ligne(rows, "Écart —")
    _check(ligne_ecart is not None and ligne_ecart["indicator"] == "Green",
           "un écart nul s'affiche en vert", results)


def _test_rapprochement_avec_ecart(results):
    print("\n[5] Une charge 615 sans Asset Repair crée l'écart")
    avant = _ecart(_rows())
    _charge_615_directe(500, INTERV_DATE)
    rows = _rows()
    apres = _ecart(rows)
    _check(apres is not None and round(apres - avant, 2) == 500,
           f"l'écart augmente de 500 DT exactement ({avant} → {apres})", results)
    ligne = _ligne(rows, "Écart —")
    _check(ligne is not None and ligne["indicator"] == "Orange",
           "un écart non nul s'affiche en orange", results)
    _check(ligne is not None and "SANS intervention saisie" in ligne["libelle"],
           "le libellé nomme la cause (facture non rattachée)", results)


def _test_equipement_sorti(results):
    print("\n[6] Un équipement sorti reste visible pour son passé")
    asset = _asset_test(f"{PREFIXE_ASSET} sorti")
    enregistrer_intervention(
        asset=asset, description="ZZTEST Réparation avant cession", cout=120,
        date=INTERV_DATE, mode_reglement="CAISSE",
        reference=f"{PREFIXE_REF}_SORTI")
    # On force le statut : le flux de cession complet n'a rien à voir avec ce
    # que le rapport doit prouver — il doit LIRE un équipement sorti.
    frappe.db.set_value("Asset", asset, "status", "Scrapped")
    frappe.db.commit()
    rows = _rows()
    _check(_ligne(rows, "ZZTEST Réparation avant cession") is not None,
           "l'intervention d'un équipement REBUT reste listée", results)


def _test_atelier_absent(asset, results):
    print("\n[7] Une intervention sans atelier est signalée")
    res = enregistrer_intervention(
        asset=asset, description="ZZTEST Sans atelier", cout=80,
        date=INTERV_DATE, mode_reglement="CAISSE",
        reference=f"{PREFIXE_REF}_NOCC")
    # Cas d'une saisie faite directement dans l'écran ERPNext, hors
    # `enregistrer_intervention` (qui, lui, impute toujours un atelier).
    frappe.db.set_value("Asset Repair", res["asset_repair"], "cost_center", None)
    frappe.db.commit()
    rows = _rows()
    ligne = _ligne(rows, "ZZTEST Sans atelier")
    _check(ligne is not None and "aucun atelier imputé" in ligne["libelle"],
           "le libellé porte l'avertissement", results)
    _check(ligne is not None and not ligne["atelier"],
           "la colonne Link reste vide (pas de lien mort)", results)


def _test_filtre_masque_rapprochement(asset, results):
    print("\n[8] Un filtre masque le rapprochement")
    filtres = dict(FILTRES_MOIS, equipement=asset)
    rows = _rows(filtres)
    _check(_ligne(rows, "Grand Livre (compte 615)") is None,
           "le rapprochement chiffré disparaît quand un filtre est actif",
           results)
    _check(_ligne(rows, "Rapprochement masqué") is not None,
           "et le rapport explique pourquoi", results)


def _test_periode_future(results):
    print("\n[9] Une période future le dit, sans cacher le préventif")
    futur = add_days(getdate(today()), 400)
    rows = _rows({"periode": "Mois", "date": str(futur)})
    _check(rows and rows[0]["section"] == "INFO",
           "une ligne INFO en tête, aucun chiffre inventé", results)
    _check(not any(r["section"] == "Réalisées" for r in rows),
           "aucune intervention réalisée annoncée sur un mois à venir", results)
    _check(not any(r["section"] == "Rapprochement" for r in rows),
           "aucun rapprochement sur un mois à venir", results)
    # Le préventif est « à ce jour » : le masquer cacherait les retards au
    # moment précis où l'on prépare le planning des mois suivants.
    _check(any(r["section"].startswith("Préventif") for r in rows),
           "le bloc préventif reste visible", results)


def _test_preventif_respecte_le_filtre(asset, results):
    print("\n[10] Le bloc préventif respecte le filtre Équipement")
    autre = _asset_test(f"{PREFIXE_ASSET} second")
    # Périodicité hebdomadaire : l'échéance tombe dans les 30 jours de
    # l'horizon, sinon la tâche ne remonterait pas et le test ne prouverait rien.
    planifier_maintenance(asset, [
        {"tache": "ZZTEST Preventif A", "periodicite": "Weekly",
         "date_debut": str(today())}])
    planifier_maintenance(autre, [
        {"tache": "ZZTEST Preventif B", "periodicite": "Weekly",
         "date_debut": str(today())}])

    # Sans filtre, les DEUX doivent apparaître — sinon le test qui suit
    # passerait pour une mauvaise raison (rien à filtrer).
    tous = _rows()
    _check(_ligne(tous, "ZZTEST Preventif A") is not None
           and _ligne(tous, "ZZTEST Preventif B") is not None,
           "sans filtre, les deux tâches préventives remontent", results)

    filtre = _rows(dict(FILTRES_MOIS, equipement=asset))
    _check(_ligne(filtre, "ZZTEST Preventif A") is not None,
           "avec filtre, la tâche de l'équipement filtré reste", results)
    _check(_ligne(filtre, "ZZTEST Preventif B") is None,
           "avec filtre, la tâche de l'AUTRE équipement disparaît", results)


def run():
    print("\n" + "=" * 70)
    print("  SCRUM-11 — Rapport Interventions")
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

    asset = _asset_test(f"{PREFIXE_ASSET} principal")

    _test_structure(results)
    _test_mois_vide_affiche_zero(results)
    _test_ligne_et_total(asset, results)
    _test_brouillon_exclu(asset, results)
    _test_rapprochement_sans_ecart(results)
    _test_rapprochement_avec_ecart(results)
    _test_equipement_sorti(results)
    _test_atelier_absent(asset, results)
    _test_filtre_masque_rapprochement(asset, results)
    _test_periode_future(results)
    _test_preventif_respecte_le_filtre(asset, results)
    _test_periode_en_cours_annoncee(results)

    print("\n" + "-" * 70)
    print(f"  {results['pass']} OK / {results['fail']} FAIL")
    print("-" * 70)
    return results
