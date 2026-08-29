"""
SCRUM-11 — tests du Rapport Interventions.

Couvre :
  1. Structure : les 14 colonnes typées, les 4 sections présentes, le parc
     en tête
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
  9. Une période entièrement future le dit, sans cacher le parc ni le préventif
 10. Le bloc préventif respecte le filtre Équipement
 11. Pièces / main-d'œuvre remontent en colonnes, et `cout` en est la somme
 12. Intervenant : prestataire → raison sociale ; salarié → « Interne — nom » ;
     aucun → « Interne »
 13. Parc : PRÊT, EN PANNE (fiche Pending brouillon), EN ATTENTE DE MAINTENANCE
     (fiche Planned dans l'horizon) ; la fiche Planned est « À VENIR » dans le
     préventif et ABSENTE des réalisées ; ligne de synthèse ; échéance dépassée

Fixtures isolées sur mai 2025, préfixe ZZTEST_RINT. Le choix du mois n'est pas
libre : il doit tomber dans un exercice comptable ACTIF (sans quoi le submit
d'une écriture lève FiscalYearError) tout en restant vierge de données réelles.

Pré-requis site : socle comptable (dont le fournisseur « Fournisseur Divers »)
+ setup.finance.maintenance.

Run: bench --site hmd.agro execute \
        hmd_agro.hmd_agro.tests.test_rapport_interventions.run
"""
import traceback

import frappe
from frappe.utils import add_days, getdate, today

from hmd_agro.hmd_agro.report.rapport_interventions.rapport_interventions import (
    COLUMNS, SECTION_PARC, execute,
)
from hmd_agro.hmd_agro.utils.maintenance_utils import (
    FOURNISSEUR_DEFAUT, HEURE_DEBUT_INTERVENTION, HEURE_FIN_INTERVENTION,
    STATUT_EN_ATTENTE, STATUT_PLANIFIEE, STATUT_TERMINEE,
    enregistrer_intervention, planifier_maintenance,
)

COMPANY = "hmd-agro"
ITEM_TEST = "ZZTEST-EQUIP-RINT"
PREFIXE_REF = "ZZTEST_RINT"
PREFIXE_ASSET = "ZZTEST Interv"
PREFIXE_PERSONNEL = "ZZTEST RINT"

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
        _purger_ecriture(je)
    assets = frappe.get_all(
        "Asset", filters={"asset_name": ["like", f"{PREFIXE_ASSET}%"]},
        pluck="name")
    # Par référence (fiches créées par `enregistrer_intervention`) ET par
    # équipement (fiches saisies « à l'écran », sans référence HMD).
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
            _purger_ecriture(je)
        frappe.db.sql("DELETE FROM `tabAsset Repair` WHERE name=%s", repair)
    for asset in assets:
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Log` WHERE asset_name=%s",
                      asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance Task` WHERE parent=%s",
                      asset)
        frappe.db.sql("DELETE FROM `tabAsset Maintenance` WHERE name=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset Activity` WHERE asset=%s", asset)
        frappe.db.sql("DELETE FROM `tabAsset` WHERE name=%s", asset)
    for pers in frappe.get_all(
            "Personnel", filters={"nom_complet": ["like", f"{PREFIXE_PERSONNEL}%"]},
            pluck="name"):
        frappe.delete_doc("Personnel", pers, force=True, ignore_permissions=True)
    frappe.db.commit()


def _purger_ecriture(je):
    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", je)
    frappe.db.sql("DELETE FROM `tabJournal Entry Account` WHERE parent=%s", je)
    frappe.db.sql("DELETE FROM `tabJournal Entry` WHERE name=%s", je)


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


