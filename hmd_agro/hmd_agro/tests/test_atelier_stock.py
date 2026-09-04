"""
SCRUM-10 — le centre de coûts des mouvements de stock (RG-FIN-40).

Le trou que ces tests ferment : l'app ne posait AUCUN centre de coûts sur les
Stock Entry qu'elle génère (médicament d'un Traitement, paillette d'une
Insémination, ration d'un lot). ERPNext prenait le centre par défaut de la
société — Frais Généraux — et, depuis la clé de répartition (Cost Center
Allocation, 03/09/2026), une ration de vaches aurait été éclatée entre les
ateliers au lieu d'aller à 100 % au Lait. Décision du 04/09/2026 : l'app pose
le centre elle-même, rien à paramétrer.

Cas :
  1. La règle : VACHE → Lait ; VELLE / VEAU / GENISSE / TAURILLON → Élevage -
     Génisses ; un centre inexistant → None (ERPNext retombe sur le défaut)
  2. Traitement d'une vache → sortie de stock ET écritures comptables sur
     Lait, rien sur Frais Généraux ; suppression → réception de compensation
     sur le MÊME centre (annulation symétrique)
  3. Traitement d'une génisse → Élevage - Génisses
  4. Ration : l'atelier d'un lot ce jour-là est celui de ses animaux —
     lecture des lots réels du site, sans rien écrire
  5. `proposer_cle` : centre Frais Généraux, date après la dernière écriture
     du centre, une ligne par atelier déjà utilisé, jamais Frais Généraux
     dans les lignes

Fixtures préfixées ZZTEST_ATL, datées d'aujourd'hui (exercice actif),
supprimées en fin de test — écritures comptables comprises.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_atelier_stock.run
"""
import traceback

import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.utils.feed_distribution import (
    _ateliers_on_date, _prefetch_population_data,
)
from hmd_agro.hmd_agro.utils.finance_kpis import ATELIER_FRAIS_GENERAUX, _nom_court
from hmd_agro.hmd_agro.utils.repartition_charges import proposer_cle
from hmd_agro.hmd_agro.utils.stock_utils import (
    ATELIER_JEUNES, ATELIER_VACHES, DEFAULT_WAREHOUSE as WAREHOUSE,
    atelier_categorie, cost_center_categorie,
)

PREFIX = "ZZTEST_ATL"
MED = f"{PREFIX}_MED"
ITEM = f"MED-{MED}"


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _cleanup():
    """Raw deletes, like test_stock_integration : the cancel lifecycle would
    re-validate the SLE timeline. Écritures comptables comprises — les tests
    précédents laissaient leurs GL Entry sur le site."""
    pieces = [r[0] for r in frappe.db.sql(
        "SELECT DISTINCT parent FROM `tabStock Entry Detail` WHERE item_code = %s", ITEM)]
    if pieces:
        frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no IN %s", (pieces,))
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent IN %s", (pieces,))
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name IN %s", (pieces,))
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code = %s", ITEM)
    frappe.db.sql("DELETE FROM `tabBin` WHERE item_code = %s", ITEM)
    for (nom,) in frappe.db.sql("SELECT name FROM `tabTraitement` WHERE animal LIKE %s",
                                f"{PREFIX}%"):
        frappe.db.sql("DELETE FROM `tabTraitement Medicale` WHERE parent = %s", nom)
        frappe.db.sql("DELETE FROM `tabTraitement` WHERE name = %s", nom)
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    for table in ("Item Price", ):
        frappe.db.sql(f"DELETE FROM `tab{table}` WHERE item_code = %s", ITEM)
    for table in ("Item Default", "UOM Conversion Detail"):
        frappe.db.sql(f"DELETE FROM `tab{table}` WHERE parent = %s", ITEM)
    frappe.db.sql("DELETE FROM `tabItem` WHERE name = %s", ITEM)
    frappe.db.sql("DELETE FROM `tabMedicament` WHERE name = %s", MED)
    frappe.db.commit()


