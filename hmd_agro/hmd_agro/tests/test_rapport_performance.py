"""
Tests — Rapport Performance (Phase 4).

Covers:
  1. Structure : colonnes typées (section / indicateur / valeur / unite),
     les 5 sections présentes, `valeur` numérique (export Excel propre)
  2. Bornes de période : Mois = mois calendaire, Semaine = ISO Lun-Dim
  3. Valeurs : Production Totale (Traite) et Lait Vendu (Bilan Lait
     Journalier) en delta par rapport à la baseline (les totaux cheptel
     incluent les données réelles de la base)

Fixtures isolées sur mars 2019 (période passée, avant tout backfill SLE —
les coûts alimentaires y valent honnêtement 0, ce que le rapport assume).

Run: bench --site <site> execute hmd_agro.hmd_agro.tests.test_rapport_performance.run
"""
import traceback

import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_performance.rapport_performance import (
    execute, period_bounds,
)

PREFIX = "TEST-PERF-"
MOIS_DATE = "2019-03-15"
SEM_DATE = "2019-03-06"        # mercredi → semaine ISO 04/03 - 10/03
BLJ_DATES = ["2019-03-01", "2019-03-02", "2019-03-03"]

_created = []


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _find(rows, section, label_starts):
    return next((r for r in rows if r["section"] == section
                 and r["indicateur"].startswith(label_starts)), None)


# ─── Fixtures ───

def _animal(suffix):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION",
        "etat_gestation": "VIDE", "date_naissance": "2015-01-01",
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    # Velage antérieur à la période pour que la reconstruction la voie VACHE
    vel = frappe.get_doc({
        "doctype": "Velage", "animal": doc.name,
        "date_velage": "2018-06-01", "type_velage": "FACILE",
        "nombre_veaux": "1", "sexe_veau1": "F", "vivant_veau1": 0,
    })
    vel.flags.ignore_validate = True
    vel.flags.ignore_links = True
    vel.db_insert()
    _created.append(("Velage", vel.name))
    return doc.name


def _traite(animal_name, date, litres):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN",
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))


def _seed_blj():
    """One BLJ per date (100 L vendus). A date already carrying a real BLJ is
    skipped — the expected delta counts only what we actually created."""
    created_days = 0
    for d in BLJ_DATES:
        if frappe.db.exists("Bilan Lait Journalier", {"date": d}):
            continue
        doc = frappe.get_doc({
            "doctype": "Bilan Lait Journalier", "date": d, "lait_vendu": 100,
        })
        doc.insert(ignore_permissions=True)
        _created.append(("Bilan Lait Journalier", doc.name))
        created_days += 1
    return created_days


