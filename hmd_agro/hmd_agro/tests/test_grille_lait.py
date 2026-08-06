"""
FIN-S24 / FIN-S25 — tests du prix du lait et de l'écart lait valorisé
(RG-FIN-10/13, RC-FIN-13/14).

Les deux sujets partagent le même moteur : l'écart lait est valorisé au prix
du litre de la période, donc à la grille qualité.

Couvre :
  1. Garde-fous de la grille : ERR-GRL-01/02/03/04/05
  2. `prix_du_litre` : paliers TB/TP, repli linéaire quand un critère n'a pas
     de palier, plafond de prime et plancher de prix
  3. `grille_active` : résolution par date, grille expirée ignorée
  4. `compute_milk_rate` : grille prioritaire, repli prix plat documenté
  5. `Bilan Lait Journalier` calcule son écart quelle que soit la source
  6. `ecart_lait` : litres perdus, valorisation, %, écart négatif non valorisé
  7. FIN-B1 : palier VOLUME (bonus quantité, bornes en litres/mois) ;
     immutabilité de la grille référencée par un décompte figé (ERR-GRL-06,
     suppression ERR-GRL-07), clôture par date_fin toujours permise

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_grille_lait.run
"""
import traceback

import frappe

from hmd_agro.hmd_agro.doctype.grille_prix_lait.grille_prix_lait import grille_active
from hmd_agro.hmd_agro.utils import finance_kpis
from hmd_agro.hmd_agro.utils.facturation_lait import compute_milk_rate

PREFIXE = "ZZTEST Grille"
# Fenêtres hors de toute donnée réelle : la grille de test vit en 2034, les
# bilans lait de test en 2033 (aucune grille ne les couvre par elle-même).
DEBUT_GRILLE = "2034-01-01"
FIN_GRILLE = "2034-12-31"
BLJ_DEBUT = "2033-05-01"
BLJ_FIN = "2033-05-05"
SANS_GRILLE = "2019-06-30"


# Grilles de production suspendues le temps du test (une grille ouverte
# couvre 2034 et empêcherait la grille de test d'être active — RG-FIN-13).
_SUSPENDUES = []


def _suspendre_grilles_reelles():
    _SUSPENDUES.clear()
    for name in frappe.get_all("Grille Prix Lait",
                               filters={"active": 1,
                                        "nom_grille": ["not like", f"{PREFIXE}%"]},
                               pluck="name"):
        _SUSPENDUES.append(name)
        frappe.db.set_value("Grille Prix Lait", name, "active", 0,
                            update_modified=False)
    frappe.db.commit()


def _restaurer_grilles_reelles():
    for name in _SUSPENDUES:
        frappe.db.set_value("Grille Prix Lait", name, "active", 1,
                            update_modified=False)
    _SUSPENDUES.clear()
    frappe.db.commit()


def _cleanup():
    # Les décomptes figés d'abord : une grille référencée refuse sa
    # suppression (ERR-GRL-07). Hard delete SQL — docstatus 1 ne s'efface pas
    # par l'API (même pattern que les Sales Invoice de test_recettes).
    if frappe.db.table_exists("Decompte Lait Mensuel"):
        frappe.db.sql("""DELETE FROM `tabDecompte Lait Mensuel`
                         WHERE periode_debut BETWEEN '2034-01-01' AND '2034-12-31'""")
    for name in frappe.get_all("Grille Prix Lait",
                               filters={"nom_grille": ["like", f"{PREFIXE}%"]},
                               pluck="name"):
        frappe.delete_doc("Grille Prix Lait", name, force=True, ignore_permissions=True)
    frappe.db.sql("DELETE FROM `tabBilan Lait Journalier` WHERE date BETWEEN %s AND %s",
                  (BLJ_DEBUT, BLJ_FIN))
    frappe.db.commit()
    _restaurer_grilles_reelles()


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


def _grille(suffixe, paliers=None, **kwargs):
    payload = {
        "doctype": "Grille Prix Lait",
        "nom_grille": f"{PREFIXE} {suffixe}",
        "statut": "VALIDEE",
        "active": 0,
        "date_debut": DEBUT_GRILLE,
        "date_fin": FIN_GRILLE,
        "prix_base": 1.500,
        "tb_reference": 3.8,
        "tp_reference": 3.2,
        "paliers": paliers or [],
    }
    payload.update(kwargs)
    return frappe.get_doc(payload).insert(ignore_permissions=True)


def _blj(date, production, vendu, ci=0, veau=0, tb=None, tp=None):
    return frappe.get_doc({
        "doctype": "Bilan Lait Journalier", "date": date,
        "production_totale_saisie": production, "lait_vendu": vendu,
        "consommation_interne": ci, "lait_veau": veau,
        "taux_tb_moyen": tb or 0, "taux_tp_moyen": tp or 0,
    }).insert(ignore_permissions=True)