def _animal(suffixe, categorie):
    animal = frappe.new_doc("Animal")
    animal.update({
        "identification_tn": f"{PREFIX}_{suffixe}", "nom_metier": f"{PREFIX}_{suffixe}",
        "categorie": categorie, "sexe": "F",
        "date_naissance": "2020-01-01" if categorie == "VACHE" else "2025-01-01",
        "statut": "ACTIF",
    })
    animal.flags.ignore_validate = True
    animal.flags.ignore_mandatory = True
    animal.insert(ignore_permissions=True)
    return animal.name


def _medicament():
    frappe.get_doc({
        "doctype": "Medicament", "nom_medicament": MED,
        "type_medicament": "ANTIBIOTIQUE", "delai_attente_lait": 5, "prix_unitaire": 10.0,
    }).insert(ignore_permissions=True)
    se = frappe.get_doc({
        "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
        "company": "hmd-agro", "posting_date": today(),
        "remarks": f"{PREFIX} réception initiale",
        "items": [{"item_code": ITEM, "qty": 10, "uom": "Unit", "stock_uom": "Unit",
                   "conversion_factor": 1, "t_warehouse": WAREHOUSE, "basic_rate": 10.0}],
    })
    se.insert(ignore_permissions=True)
    se.submit()
    frappe.db.commit()