def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabVelage` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.commit()


# ─── Tests ───

def test_structure(results):
    print("  ----  Structure — colonnes typées + 5 sections")
    cols, rows = execute({"periode": "Mois", "date": MOIS_DATE})
    names = [c["fieldname"] for c in cols]
    _check(names == ["section", "indicateur", "valeur", "unite"],
           f"Colonnes = section/indicateur/valeur/unite (got {names})", results)
    valeur_col = cols[2]
    _check(valeur_col["fieldtype"] == "Float" and valeur_col.get("precision") == 2,
           "Colonne valeur = Float precision 2 (export Excel propre)", results)
    sections = {r["section"] for r in rows}
    for s in ("Cheptel", "Production", "Alimentation", "Charges", "Coûts Unitaires"):
        _check(s in sections, f"Section « {s} » présente", results)
    non_numeric = [r for r in rows
                   if r["valeur"] is not None
                   and not isinstance(r["valeur"], (int, float))]
    _check(not non_numeric,
           f"Toutes les valeurs sont numériques ({len(non_numeric)} non conformes)",
           results)


def test_period_bounds(results):
    print("  ----  Bornes de période — Mois calendaire / Semaine ISO")
    debut, fin = period_bounds("Mois", getdate(MOIS_DATE))
    _check((str(debut), str(fin)) == ("2019-03-01", "2019-03-31"),
           f"Mois : 2019-03-01 → 2019-03-31 (got {debut} → {fin})", results)
    debut, fin = period_bounds("Semaine", getdate(SEM_DATE))
    _check((str(debut), str(fin)) == ("2019-03-04", "2019-03-10"),
           f"Semaine ISO : lundi 04/03 → dimanche 10/03 (got {debut} → {fin})",
           results)


def test_valeurs_mois(results, base_prod, base_vendu, blj_days):
    print("  ----  Valeurs mensuelles — deltas depuis la baseline")
    _, rows = execute({"periode": "Mois", "date": MOIS_DATE})
    prod = _find(rows, "Production", "Production Totale")["valeur"]
    # 2 vaches × 10 L × 31 jours = 620 L
    _check(round(prod - base_prod, 1) == 620,
           f"Δ Production Totale = 620 L (got {round(prod - base_prod, 1)})",
           results)
    vendu = _find(rows, "Production", "Lait Vendu")["valeur"]
    attendu = 100 * blj_days
    _check(round(vendu - base_vendu, 1) == attendu,
           f"Δ Lait Vendu = {attendu} L (got {round(vendu - base_vendu, 1)})",
           results)
    lc = _find(rows, "Alimentation", "L/C")
    _check(lc is not None and "cible" in lc["indicateur"],
           "Ligne L/C présente avec la cible dans le libellé", results)
    iofc = _find(rows, "Coûts Unitaires", "IOFC (Income Over Feed Cost) / Vache")
    _check(iofc is not None, "Ligne IOFC (Income Over Feed Cost)/VL/j présente",
           results)
    hors = _find(rows, "Coûts Unitaires", "Coût du Litre hors Amortissement")
    _check(hors is not None, "Ligne Coût du Litre hors Amortissement présente",
           results)


def test_valeurs_semaine(results, base_prod_sem):
    print("  ----  Valeurs hebdomadaires — production de la semaine ISO")
    _, rows = execute({"periode": "Semaine", "date": SEM_DATE})
    prod = _find(rows, "Production", "Production Totale")["valeur"]
    # 2 vaches × 10 L × 7 jours = 140 L
    _check(round(prod - base_prod_sem, 1) == 140,
           f"Δ Production semaine = 140 L (got {round(prod - base_prod_sem, 1)})",
           results)


def test_periode_future(results):
    print("  ----  Période future — ligne INFO, pas de faux zéros")
    _, rows = execute({"periode": "Mois", "date": "2099-01-15"})
    _check(len(rows) == 1 and rows[0]["section"] == "INFO",
           "Période future → une seule ligne INFO", results)


# ─── Runner ───

def run():
    print("\n" + "=" * 70)
    print("  RAPPORT PERFORMANCE — TESTS")
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

    # Baselines avant fixtures (les totaux incluent les données réelles)
    _, base_rows = execute({"periode": "Mois", "date": MOIS_DATE})
    base_prod = (_find(base_rows, "Production", "Production Totale")
                 or {}).get("valeur", 0)
    base_vendu = (_find(base_rows, "Production", "Lait Vendu")
                  or {}).get("valeur", 0)
    _, base_sem = execute({"periode": "Semaine", "date": SEM_DATE})
    base_prod_sem = (_find(base_sem, "Production", "Production Totale")
                     or {}).get("valeur", 0)

    cows = [_animal(f"C{i}") for i in (1, 2)]
    for day in range(1, 32):
        for c in cows:
            _traite(c, f"2019-03-{day:02d}", 10)
    blj_days = _seed_blj()
    frappe.db.commit()

    test_structure(results)
    test_period_bounds(results)
    test_valeurs_mois(results, base_prod, base_vendu, blj_days)
    test_valeurs_semaine(results, base_prod_sem)
    test_periode_future(results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} "
          f"passés, {results['fail']} échoués")
    print("=" * 70)
    return results