def _fiche(asset, description, statut=STATUT_TERMINEE, date=INTERV_DATE,
           reference=None, **champs):
    """Une fiche saisie « à l'écran » (sans écriture 615), insérée, non soumise."""
    doc = frappe.get_doc({
        "doctype": "Asset Repair", "company": COMPANY, "asset": asset,
        "failure_date": f"{date} {HEURE_DEBUT_INTERVENTION}",
        "completion_date": (f"{date} {HEURE_FIN_INTERVENTION}"
                            if statut == STATUT_TERMINEE else None),
        "repair_status": statut, "description": description,
        "cost_center": f"Lait - {_abbr()}", "reference_hmd": reference,
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


def _premiere(rows, libelle_contient):
    return next((r for r in rows if r["libelle"]
                 and libelle_contient in r["libelle"]), None)


def _ligne(rows, libelle_contient):
    """First row outside the Parc section whose libelle contains the text.

    The Parc section (first in the report) repeats the last intervention's
    description and the next due task in its own libelle, so a raw substring
    lookup would hit the equipment row instead of the intervention row.
    """
    return _premiere([r for r in rows if r["section"] != SECTION_PARC],
                     libelle_contient)


def _ligne_equipement(rows, asset):
    return next((r for r in rows if r["equipement"] == asset), None)


def _ecart(rows):
    ligne = _ligne(rows, "Écart —")
    return ligne["cout"] if ligne else None


def _synthese(rows):
    return _premiere(_section(rows, SECTION_PARC), "équipement(s) ·")


# ─── Tests ───

def _test_structure(results):
    print("\n[1] Structure")
    rows = _rows()
    attendus = ["section", "date", "equipement", "designation", "type",
                "libelle", "atelier", "intervenant", "pieces", "main_oeuvre",
                "cout", "heures", "nb_interventions", "nb_equipements"]
    _check([c["fieldname"] for c in COLUMNS] == attendus,
           "les 14 colonnes attendues, dans l'ordre", results)
    types = {c["fieldname"]: c["fieldtype"] for c in COLUMNS}
    _check(types.get("nb_interventions") == "Int"
           and types.get("nb_equipements") == "Int",
           "les deux compteurs sont des entiers (triables, exportables)",
           results)
    _check(types.get("pieces") == "Currency" and types.get("main_oeuvre") == "Currency"
           and types.get("heures") == "Float",
           "pièces et M.O. sont des montants, les heures un Float", results)
    # Un salarié OU un prestataire : un Link ne saurait pointer vers les deux.
    _check(types.get("intervenant") == "Data",
           "l'intervenant est un texte (salarié ou prestataire)", results)
    _check(rows and rows[0]["section"] == SECTION_PARC,
           "le parc ouvre le rapport", results)
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
        # Un coût saisi en bloc n'est pas ventilé : pièces et M.O. restent
        # vides (un tiret), pas « 0 » — on n'affirme pas ce qu'on ne sait pas.
        _check(ligne["pieces"] is None and ligne["main_oeuvre"] is None,
               "sans ventilation, pièces et M.O. restent vides", results)
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
    _check(_ligne_equipement(_section(rows, SECTION_PARC), asset) is None,
           "mais l'équipement REBUT ne fait plus partie du parc", results)
    return asset


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
    print("\n[9] Une période future le dit, sans cacher le parc ni le préventif")
    futur = add_days(getdate(today()), 400)
    rows = _rows({"periode": "Mois", "date": str(futur)})
    _check(_ligne(rows, "Pas encore d'intervention") is not None,
           "une ligne INFO l'annonce, aucun chiffre inventé", results)
    _check(not any(r["section"] == "Réalisées" for r in rows),
           "aucune intervention réalisée annoncée sur un mois à venir", results)
    _check(not any(r["section"] == "Rapprochement" for r in rows),
           "aucun rapprochement sur un mois à venir", results)
    # Le parc et le préventif sont « à ce jour » : les masquer cacherait les
    # retards au moment précis où l'on prépare le planning des mois suivants.
    _check(rows and rows[0]["section"] == SECTION_PARC,
           "le parc reste en tête", results)
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
    tache = _ligne(tous, "ZZTEST Preventif A")
    _check(tache is not None and tache["type"] == "PLANIFIÉE"
           and tache["designation"] == f"{PREFIXE_ASSET} principal",
           "une tâche ERPNext se lit PLANIFIÉE, avec la désignation de "
           "l'équipement", results)

    filtre = _rows(dict(FILTRES_MOIS, equipement=asset))
    _check(_ligne(filtre, "ZZTEST Preventif A") is not None,
           "avec filtre, la tâche de l'équipement filtré reste", results)
    _check(_ligne(filtre, "ZZTEST Preventif B") is None,
           "avec filtre, la tâche de l'AUTRE équipement disparaît", results)


def _test_pieces_main_oeuvre(asset, results):
    print("\n[11] Pièces et main-d'œuvre remontent, le coût en est la somme")
    avant = _ligne(_rows(), "TOTAL —")
    _fiche(asset, "ZZTEST Courroie + pose", cout_pieces=200, cout_main_oeuvre=50,
           reference=f"{PREFIXE_REF}_PMO").submit()
    rows = _rows()
    ligne = _ligne(rows, "ZZTEST Courroie + pose")
    _check(ligne is not None and ligne["pieces"] == 200
           and ligne["main_oeuvre"] == 50,
           "pièces (200) et M.O. (50) remontent en colonnes", results)
    _check(ligne is not None and ligne["cout"] == 250,
           "le coût de la ligne = pièces + M.O. (250)", results)
    total = _ligne(rows, "TOTAL —")
    _check(total is not None and total["pieces"] == 200
           and total["main_oeuvre"] == 50
           and round(total["cout"] - avant["cout"], 2) == 250,
           "le TOTAL cumule pièces, M.O. et coût", results)


def _test_intervenant(asset, results):
    print("\n[12] L'intervenant : prestataire, salarié, ou personne")
    if not frappe.db.exists("Supplier", FOURNISSEUR_DEFAUT):
        _check(False, f"prérequis absent : fournisseur « {FOURNISSEUR_DEFAUT} » "
                      "(socle comptable)", results)
        return
    pers = _personnel_test()
    _fiche(asset, "ZZTEST Intervenant salarié", personnel=pers.name,
           reference=f"{PREFIXE_REF}_PERS").submit()
    _fiche(asset, "ZZTEST Intervenant prestataire", prestataire=FOURNISSEUR_DEFAUT,
           reference=f"{PREFIXE_REF}_PRESTA").submit()
    rows = _rows()
    salarie = _ligne(rows, "ZZTEST Intervenant salarié")
    _check(salarie is not None
           and salarie["intervenant"] == f"Interne — {pers.nom_complet}",
           "salarié → « Interne — nom complet »", results)
    presta = _ligne(rows, "ZZTEST Intervenant prestataire")
    raison_sociale = frappe.db.get_value("Supplier", FOURNISSEUR_DEFAUT,
                                         "supplier_name")
    _check(presta is not None and presta["intervenant"] == raison_sociale,
           "prestataire → raison sociale du fournisseur", results)
    aucun = _ligne(rows, "ZZTEST Vidange moteur")
    _check(aucun is not None and aucun["intervenant"] == "Interne",
           "aucun intervenant → « Interne »", results)


def _test_parc(asset, results):
    print("\n[13] Parc — état du matériel")
    pret = _asset_test(f"{PREFIXE_ASSET} parc prêt")
    panne = _asset_test(f"{PREFIXE_ASSET} parc panne")
    attente = _asset_test(f"{PREFIXE_ASSET} parc attente")
    # La panne est une fiche Pending OUVERTE : c'est elle qui fait foi.
    _fiche(panne, "ZZTEST Panne hydraulique", statut=STATUT_EN_ATTENTE,
           date=str(today()), reference=f"{PREFIXE_REF}_PANNE")
    # Une fiche « À venir » à 10 jours : dans l'horizon (30 j) → en attente.
    date_prevue = add_days(today(), 10)
    planifiee = _fiche(attente, "ZZTEST Graissage planifié",
                       statut=STATUT_PLANIFIEE, date=date_prevue,
                       reference=f"{PREFIXE_REF}_PLAN")

    rows = _rows()
    parc = _section(rows, SECTION_PARC)
    ligne_pret = _ligne_equipement(parc, pret)
    _check(ligne_pret is not None and ligne_pret["type"] == "PRÊT"
           and ligne_pret["indicator"] == "Green"
           and ligne_pret["libelle"] == "Aucune intervention terminée"
           and ligne_pret["date"] is None,
           "sans fiche ni échéance : PRÊT (vert), aucune intervention", results)
    ligne_panne = _ligne_equipement(parc, panne)
    _check(ligne_panne is not None and ligne_panne["type"] == "EN PANNE"
           and ligne_panne["indicator"] == "Red",
           "fiche Pending ouverte : EN PANNE (rouge)", results)
    _check(frappe.db.get_value("Asset", panne, "status") == "Out of Order",
           "et ERPNext a passé l'équipement « Out of Order »", results)
    ligne_attente = _ligne_equipement(parc, attente)
    _check(ligne_attente is not None
           and ligne_attente["type"] == "EN ATTENTE DE MAINTENANCE"
           and ligne_attente["indicator"] == "Orange",
           "fiche Planned à 10 j : EN ATTENTE DE MAINTENANCE (orange)", results)
    _check(ligne_attente is not None
           and getdate(ligne_attente["date"]) == getdate(date_prevue)
           and "Prochaine : ZZTEST Graissage planifié" in ligne_attente["libelle"]
           and "EN RETARD" not in ligne_attente["libelle"],
           "la prochaine échéance est datée et nommée, sans retard", results)
    principal = _ligne_equipement(parc, asset)
    _check(principal is not None
           and principal["libelle"].startswith("Dernière : 10/05/2025 — ZZTEST"),
           "la dernière intervention terminée est datée et nommée", results)

    # La fiche Planned est une échéance, pas une intervention réalisée.
    prev = _ligne(_section(rows, "Préventif"), "ZZTEST Graissage planifié")
    _check(prev is not None and prev["type"] == "À VENIR"
           and prev["indicator"] == "Blue" and prev["equipement"] == attente,
           "la fiche Planned est « À VENIR » (bleu) dans le préventif", results)
    mois_courant = _rows({"periode": "Mois", "date": str(today())})
    _check(_ligne(_section(rows, "Réalisées"), "ZZTEST Graissage planifié") is None
           and _ligne(_section(mois_courant, "Réalisées"),
                      "ZZTEST Graissage planifié") is None,
           "et absente des réalisées", results)

    # Synthèse : sur un seul équipement, les compteurs sont déterministes.
    synthese = _synthese(_rows(dict(FILTRES_MOIS, equipement=panne)))
    _check(synthese is not None and synthese["libelle"]
           == "1 équipement(s) · 0 prêt(s) · 0 en attente · 1 en panne · "
              "0 échéance(s) dépassée(s)"
           and synthese["nb_equipements"] == 1 and synthese["indicator"] == "Red",
           "la synthèse compte 1 équipement en panne", results)
    synthese_tous = _synthese(rows)
    _check(synthese_tous is not None
           and synthese_tous["nb_equipements"] == len(parc) - 1
           and synthese_tous["libelle"].startswith(f"{len(parc) - 1} équipement(s)"),
           "sans filtre, la synthèse compte toutes les lignes du parc", results)

    # Le temps passe : l'échéance planifiée est dépassée.
    frappe.db.set_value("Asset Repair", planifiee.name, "failure_date",
                        f"{add_days(today(), -3)} {HEURE_DEBUT_INTERVENTION}")
    frappe.db.commit()
    rows = _rows(dict(FILTRES_MOIS, equipement=attente))
    ligne_attente = _ligne_equipement(_section(rows, SECTION_PARC), attente)
    _check(ligne_attente is not None
           and ligne_attente["type"] == "EN ATTENTE DE MAINTENANCE"
           and ligne_attente["libelle"].endswith("EN RETARD"),
           "échéance dépassée : toujours en attente, libellé « EN RETARD »",
           results)
    synthese = _synthese(rows)
    _check(synthese is not None and "1 échéance(s) dépassée(s)" in synthese["libelle"],
           "la synthèse compte l'échéance dépassée", results)
    prev = _ligne(_section(rows, "Préventif"), "ZZTEST Graissage planifié")
    _check(prev is not None and prev["type"] == "EN RETARD"
           and prev["indicator"] == "Red",
           "le préventif la lit « EN RETARD » (rouge)", results)


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
    _test_pieces_main_oeuvre(asset, results)
    _test_intervenant(asset, results)
    # Le parc AVANT le préventif : [10] pose une tâche hebdomadaire sur
    # l'équipement principal, qui passerait alors « en attente ».
    _test_parc(asset, results)
    _test_preventif_respecte_le_filtre(asset, results)
    _test_periode_en_cours_annoncee(results)

    print("\n" + "-" * 70)
    print(f"  {results['pass']} OK / {results['fail']} FAIL")
    print("-" * 70)
    return results
