"""
Tests unitaires — Allotement Animaux Report
Run: bench execute hmd_agro.hmd_agro.tests.test_allotement_report.run_all_tests
"""
import json

import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux import (
    _apply_suggestions, _get_suggestion, execute,
    get_lots_capacity, update_lot_seuils,
)

LOT_MAP = {"FV": "Primipare et FV", "FP": "FP", "THP": "THP", "HP": "HP",
           "MP": "MP", "TARISSEMENT": "TARISSEMENT", "TARIE": "TARIE"}
_find_lot = LOT_MAP.get
REF = getdate("2026-04-10")

TEST_BAT = "TEST-BAT-SEUIL"
TEST_LOT = "TEST-LOT-SEUIL"


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


def run_all_tests():
    print("\n" + "=" * 60)
    print("  ALLOTEMENT ANIMAUX — TESTS UNITAIRES")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    test_suggestion_primipare(results)
    test_suggestion_multipare(results)
    test_suggestion_tarissement(results)
    test_suggestion_tarie(results)
    test_suggestion_no_dim(results)
    test_apply_same_lot_filtered(results)
    test_execute(results)
    test_seuil_persistence(results)
    test_get_lots_capacity_includes_seuil(results)

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results


def test_suggestion_primipare(results):
    log("Primipare (1ère lactation)", "HEAD")
    base = {"numero_lactation": 1, "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE"}
    for dim, expected in [(50, "Primipare et FV"), (300, "Primipare et FV"), (301, "FP")]:
        r = _get_suggestion({**base, "dim": dim}, REF, _find_lot)
        check(r == expected, f"DIM {dim} → {expected}", f"DIM {dim} → {r}", results)


def test_suggestion_multipare(results):
    log("Multipare (lactation > 1)", "HEAD")
    base = {"numero_lactation": 3, "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE"}
    cases = [
        (10, "Primipare et FV"), (30, "Primipare et FV"),
        (31, "THP"), (120, "THP"),
        (121, "HP"), (240, "HP"),
        (241, "MP"), (305, "MP"),
        (306, "FP"), (500, "FP"),
    ]
    for dim, expected in cases:
        r = _get_suggestion({**base, "dim": dim}, REF, _find_lot)
        check(r == expected, f"DIM {dim} → {expected}", f"DIM {dim} → {r}", results)


def test_suggestion_tarissement(results):
    log("Tarissement (≤60j avant vêlage)", "HEAD")
    base = {"etat_gestation": "GESTANTE", "etat_lactation": "EN_PRODUCTION",
            "dim": 250, "numero_lactation": 3}

    r = _get_suggestion({**base, "date_velage_prevue": getdate("2026-05-20")}, REF, _find_lot)
    check(r == "TARISSEMENT", "40j avant → TARISSEMENT", f"40j → {r}", results)

    r = _get_suggestion({**base, "date_velage_prevue": getdate("2026-06-09")}, REF, _find_lot)
    check(r == "TARISSEMENT", "60j avant → TARISSEMENT (limite)", f"60j → {r}", results)

    r = _get_suggestion({**base, "date_velage_prevue": getdate("2026-06-10")}, REF, _find_lot)
    check(r != "TARISSEMENT", "61j → suit DIM", f"61j → {r}", results)

    r = _get_suggestion({**base, "dim": 100, "date_velage_prevue": getdate("2026-05-01")}, REF, _find_lot)
    check(r == "TARISSEMENT", "Priorité tarissement sur DIM", f"→ {r}", results)


def test_suggestion_tarie(results):
    log("Vache TARIE", "HEAD")
    r = _get_suggestion({"etat_lactation": "TARIE", "etat_gestation": "VIDE",
                         "dim": None, "numero_lactation": 2}, REF, _find_lot)
    check(r == "TARIE", "TARIE → lot TARIE", f"→ {r}", results)

    r = _get_suggestion({"etat_lactation": "TARIE", "etat_gestation": "GESTANTE",
                         "date_velage_prevue": getdate("2026-05-01"),
                         "dim": None, "numero_lactation": 2}, REF, _find_lot)
    check(r == "TARIE", "TARIE + proche vêlage → reste TARIE", f"→ {r}", results)


def test_suggestion_no_dim(results):
    log("Pas de lactation (DIM=None)", "HEAD")
    r = _get_suggestion({"dim": None, "etat_lactation": "", "etat_gestation": "VIDE",
                         "numero_lactation": 0}, REF, _find_lot)
    check(r is None, "Pas de DIM → None", f"→ {r}", results)


