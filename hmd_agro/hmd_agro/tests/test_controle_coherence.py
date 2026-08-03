"""
FIN-S70 — tests du contrôle de cohérence finance (RG-FIN-70).

Le rapport est l'outil de validation sur données réelles : il doit tourner
sur n'importe quelle base sans exploser, et surtout **détecter** ce qu'il
prétend détecter. On lui injecte donc de vraies anomalies et on vérifie
qu'il les remonte.

Couvre :
  1. Exécution : structure des lignes, statuts admis, ligne de synthèse
  2. Période vierge (aucune écriture) → alerte, pas de plantage
  3. Anomalie injectée : écart lait négatif (sur-affectation) → ERREUR
  4. Anomalie injectée : animal vendu avec un prix mais sans facture → ERREUR
  5. La synthèse et `run()` comptent la même chose

Run: bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.tests.test_controle_coherence.run
"""
import traceback

import frappe
from frappe.utils import add_months, get_first_day, get_last_day, today

from hmd_agro.hmd_agro.report.controle_coherence_finance import (
    controle_coherence_finance as ctl,
)

PREFIXE_TN = "8895000"
MERE_TEST = "zztest_mere_controle"
BLJ_TEST = "2036-04-10"


def _cleanup():
    animaux = frappe.get_all(
        "Animal", filters={"identification_tn": ["like", f"{PREFIXE_TN}%"]},
        fields=["name", "id_lot"])
    lots = {a.id_lot for a in animaux if a.id_lot}
    for animal in [a.name for a in animaux]:
        for si in frappe.get_all(
                "Sales Invoice",
                filters={"remarks": ["like", f"%ANIMAL_VENTE_{animal}%"]}, pluck="name"):
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no=%s", si)
            frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no=%s", si)
            frappe.db.sql("DELETE FROM `tabSales Invoice Item` WHERE parent=%s", si)
            frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE name=%s", si)
        frappe.db.sql("DELETE FROM `tabAllotement History` WHERE animal=%s", animal)
        frappe.db.sql("DELETE FROM `tabAnimal` WHERE name=%s", animal)
    frappe.db.sql("DELETE FROM `tabMere externe` WHERE name=%s", MERE_TEST)
    frappe.db.sql("DELETE FROM `tabBilan Lait Journalier` WHERE date=%s", BLJ_TEST)
    frappe.db.commit()
    # Suppressions en SQL direct → `Animal.on_trash` ne tourne pas : on
    # recompte les lots pour ne pas laisser un effectif fantôme derrière nous.
    from hmd_agro.hmd_agro.doctype.lot.lot import update_lot_animal_count

    for lot in {l for l in lots if l}:
        update_lot_animal_count(lot)
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _ligne(data, fragment):
    return next((d for d in data if fragment.lower() in d["controle"].lower()), None)


def _animal_vendu_sans_facture():
    """Sortie valorisée dont la facture manque — exactement le trou que le
    contrôle doit voir. Le prix est posé APRÈS la sortie, en base, pour
    court-circuiter la facturation automatique (RG-FIN-20)."""
    if not frappe.db.exists("Mere externe", MERE_TEST):
        frappe.get_doc({"doctype": "Mere externe", "nom_mere": MERE_TEST,
                        "race": "Montbéliarde"}).insert(ignore_permissions=True)
    doc = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": f"{PREFIXE_TN}001",
        "categorie": "VACHE", "sexe": "F",
        "date_naissance": str(add_months(today(), -60)),
        "est_achat": 1, "prix_achat": 3000, "date_entree": str(add_months(today(), -50)),
        "id_mere_externe": MERE_TEST,
        "id_pere": frappe.db.get_value("Taureau", {}, "name"),
        "id_lot": frappe.db.get_value("Lot", {"actif": 1}, "name"),
        "statut": "ACTIF",
    })
    doc.insert(ignore_permissions=True)
    doc.statut = "VENDU"
    doc.date_sortie = str(today())
    doc.flags.ignore_validate = True
    doc.save(ignore_permissions=True)
    frappe.db.set_value("Animal", doc.name, "prix_vente", 2800, update_modified=False)
    frappe.db.commit()
    return doc.name


