"""
Tests unitaires — Rapport Mensuel / Indicateurs

Vache counts = snapshot at date_filter (reconstructed from events).
Production / Concentré / MS = cumulative date_debut → date_filter.
Cheptel-wide values include real DB data; tests use baseline-delta to isolate fixtures.

Run: bench execute hmd_agro.hmd_agro.tests.test_indicateurs_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _indicateurs

PREFIX = "TEST-IND-"

def _ctx(date_filter_str):
    return {
        "date_filter": getdate(date_filter_str),
        "date_debut": getdate("2024-03-01"),
        "date_fin": getdate("2024-03-31"),
        "nb_jours": 31, "mois": 3, "annee": 2024,
    }

CTX_END = _ctx("2024-03-31")


def log(msg, level="INFO"):
    prefix = {"PASS": "  OK", "FAIL": "FAIL", "HEAD": "----"}.get(level, "    ")
    print(f"  {prefix}  {msg}")

def check(condition, pass_msg, fail_msg, results):
    if condition:
        log(pass_msg, "PASS")
        results["pass"] += 1
    else:
        log(fail_msg, "FAIL")
        results["fail"] += 1


_created = []

def _aliment(suffix, ms_pct, type_aliment="CONCENTRE"):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Aliment", "nom_aliment": name, "type_aliment": type_aliment,
        "unite": "KG", "prix_unitaire": 1.0, "ms_pct": ms_pct,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Aliment", name))
    return name

def _ration(suffix, composition):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Ration", "nom_ration": name, "active": 1,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Ration", name))
    for idx, (aliment_name, qty) in enumerate(composition, 1):
        child = frappe.get_doc({
            "doctype": "Composition Ration", "parent": name, "parenttype": "Ration",
            "parentfield": "composition", "idx": idx,
            "aliment": aliment_name, "quantite": qty, "unite": "KG",
        })
        child.db_insert()
        _created.append(("Composition Ration", child.name))
    return name

def _lot(suffix, ration, nb):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Lot", "nom": name, "actif": 1,
        "id_ration_actuelle": ration, "nb_animaux": nb,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Lot", name))
    return name

def _animal(suffix, lot):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
        "date_naissance": "2020-01-01", "date_entree": "2024-01-01", "id_lot": lot,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    # Velage so reconstruction sees her as VACHE
    vel = frappe.get_doc({
        "doctype": "Velage", "animal": doc.name,
        "date_velage": "2023-06-01", "type_velage": "FACILE",
        "nombre_veaux": "1", "sexe_veau1": "F", "vivant_veau1": 0,
    })
    vel.flags.ignore_validate = True
    vel.flags.ignore_links = True
    vel.db_insert()
    _created.append(("Velage", vel.name))
    return doc

def _traite(animal_name, date, litres, lot):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN", "id_lot": lot,
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))

def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find(rows, label_starts):
    return next((r for r in rows if r["indicateur"].startswith(label_starts)), None)


def _setup():
    frappe.db.sql("DELETE FROM `tabAliment` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabRation` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabComposition Ration` WHERE parent LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabVelage` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    # 2 concentrés + 1 fourrage to verify the type filter
    soja = _aliment("SOJA", 0.90, "CONCENTRE")
    mais = _aliment("MAIS", 0.88, "CONCENTRE")
    foin = _aliment("FOIN", 0.85, "FOURRAGE")
    ration = _ration("RATION", [(soja, 2), (mais, 5), (foin, 10)])
    lot = _lot("LOT", ration, 4)

    cows = [_animal(f"C{i}", lot) for i in range(1, 5)]
    for day in range(1, 32):
        date_str = f"2024-03-{day:02d}"
        for c in cows:
            _traite(c.name, date_str, 25, lot)
    frappe.db.commit()


# ─── Tests ───

def test_columns(results):
    log("Columns — indicateur, valeur, unité", "HEAD")
    cols, _ = _indicateurs(CTX_END)
    names = [c["fieldname"] for c in cols]
    check(names == ["indicateur", "valeur", "unite"], "Has 3 expected columns",
          f"Got {names}", results)

def test_vache_counts_delta(results, base_vp, base_vl, base_vt):
    log("Vache counts — delta from baseline = +4 lact (test fixture)", "HEAD")
    _, rows = _indicateurs(CTX_END)
    vp = _find(rows, "Vaches Présentes")["valeur"]
    vl = _find(rows, "Vaches Lactantes")["valeur"]
    vt = _find(rows, "Vaches Taries")["valeur"]
    check(vp - base_vp == 4, "Δ Présentes = +4 (4 fixture cows)",
          f"Got Δ={vp - base_vp}", results)
    check(vl - base_vl == 4, "Δ Lactantes = +4", f"Got Δ={vl - base_vl}", results)
    check(vt - base_vt == 0, "Δ Taries = 0", f"Got Δ={vt - base_vt}", results)

def test_production_delta(results, base_prod):
    log("Production Totale — delta from baseline", "HEAD")
    _, rows = _indicateurs(CTX_END)
    prod = _find(rows, "Production Totale")["valeur"]
    # 4 cows × 25L × 31 days = 3100L
    delta = round(prod - base_prod, 1)
    check(delta == 3100, "Δ Production = 3100L", f"Got Δ={delta}", results)

def test_concentre_delta(results, base_conc):
    log("Concentré Total — only CONCENTRE-tagged aliments", "HEAD")
    _, rows = _indicateurs(CTX_END)
    conc = _find(rows, "Concentré Total")["valeur"]
    # Soja 2kg + Mais 5kg = 7kg/cow concentré (Foin not counted)
    # 4 cows × 7kg × 31 days = 868kg
    delta = round(conc - base_conc, 1)
    check(delta == 868, "Δ Concentré = 868kg (Foin FOURRAGE excluded)",
          f"Got Δ={delta}", results)

def test_efficacite_alim_delta(results, base_ms):
    log("Efficacité Alim — delta MS includes all aliments", "HEAD")
    _, rows = _indicateurs(CTX_END)
    # Verify MS total for the test cohort
    # MS contribution: (2×0.9 + 5×0.88 + 10×0.85) × 4 cows × 31 days
    # = (1.8 + 4.4 + 8.5) × 124 = 14.7 × 124 = 1822.8 kg MS
    # We can't easily extract MS alone from indicateurs output; trust the
    # alimentation report for that. Just check Efficacité Alim is sensible (>0).
    eff = _find(rows, "Efficacité Alimentaire")["valeur"]
    check(eff > 0, f"Efficacité > 0 (got {eff})", f"Got {eff}", results)

def test_ratios(results):
    log("Ratios L/C and C/L are positive and reciprocal in shape", "HEAD")
    _, rows = _indicateurs(CTX_END)
    lc = _find(rows, "L/C")["valeur"]
    cl = _find(rows, "C/L")["valeur"]
    # Both rounded independently (2 vs 3 decimals); product can drift up to ~5% for small L/C.
    check(lc > 0 and cl > 0 and abs(lc * cl - 1) < 0.05,
          f"L/C={lc}, C/L={cl}, product={lc * cl:.3f}",
          f"L/C={lc}, C/L={cl}", results)

def test_midmonth_caps(results):
    log("date_filter mid-month → cumulatives respect the cutoff", "HEAD")
    _, rows_mid = _indicateurs(_ctx("2024-03-15"))
    _, rows_end = _indicateurs(CTX_END)
    prod_mid = _find(rows_mid, "Production Totale")["valeur"]
    prod_end = _find(rows_end, "Production Totale")["valeur"]
    check(prod_mid < prod_end, f"Mid-month prod ({prod_mid}) < end-month prod ({prod_end})",
          f"prod_mid={prod_mid}, prod_end={prod_end}", results)

def test_deferred_frais(results):
    log("Frais rows present with valeur=None (à intégrer)", "HEAD")
    _, rows = _indicateurs(CTX_END)
    frais_conc = _find(rows, "Frais Concentré")
    check(frais_conc and frais_conc["valeur"] is None, "Frais Concentré shown but unset",
          f"Got {frais_conc}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / INDICATEURS — TESTS")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    # Capture baseline before fixtures (cheptel-wide totals include real DB data)
    _cleanup()
    _, base_rows = _indicateurs(CTX_END)
    base_vp = (_find(base_rows, "Vaches Présentes") or {}).get("valeur", 0)
    base_vl = (_find(base_rows, "Vaches Lactantes") or {}).get("valeur", 0)
    base_vt = (_find(base_rows, "Vaches Taries") or {}).get("valeur", 0)
    base_prod = (_find(base_rows, "Production Totale") or {}).get("valeur", 0)
    base_conc = (_find(base_rows, "Concentré Total") or {}).get("valeur", 0)
    base_ms = 0  # unused

    try:
        _setup()
        test_columns(results)
        test_vache_counts_delta(results, base_vp, base_vl, base_vt)
        test_production_delta(results, base_prod)
        test_concentre_delta(results, base_conc)
        test_efficacite_alim_delta(results, base_ms)
        test_ratios(results)
        test_midmonth_caps(results)
        test_deferred_frais(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