def test_apply_same_lot_filtered(results):
    log("_apply_suggestions — filtrage quand lot suggéré = lot actuel", "HEAD")

    thp_lot = frappe.db.get_value("Lot", {"actif": 1, "lot_type": "THP"}, "name")
    fp_lot = frappe.db.get_value("Lot", {"actif": 1, "lot_type": "FP"}, "name")
    if not thp_lot or not fp_lot:
        log(f"Skip (THP={thp_lot}, FP={fp_lot} introuvables en base)", "FAIL")
        results["fail"] += 1
        return

    data = [
        {"lot_actuel": thp_lot, "dim": 100, "numero_lactation": 2,
         "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE", "suggestion_lot": ""},
        {"lot_actuel": fp_lot, "dim": 100, "numero_lactation": 2,
         "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE", "suggestion_lot": ""},
    ]
    _apply_suggestions(data, REF)

    check(data[0]["suggestion_lot"] == "",
          f"DIM 100 déjà en {thp_lot} (THP) → pas de suggestion",
          f"→ '{data[0]['suggestion_lot']}'", results)
    check(data[1]["suggestion_lot"] == thp_lot,
          f"DIM 100 en {fp_lot} → suggestion {thp_lot}",
          f"→ '{data[1]['suggestion_lot']}'", results)


def test_execute(results):
    log("execute() — colonnes et données", "HEAD")
    columns, data = execute()

    expected = ["nom_metier", "lot_actuel", "dim", "jours_gestation",
                "j_2", "j_1", "j", "delta_j_vs_j_1", "moyenne_3j"]
    col_names = [c["fieldname"] for c in columns]
    check(col_names == expected, f"Colonnes = {expected}", f"Colonnes: {col_names}", results)
    check(isinstance(data, list), "Data est une liste", f"Type: {type(data)}", results)


def _ensure_test_lot():
    if not frappe.db.exists("Batiment", TEST_BAT):
        frappe.get_doc({
            "doctype": "Batiment", "nom_batiment": TEST_BAT,
            "type_batiment": "ELEVAGE", "actif": 1,
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("Lot", TEST_LOT):
        frappe.get_doc({
            "doctype": "Lot", "nom": TEST_LOT, "batiment": TEST_BAT,
            "lot_type": "TEST", "superficie_m2": 100,
            "capacite_optimale": 10, "capacite_maximale": 15, "actif": 1,
        }).insert(ignore_permissions=True)


def _cleanup_test_lot():
    if frappe.db.exists("Lot", TEST_LOT):
        frappe.delete_doc("Lot", TEST_LOT, force=1, ignore_permissions=True)
    if frappe.db.exists("Batiment", TEST_BAT):
        frappe.delete_doc("Batiment", TEST_BAT, force=1, ignore_permissions=True)


def test_seuil_persistence(results):
    log("update_lot_seuils — persistance & normalisation", "HEAD")
    _ensure_test_lot()
    try:
        cases = [
            ({TEST_LOT: 25.5}, 25.5, "dict 25.5"),
            (json.dumps({TEST_LOT: 18.0}), 18.0, "JSON str 18.0"),
            ({TEST_LOT: 0}, 0.0, "0 → cleared"),
            ({TEST_LOT: ""}, 0.0, "'' → cleared"),
            ({TEST_LOT: "abc"}, 0.0, "'abc' → cleared (no crash)"),
        ]
        for arg, expected, label in cases:
            update_lot_seuils(arg)
            val = float(frappe.db.get_value("Lot", TEST_LOT, "seuil_production_3j") or 0)
            check(val == expected, label, f"{label}: got {val!r}", results)
    finally:
        _cleanup_test_lot()


def test_get_lots_capacity_includes_seuil(results):
    log("get_lots_capacity — expose seuil_production_3j", "HEAD")
    _ensure_test_lot()
    try:
        update_lot_seuils({TEST_LOT: 24.0})
        lot = next((l for l in get_lots_capacity() if l.get("name") == TEST_LOT), None)
        check(lot is not None, "Lot test dans la réponse", "Lot test absent", results)
        if lot:
            check(float(lot.get("seuil_production_3j") or 0) == 24.0,
                  "Champ seuil_production_3j = 24.0",
                  f"Got {lot.get('seuil_production_3j')!r}", results)
    finally:
        _cleanup_test_lot()