def run():
    print("\n" + "=" * 70)
    print("  FIN-S70 — Contrôle de cohérence finance")
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

    debut, fin = str(get_first_day(today())), str(get_last_day(today()))

    # ── 1. Structure
    columns, data = ctl.execute({"date_debut": debut, "date_fin": fin})
    _check(len(columns) == 5 and columns[0]["fieldname"] == "domaine",
           "Colonnes du rapport conformes", results)
    _check(len(data) >= 20, f"{len(data)} lignes de contrôle produites", results)
    _check(all(set(d) >= {"domaine", "controle", "statut", "valeur", "detail",
                          "indicator"} for d in data),
           "Chaque ligne porte domaine / contrôle / statut / valeur / détail", results)
    _check(all(d["statut"] in (ctl.OK, ctl.ALERTE, ctl.ERREUR) for d in data),
           "Tous les statuts sont OK / ALERTE / ERREUR", results)
    _check(all(d["indicator"] == ctl.INDICATEURS[d["statut"]] for d in data),
           "La couleur suit le statut (vert / orange / rouge)", results)
    _check(data[0]["domaine"] == "SYNTHÈSE",
           "La synthèse ouvre le rapport", results)
    domaines = {d["domaine"] for d in data}
    _check({"Socle", "Grand Livre", "Lait", "Coûts", "Personnel",
            "Immobilisations", "Troupeau"} <= domaines,
           f"Les 7 domaines sont couverts ({len(domaines)} présents)", results)

    # ── 2. Période vierge : le rapport doit rester lisible
    _, vide = ctl.execute({"date_debut": "2039-01-01", "date_fin": "2039-01-31"})
    ecritures = _ligne(vide, "Écritures sur la période")
    _check(ecritures is not None and ecritures["statut"] == ctl.ALERTE,
           "Période sans écriture → alerte explicite, pas d'erreur", results)
    # Sur une période sans donnée, seul le référentiel peut être en erreur
    # (ici : aucun exercice fiscal en 2039) — jamais les données elles-mêmes.
    erreurs_vide = [d for d in vide
                    if d["statut"] == ctl.ERREUR and d["domaine"] != "SYNTHÈSE"]
    _check(all(d["domaine"] == "Socle" for d in erreurs_vide),
           "Aucune erreur de données inventée sur une période vide "
           f"({len(erreurs_vide)} erreur(s), toutes de référentiel)", results)

    # ── 3. Anomalie : écart lait négatif
    frappe.get_doc({
        "doctype": "Bilan Lait Journalier", "date": BLJ_TEST,
        "production_totale_saisie": 500, "lait_vendu": 540,
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    _, avec_ecart = ctl.execute({"date_debut": "2036-04-01", "date_fin": "2036-04-30"})
    negatif = _ligne(avec_ecart, "négatifs")
    _check(negatif is not None and negatif["statut"] == ctl.ERREUR,
           "Sur-affectation du lait détectée comme ERREUR", results)
    _check(negatif and "40" in negatif["valeur"],
           f"Volume sur-affecté chiffré ({negatif['valeur'] if negatif else '—'})",
           results)

    # ── 4. Anomalie : vente non facturée
    animal = _animal_vendu_sans_facture()
    _, avec_vente = ctl.execute({"date_debut": debut, "date_fin": fin})
    ventes = _ligne(avec_vente, "Sorties d'animaux facturées")
    _check(ventes is not None and ventes["statut"] == ctl.ERREUR,
           "Sortie valorisée sans facture détectée comme ERREUR", results)
    _check(ventes and animal in ventes["detail"],
           "L'animal fautif est nommé dans le détail", results)

    synthese = avec_vente[0]
    erreurs = sum(1 for d in avec_vente[1:] if d["statut"] == ctl.ERREUR)
    _check(synthese["statut"] == ctl.ERREUR and f"{erreurs} erreur" in synthese["valeur"],
           f"La synthèse remonte les {erreurs} erreur(s)", results)

    # ── 5. Sortie console
    resume = ctl.run(debut, fin)
    _check(resume["erreurs"] == erreurs and resume["controles"] == len(avec_vente) - 1,
           f"run() compte les mêmes contrôles ({resume['controles']}) "
           f"et erreurs ({resume['erreurs']})", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