def _traitement(animal):
    trt = frappe.get_doc({
        "doctype": "Traitement", "animal": animal, "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [{"medicament": MED, "dose": 10, "unite_dose": "ml"}],
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()
    return trt.name


def _piece(remark):
    return frappe.db.get_value("Stock Entry", {"remarks": remark, "docstatus": 1}, "name")


def _centre_ligne(piece):
    return frappe.db.get_value("Stock Entry Detail", {"parent": piece}, "cost_center")


def _gl_charges_par_centre(piece):
    """{centre: solde} des écritures de CHARGE de la pièce."""
    rows = frappe.db.sql("""
        SELECT gle.cost_center, SUM(gle.debit - gle.credit)
        FROM `tabGL Entry` gle JOIN `tabAccount` acc ON acc.name = gle.account
        WHERE gle.voucher_no = %s AND gle.is_cancelled = 0 AND acc.root_type = 'Expense'
        GROUP BY gle.cost_center
    """, piece)
    return {cc: round(float(solde), 3) for cc, solde in rows}


# ─── Cas ─────────────────────────────────────────────────────────────────────

def _test_regle(results):
    print("\n── 1. La règle RG-FIN-40 ──")
    _check(atelier_categorie("VACHE") == ATELIER_VACHES, "VACHE → Lait", results)
    for cat in ("VELLE", "VEAU", "GENISSE", "TAURILLON"):
        _check(atelier_categorie(cat) == ATELIER_JEUNES, f"{cat} → Élevage - Génisses", results)
    lait = cost_center_categorie("VACHE")
    _check(lait and _nom_court(lait) == ATELIER_VACHES and frappe.db.exists("Cost Center", lait),
           f"le centre de coûts existe : {lait}", results)
    _check(cost_center_categorie("VACHE", company="ZZ_SOCIETE_INEXISTANTE") is None,
           "socle absent → None (ERPNext retombe sur le centre par défaut)", results)


def _test_traitement(results, categorie, attendu, libelle):
    print(f"\n── {libelle} ──")
    animal = _animal(categorie, categorie)
    trt = _traitement(animal)
    sortie = _piece(f"Traitement {trt}")
    _check(bool(sortie), f"la sortie de stock du traitement existe ({sortie})", results)
    if not sortie:
        return
    centre = _centre_ligne(sortie)
    _check(_nom_court(centre) == attendu, f"ligne de stock sur « {attendu} » (lu : {centre})", results)
    gl = _gl_charges_par_centre(sortie)
    _check(list(gl) == [centre] and gl[centre] > 0,
           f"écritures de charge sur {attendu} uniquement, rien sur Frais Généraux : {gl}", results)
    _check(not any(_nom_court(cc) == ATELIER_FRAIS_GENERAUX for cc in gl),
           "aucune écriture de la pièce sur Frais Généraux", results)

    frappe.delete_doc("Traitement", trt, force=True)
    frappe.db.commit()
    retour = _piece(f"Restore Traitement {trt} delete")
    _check(bool(retour), f"la réception de compensation existe ({retour})", results)
    if retour:
        _check(_centre_ligne(retour) == centre,
               f"compensation sur le MÊME centre ({_nom_court(centre)}) — annulation symétrique",
               results)
        gl_retour = _gl_charges_par_centre(retour)
        _check(list(gl_retour) == [centre] and round(gl_retour[centre] + gl[centre], 3) == 0,
               f"les écritures de charge s'annulent sur {attendu} : {gl_retour}", results)


def _test_rations(results):
    print("\n── 4. L'atelier d'un lot (lots réels, lecture seule) ──")
    jour = getdate(today())
    ateliers = _ateliers_on_date(jour, _prefetch_population_data(jour))
    if not ateliers:
        print("  (aucun lot peuplé aujourd'hui — cas non exécuté)")
        return
    for lot, centre in sorted(ateliers.items()):
        categories = [a.categorie for a in frappe.get_all(
            "Animal", filters={"id_lot": lot, "statut": "ACTIF"}, fields=["categorie"])]
        if not categories:
            continue
        vaches = sum(1 for c in categories if c == "VACHE")
        attendu = ATELIER_VACHES if vaches * 2 > len(categories) else ATELIER_JEUNES
        _check(_nom_court(centre) == attendu,
               f"lot {lot} ({len(categories)} animaux, {vaches} vaches) → {attendu} (lu : {centre})",
               results)
    _check(not any(_nom_court(cc) == ATELIER_FRAIS_GENERAUX for cc in ateliers.values()),
           "aucun lot n'est imputé à Frais Généraux", results)


def _test_proposer_cle(results):
    print("\n── 5. proposer_cle — la clé pré-remplie ──")
    p = proposer_cle()
    _check(p and _nom_court(p["main_cost_center"]) == ATELIER_FRAIS_GENERAUX,
           f"centre principal = Frais Généraux ({p.get('main_cost_center')})", results)
    if not p:
        return
    derniere = frappe.db.get_value(
        "GL Entry", {"cost_center": p["main_cost_center"], "is_cancelled": 0}, "max(posting_date)")
    _check(not derniere or getdate(p["valid_from"]) > getdate(derniere),
           f"date proposée {p['valid_from']} après la dernière écriture ({derniere})", results)
    _check(getdate(p["valid_from"]).day == 1, "date proposée = un 1er du mois", results)
    _check(p["ateliers"] and p["main_cost_center"] not in p["ateliers"],
           f"lignes = ateliers utilisés, sans Frais Généraux : {[_nom_court(a) for a in p['ateliers']]}",
           results)
    _check(all(frappe.db.get_value("Cost Center", a, "is_group") == 0 for a in p["ateliers"]),
           "aucun groupe dans les lignes", results)


# ─── Runner ──────────────────────────────────────────────────────────────────

def run():
    print("\n" + "=" * 70)
    print("  SCRUM-10 — centre de coûts des mouvements de stock (RG-FIN-40)")
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
    _test_regle(results)
    _medicament()
    _test_traitement(results, "VACHE", ATELIER_VACHES, "2. Traitement d'une vache → Lait")
    _test_traitement(results, "GENISSE", ATELIER_JEUNES,
                     "3. Traitement d'une génisse → Élevage - Génisses")
    _test_rations(results)
    _test_proposer_cle(results)
    print("\n" + "-" * 70)
    print(f"  RÉSULTAT : {results['pass']} OK, {results['fail']} FAIL")
    print("-" * 70 + "\n")
    return results
