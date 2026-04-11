"""
Tests unitaires — Allotement Animaux Report
Run: bench execute hmd_agro.hmd_agro.tests.test_allotement_report.run_all_tests
"""
import frappe
from frappe.utils import today, add_days, getdate

from hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux import (
    _get_suggestion, execute
)

LOT_MAP = {"FV": "Primipare et FV", "FP": "FP", "THP": "THP", "HP": "HP",
           "MP": "MP", "TARISSEMENT": "TARISSEMENT", "TARIE": "TARIE"}

def _find_lot(kw):
    return LOT_MAP.get(kw)

REF = getdate("2026-04-10")


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

    test_find_lot(results)
    test_suggestion_primipare(results)
    test_suggestion_multipare(results)
    test_suggestion_tarissement(results)
    test_suggestion_tarie(results)
    test_suggestion_no_dim(results)
    test_apply_same_lot_filtered(results)
    test_past_date_no_suggestions(results)
    test_execute(results)

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results


# ─── find_lot ───

def test_find_lot(results):
    log("find_lot — recherche par mot-clé", "HEAD")

    lot_names = ["THP", "HP", "MP", "FP", "TARISSEMENT", "TARIE", "Primipare et FV"]

    def find_lot(keyword):
        kw = keyword.lower()
        for n in lot_names:
            nl = n.lower()
            if kw == "tarie" and "tarissement" in nl:
                continue
            if kw == "hp" and "thp" in nl:
                continue
            if kw in nl:
                return n
        return None

    check(find_lot("FV") == "Primipare et FV", "FV → Primipare et FV", f"FV → {find_lot('FV')}", results)
    check(find_lot("HP") == "HP", "HP ne matche pas THP", f"HP → {find_lot('HP')}", results)
    check(find_lot("TARIE") == "TARIE", "TARIE ne matche pas TARISSEMENT", f"TARIE → {find_lot('TARIE')}", results)
    check(find_lot("TARISSEMENT") == "TARISSEMENT", "TARISSEMENT exact", f"TARISSEMENT → {find_lot('TARISSEMENT')}", results)
    check(find_lot("ZZZZZ") is None, "Inconnu → None", f"Inconnu → {find_lot('ZZZZZ')}", results)


# ─── Primipare ───

def test_suggestion_primipare(results):
    log("Primipare (1ère lactation)", "HEAD")

    base = {"numero_lactation": 1, "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE"}

    r = _get_suggestion({**base, "dim": 50}, REF, _find_lot)
    check(r == "Primipare et FV", "DIM 50 → FV", f"DIM 50 → {r}", results)

    r = _get_suggestion({**base, "dim": 300}, REF, _find_lot)
    check(r == "Primipare et FV", "DIM 300 → FV (limite)", f"DIM 300 → {r}", results)

    r = _get_suggestion({**base, "dim": 301}, REF, _find_lot)
    check(r == "FP", "DIM 301 → FP", f"DIM 301 → {r}", results)


# ─── Multipare ───

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


# ─── Tarissement ───

def test_suggestion_tarissement(results):
    log("Tarissement (≤60j avant vêlage)", "HEAD")

    base = {"etat_gestation": "GESTANTE", "etat_lactation": "EN_PRODUCTION",
            "dim": 250, "numero_lactation": 3}

    # 40j → TARISSEMENT
    r = _get_suggestion({**base, "date_velage_prevue": getdate("2026-05-20")}, REF, _find_lot)
    check(r == "TARISSEMENT", "40j avant → TARISSEMENT", f"40j → {r}", results)

    # 60j → TARISSEMENT (limite)
    r = _get_suggestion({**base, "date_velage_prevue": getdate("2026-06-09")}, REF, _find_lot)
    check(r == "TARISSEMENT", "60j avant → TARISSEMENT", f"60j → {r}", results)

    # 61j → suit DIM
    r = _get_suggestion({**base, "date_velage_prevue": getdate("2026-06-10")}, REF, _find_lot)
    check(r != "TARISSEMENT", "61j → suit DIM", f"61j → {r}", results)

    # Priorité sur DIM
    r = _get_suggestion({**base, "dim": 100, "date_velage_prevue": getdate("2026-05-01")}, REF, _find_lot)
    check(r == "TARISSEMENT", "Priorité tarissement sur DIM", f"→ {r}", results)


# ─── Tarie ───

def test_suggestion_tarie(results):
    log("Vache TARIE", "HEAD")

    r = _get_suggestion({"etat_lactation": "TARIE", "etat_gestation": "VIDE",
                         "dim": None, "numero_lactation": 2}, REF, _find_lot)
    check(r == "TARIE", "TARIE → lot TARIE", f"TARIE → {r}", results)

    # TARIE + GESTANTE proche → reste TARIE (déjà passée par tarissement)
    r = _get_suggestion({"etat_lactation": "TARIE", "etat_gestation": "GESTANTE",
                         "date_velage_prevue": getdate("2026-05-01"),
                         "dim": None, "numero_lactation": 2}, REF, _find_lot)
    check(r == "TARIE", "TARIE + proche vêlage → reste TARIE", f"→ {r}", results)


# ─── Pas de DIM ───

def test_suggestion_no_dim(results):
    log("Pas de lactation (DIM=None)", "HEAD")

    r = _get_suggestion({"dim": None, "etat_lactation": "", "etat_gestation": "VIDE",
                         "numero_lactation": 0}, REF, _find_lot)
    check(r is None, "Pas de DIM → None", f"→ {r}", results)


# ─── _apply_suggestions filtre quand lot = suggestion ───

def test_apply_same_lot_filtered(results):
    log("_apply_suggestions — même lot = pas de suggestion", "HEAD")

    from hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux import _apply_suggestions

    data = [
        {"lot_actuel": "THP", "dim": 100, "numero_lactation": 2,
         "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
         "suggestion_lot": ""},
        {"lot_actuel": "FP", "dim": 100, "numero_lactation": 2,
         "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
         "suggestion_lot": ""},
    ]

    _apply_suggestions(data, REF)

    check(data[0]["suggestion_lot"] == "",
        "DIM 100 déjà en THP → pas de suggestion",
        f"→ '{data[0]['suggestion_lot']}'", results)

    check(data[1]["suggestion_lot"] != "",
        "DIM 100 en FP → suggestion THP",
        f"→ '{data[1]['suggestion_lot']}'", results)


# ─── Date passée ───

def test_past_date_no_suggestions(results):
    log("Date passée → pas de suggestions", "HEAD")

    _, data = execute({"reference_date": add_days(today(), -7)})
    has_suggestions = any(row.get("suggestion_lot") for row in data)
    check(not has_suggestions, "Date -7j → aucune suggestion", "Suggestions trouvées pour date passée", results)


# ─── execute() ───

def test_execute(results):
    log("execute() — colonnes et données", "HEAD")

    columns, data = execute()

    check(len(columns) == 10, "10 colonnes", f"{len(columns)} colonnes", results)

    col_names = [c["fieldname"] for c in columns]
    expected = ["nom_metier", "lot_actuel", "dim", "jours_gestation",
                "j_2", "j_1", "j", "delta_j_vs_j_1", "moyenne_3j", "suggestion_lot"]
    check(col_names == expected, "Noms colonnes corrects", f"Colonnes: {col_names}", results)

    check(isinstance(data, list), "Data est une liste", f"Data type: {type(data)}", results)