def run():
    print("\n" + "=" * 70)
    print("  FIN-S24/S25 — Grille de prix qualité & écart lait valorisé")
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
    _suspendre_grilles_reelles()

    # ── 1. Garde-fous
    _throws(lambda: _grille("Dates", date_debut=FIN_GRILLE, date_fin=DEBUT_GRILLE),
            "ERR-GRL-01", "Fin avant début refusée", results)
    _throws(lambda: _grille("Prix", prix_base=0),
            "ERR-GRL-02", "Prix de base nul refusé", results)
    _throws(lambda: _grille("Bornes", paliers=[
        {"critere": "TB", "borne_min": 4.0, "borne_max": 3.0, "prime": 0.02}]),
        "ERR-GRL-03", "Borne haute ≤ borne basse refusée", results)
    _throws(lambda: _grille("Chevauche", paliers=[
        {"critere": "TB", "borne_min": 3.0, "borne_max": 4.0, "prime": 0.01},
        {"critere": "TB", "borne_min": 3.5, "borne_max": 4.5, "prime": 0.02}]),
        "ERR-GRL-04", "Paliers qui se chevauchent refusés", results)

    # ── 2. Moteur de prix
    grille = _grille("Paliers", paliers=[
        {"critere": "TB", "borne_min": 0, "borne_max": 3.5, "prime": -0.050},
        {"critere": "TB", "borne_min": 3.5, "borne_max": 4.0, "prime": 0.020},
        {"critere": "TB", "borne_min": 4.0, "borne_max": None, "prime": 0.060},
    ], prime_tp_par_point=0.010)

    _check(grille.prix_du_litre() == 1.500,
           "Sans donnée qualité → prix de base (1.500)", results)
    _check(grille.prix_du_litre(tb=3.2) == 1.450,
           "TB 3.2 → pénalité de palier (1.450)", results)
    _check(grille.prix_du_litre(tb=3.7) == 1.520,
           "TB 3.7 → prime de palier (1.520)", results)
    _check(grille.prix_du_litre(tb=4.5) == 1.560,
           "TB 4.5 → palier ouvert vers le haut (1.560)", results)
    _check(grille.prix_du_litre(tb=4.0) == 1.560,
           "Borne basse incluse : TB 4.0 relève du palier supérieur", results)
    # TP n'a aucun palier → repli sur l'indexation linéaire
    _check(abs(grille.prix_du_litre(tp=3.7) - 1.505) < 0.0005,
           "TP sans palier → indexation linéaire (0.5 pt × 0.010)", results)

    detail = grille.prix_du_litre(tb=4.5, tp=3.7, detail=True)
    _check(detail["primes"]["TB"] == 0.06 and abs(detail["primes"]["TP"] - 0.005) < 0.0005,
           "Le détail expose la prime de chaque critère", results)
    _check(detail["grille"] == grille.name and detail["statut"] == "VALIDEE",
           "Le détail trace la grille et son statut", results)

    grille.plafond_prime = 0.030
    grille.save(ignore_permissions=True)
    _check(grille.prix_du_litre(tb=4.5) == 1.530,
           "Plafond de prime appliqué (1.530)", results)
    grille.plafond_prime = 0
    grille.plancher_prix = 1.480
    grille.save(ignore_permissions=True)
    _check(grille.prix_du_litre(tb=3.2) == 1.480,
           "Plancher de prix appliqué malgré la pénalité (1.480)", results)

    # ── 3. Résolution par date + unicité
    grille.active = 1
    grille.save(ignore_permissions=True)
    active = grille_active("2034-06-15")
    _check(active and active.name == grille.name,
           "grille_active résout la grille en vigueur à la date", results)
    _check(grille_active("2035-06-15") is None or
           grille_active("2035-06-15").name != grille.name,
           "Une grille expirée ne s'applique plus", results)
    _throws(lambda: _grille("Concurrente", active=1),
            "ERR-GRL-05", "Deux grilles actives sur la même période refusées", results)

    # ── 4. compute_milk_rate
    _check(compute_milk_rate(tb_moyen=4.5, date="2034-06-15") == 1.560,
           "compute_milk_rate applique la grille de la date", results)
    plat = compute_milk_rate(tb_moyen=4.5, date=SANS_GRILLE, detail=True)
    _check(plat["grille"] is None and plat["statut"] == "PRIX_PLAT",
           f"Aucune grille à cette date → repli prix plat ({plat['prix']})", results)

    # ── 5/6. Écart lait valorisé
    _blj(BLJ_DEBUT, production=1000, vendu=900, ci=30, veau=40)
    blj = frappe.get_doc("Bilan Lait Journalier", {"date": BLJ_DEBUT})
    _check(abs(blj.ecart_litres - 30) < 0.01,
           f"Écart calculé à l'enregistrement du bilan ({blj.ecart_litres} L)", results)

    _blj("2033-05-02", production=1000, vendu=950, ci=20, veau=20)   # écart 10
    _blj("2033-05-03", production=1000, vendu=990, ci=10, veau=10)   # écart −10
    frappe.db.commit()

    ec = finance_kpis.ecart_lait(BLJ_DEBUT, BLJ_FIN, prix_litre=1.5)
    _check(abs(ec["litres_perdus"] - 40) < 0.01,
           f"Litres perdus = 30 + 10 (écart négatif exclu) → {ec['litres_perdus']}",
           results)
    _check(abs(ec["litres"] - 30) < 0.01,
           "Écart net = 30 L (les 10 L négatifs se compensent)", results)
    _check(abs(ec["litres_negatifs"] - 10) < 0.01,
           "Les écarts négatifs sont comptés à part (erreur de saisie)", results)
    _check(abs(ec["valeur"] - 60) < 0.01,
           f"Valorisation = 40 L × 1.5 = {ec['valeur']} TND", results)
    _check(abs(ec["pct_production"] - 40 / 3000 * 100) < 0.01,
           f"Part de la production = {ec['pct_production']} %", results)
    _check(ec["jours"] == 3 and abs(ec["production"] - 3000) < 0.01,
           "Production et nombre de jours cohérents", results)

    auto = finance_kpis.ecart_lait(BLJ_DEBUT, BLJ_FIN)
    _check(auto["prix_litre"] > 0 and auto["valeur"] > 0,
           f"Sans prix fourni, l'écart est valorisé au prix du litre "
           f"({auto['prix_litre']} TND/L)", results)

    vide = finance_kpis.ecart_lait("2038-01-01", "2038-01-31")
    _check(vide["litres_perdus"] == 0 and vide["valeur"] == 0,
           "Période sans bilan lait → 0 honnête", results)

    # ── 7. FIN-B1 — palier VOLUME (bonus quantité) + immutabilité
    grille_vol = _grille("Volume", paliers=[
        {"critere": "VOLUME", "borne_min": 0, "borne_max": 10000, "prime": 0},
        {"critere": "VOLUME", "borne_min": 10000, "borne_max": None, "prime": 0.020},
    ])
    _check(grille_vol.prix_du_litre(volume=12000) == 1.520,
           "VOLUME ≥ 10000 L/mois → bonus quantité (1.520)", results)
    _check(grille_vol.prix_du_litre(volume=5000) == 1.500,
           "VOLUME sous le seuil → prix de base (1.500)", results)
    _check(grille_vol.prix_du_litre() == 1.500,
           "Sans volume fourni → aucun bonus quantité", results)

    # Un décompte figé référence la grille → ses champs de prix se figent.
    dlm = frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": "2034-02-01", "periode_fin": "2034-02-28",
        "volume_litres": 12000, "grille": grille_vol.name,
        "prix_base": 1.500, "prime_quantite": 0.020,
    }).insert(ignore_permissions=True)
    dlm.submit()
    frappe.db.commit()

    def _modifier_prix():
        doc = frappe.get_doc("Grille Prix Lait", grille_vol.name)
        doc.prix_base = 1.700
        doc.save(ignore_permissions=True)

    def _modifier_paliers():
        doc = frappe.get_doc("Grille Prix Lait", grille_vol.name)
        doc.paliers[1].prime = 0.050
        doc.save(ignore_permissions=True)

    _throws(_modifier_prix, "ERR-GRL-06",
            "Grille référencée par un décompte figé : prix_base gelé", results)
    _throws(_modifier_paliers, "ERR-GRL-06",
            "Grille référencée par un décompte figé : paliers gelés", results)
    _throws(lambda: frappe.delete_doc("Grille Prix Lait", grille_vol.name,
                                      ignore_permissions=True),
            "ERR-GRL-07",
            "Grille référencée par un décompte figé : suppression refusée", results)
    try:
        doc = frappe.get_doc("Grille Prix Lait", grille_vol.name)
        doc.date_fin = "2034-06-30"
        doc.save(ignore_permissions=True)
        _check(True, "Clôturer la grille (date_fin) reste permis — "
                     "versionnement par dates", results)
    except Exception as exc:
        _check(False, f"Clôture par date_fin refusée à tort : {exc}", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
