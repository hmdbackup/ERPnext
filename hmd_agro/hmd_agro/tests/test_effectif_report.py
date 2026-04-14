"""
Tests — Rapport Mensuel / Effectif (per-day diff).
Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_effectif_report.run_all_tests
"""
import frappe
import json
from frappe.utils import getdate

from hmd_agro.hmd_agro.utils import snapshot as S
from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _effectif, _production_lot

PREFIX = "TEST-EFF-"
ANNEE = 2099


# ─── Reporting helpers ───────────────────────────────────────────────────────

def _log(msg, level="INFO"):
    prefix = {"PASS": "  OK", "FAIL": "FAIL", "HEAD": "----"}.get(level, "    ")
    print(f"  {prefix}  {msg}")

def _check(cond, ok_msg, fail_msg, results):
    if cond:
        _log(ok_msg, "PASS"); results["pass"] += 1
    else:
        _log(fail_msg, "FAIL"); results["fail"] += 1


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _state(cat, lact="", gest="", statut="ACTIF", prix=0, est_achat=0):
    return {"cat": cat, "lact": lact, "gest": gest, "statut": statut,
            "lot": None, "prix_vente": prix, "date_sortie": None,
            "est_achat": est_achat, "date_entree": None}

def _snap(date_str, animals):
    agg = S.aggregate_counts(animals)
    doc = frappe.get_doc({
        "doctype": S.DOCTYPE, "date_snapshot": date_str, "frozen": 1,
        "animals_json": json.dumps(animals),
        "events_json": "{}",
        "aggregates_json": json.dumps(agg),
    })
    doc.name = f"SNAP-{date_str}"
    doc.db_insert()

def _animal(suffix, **kwargs):
    defaults = {
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "sexe": "F", "statut": "ACTIF",
        "date_naissance": f"{ANNEE-4}-01-01", "date_entree": f"{ANNEE-1}-12-31",
    }
    defaults.update(kwargs)
    doc = frappe.get_doc(defaults)
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    return doc

def _traite(animal, date, litres):
    doc = frappe.get_doc({"doctype": "Traite", "animal": animal,
                          "date_traite": date, "quantite_litres": litres})
    doc.name = f"{PREFIX}TR-{animal}-{date}"
    doc.db_insert()

def _velage(animal, date, sexe1, vivant1=1):
    doc = frappe.get_doc({"doctype": "Velage", "animal": animal, "date_velage": date,
                          "type_velage": "FACILE", "nombre_veaux": "1",
                          "sexe_veau1": sexe1, "vivant_veau1": vivant1})
    doc.name = f"{PREFIX}VEL-{animal}-{date}"
    doc.db_insert()

def _cleanup():
    frappe.db.sql(f"DELETE FROM `tab{S.DOCTYPE}` WHERE date_snapshot LIKE %s", f"{ANNEE}%")
    frappe.db.sql(f"DELETE FROM `tab{S.DOCTYPE}` WHERE date_snapshot LIKE %s", f"{ANNEE-1}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabVelage` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabTraite` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.commit()


# ─── Unit tests ──────────────────────────────────────────────────────────────

def test_resolve_col(r):
    _log("resolve_col", "HEAD")
    _check(S.resolve_col("VACHE", "EN_PRODUCTION", "VIDE") == "Vaches - Lact.", "vache lact", "wrong", r)
    _check(S.resolve_col("VACHE", "TARIE", "VIDE") == "Vaches - Tarie", "vache tarie", "wrong", r)
    _check(S.resolve_col("GENISSE", "", "GESTANTE") == "Gén. - Pleine", "gen pleine", "wrong", r)
    _check(S.resolve_col("GENISSE", "", "VIDE") == "Gén. - Vide", "gen vide", "wrong", r)
    _check(S.resolve_col("VEAU", "", "") == "Veaux", "veau", "wrong", r)
    _check(S.resolve_col("VELLE", "", "") == "Velles", "velle", "wrong", r)
    _check(S.resolve_col("TAURILLON", "", "") == "Engraiss.", "taurillon", "wrong", r)


def test_aggregate(r):
    _log("aggregate_counts — skips non-ACTIF", "HEAD")
    animals = {
        "a": _state("VACHE", "EN_PRODUCTION", "VIDE"),
        "b": _state("VACHE", "TARIE", "VIDE"),
        "c": _state("GENISSE", "", "GESTANTE"),
        "d": _state("VEAU", statut="MORT"),
    }
    agg = S.aggregate_counts(animals)
    _check(agg["Vaches - Lact."] == 1 and agg["Vaches - Tarie"] == 1, "1+1 vaches", f"{agg}", r)
    _check(agg["Total"] == 3, "total excludes MORT", f"{agg}", r)


def test_diff_velage(r):
    _log("diff_day — vêlage (Génisse gestante → Vache lactante)", "HEAD")
    prev = {"x": _state("GENISSE", "", "GESTANTE")}
    curr = {"x": _state("VACHE", "EN_PRODUCTION", "VIDE")}
    d = S.diff_day(prev, curr)
    _check(d["velage"]["Vaches - Lact."] == 1, "vêlage → lact", f"{d['velage']}", r)
    _check(d["cat_plus"]["Total"] == 0 and d["cat_minus"]["Total"] == 0, "not a cat change", "misclassified", r)


def test_diff_tarissement(r):
    _log("diff_day — tarissement (Lact → Tarie)", "HEAD")
    d = S.diff_day({"x": _state("VACHE", "EN_PRODUCTION", "VIDE")},
                   {"x": _state("VACHE", "TARIE", "VIDE")})
    _check(d["cat_minus"]["Vaches - Lact."] == 1 and d["cat_plus"]["Vaches - Tarie"] == 1, "-lact +tarie", f"{d}", r)


def test_diff_insemination(r):
    _log("diff_day — IA réussie (Gén. Vide → Pleine)", "HEAD")
    d = S.diff_day({"x": _state("GENISSE", "", "VIDE")},
                   {"x": _state("GENISSE", "", "GESTANTE")})
    _check(d["cat_minus"]["Gén. - Vide"] == 1 and d["cat_plus"]["Gén. - Pleine"] == 1, "Vide→Pleine", f"{d}", r)


def test_diff_vente(r):
    _log("diff_day — vente avec prix", "HEAD")
    d = S.diff_day({"x": _state("VACHE", "EN_PRODUCTION", "VIDE")},
                   {"x": _state("VACHE", "EN_PRODUCTION", "VIDE", statut="VENDU", prix=800)})
    _check(d["ventes"]["Vaches - Lact."] == 1, "1 vente", f"{d['ventes']}", r)
    _check(d["prix_vente"]["Vaches - Lact."] == 800, "prix=800", f"{d['prix_vente']}", r)


def test_diff_mortalite(r):
    _log("diff_day — mortalité veau", "HEAD")
    d = S.diff_day({"x": _state("VEAU")}, {"x": _state("VEAU", statut="MORT")})
    _check(d["mortalite"]["Veaux"] == 1, "1 mort", f"{d['mortalite']}", r)
    _check(d["prix_vente"]["Total"] == 0, "no prix", f"{d['prix_vente']}", r)


def test_diff_achat(r):
    _log("diff_day — achat", "HEAD")
    d = S.diff_day({}, {"x": _state("GENISSE", "", "VIDE", est_achat=1)})
    _check(d["achats"]["Gén. - Vide"] == 1, "1 achat", f"{d['achats']}", r)


def test_diff_manual_cat(r):
    _log("diff_day — changement catégorie manuel (Velle → Génisse)", "HEAD")
    d = S.diff_day({"x": _state("VELLE")}, {"x": _state("GENISSE", "", "VIDE")})
    _check(d["cat_minus"]["Velles"] == 1 and d["cat_plus"]["Gén. - Vide"] == 1, "-Velle +Gén", f"{d}", r)


# ─── Integration ─────────────────────────────────────────────────────────────

def test_effectif_single_day(r):
    _log("_effectif — single day with vente + naissance event", "HEAD")
    _cleanup()
    # Day D-1 (frozen): 2 vaches lact, 1 veau
    _snap(f"{ANNEE}-03-14", {
        "A": _state("VACHE", "EN_PRODUCTION", "VIDE"),
        "B": _state("VACHE", "EN_PRODUCTION", "VIDE"),
        "V1": _state("VEAU"),
    })
    # Day D (frozen): B sold @ 700; a new veau appears (born today)
    _snap(f"{ANNEE}-03-15", {
        "A": _state("VACHE", "EN_PRODUCTION", "VIDE"),
        "B": _state("VACHE", "EN_PRODUCTION", "VIDE", statut="VENDU", prix=700),
        "V1": _state("VEAU"),
        "V2": _state("VEAU"),
    })
    # Velage event on day D
    _animal("MERE", categorie="VACHE", etat_lactation="EN_PRODUCTION", etat_gestation="VIDE")
    _velage(f"{PREFIX}MERE", f"{ANNEE}-03-15", "M")

    ctx = {"date_filter": getdate(f"{ANNEE}-03-15"),
           "date_debut": getdate(f"{ANNEE}-03-01"), "date_fin": getdate(f"{ANNEE}-03-31"),
           "nb_jours": 31, "mois": 3, "annee": ANNEE, "jour": 15}
    _, data = _effectif(ctx)
    by_label = {row["ligne"]: row for row in data}

    _check(by_label["Effectif Initial"]["Total"] == 3, "init=3", f"got {by_label['Effectif Initial']}", r)
    _check(by_label["Vente (Quantité)"]["Vaches - Lact."] == 1, "1 vente lact", f"{by_label['Vente (Quantité)']}", r)
    _check(by_label["Vente (Prix DT)"]["Vaches - Lact."] == 700, "prix=700", f"{by_label['Vente (Prix DT)']}", r)
    _check(by_label["Naissance"]["Veaux"] == 1, "1 naissance M (event)", f"{by_label['Naissance']}", r)
    # Final reads the frozen snapshot for the day: A + V1 + V2 (B=VENDU excluded, MERE created after snap)
    _check(by_label["Effectif Final"]["Total"] == 3, "final=3 (A + V1 + V2)", f"got {by_label['Effectif Final']}", r)


def test_effectif_gap_initial(r):
    _log("_effectif — missing previous day snapshot → gap", "HEAD")
    _cleanup()
    ctx = {"date_filter": getdate(f"{ANNEE}-06-15"),
           "date_debut": getdate(f"{ANNEE}-06-01"), "date_fin": getdate(f"{ANNEE}-06-30"),
           "nb_jours": 30, "mois": 6, "annee": ANNEE, "jour": 15}
    _, data = _effectif(ctx)
    _check(len(data) == 1 and "Importer" in data[0]["ligne"], "gap message", f"{data}", r)


def test_effectif_chain_invariant(r):
    _log("_effectif — next-day Initial = previous-day Final", "HEAD")
    _cleanup()
    _snap(f"{ANNEE}-03-14", {"A": _state("VACHE", "EN_PRODUCTION", "VIDE")})
    _snap(f"{ANNEE}-03-15", {"A": _state("VACHE", "EN_PRODUCTION", "VIDE"),
                             "B": _state("GENISSE", "", "VIDE", est_achat=1)})
    _snap(f"{ANNEE}-03-16", {"A": _state("VACHE", "EN_PRODUCTION", "VIDE"),
                             "B": _state("GENISSE", "", "VIDE", est_achat=1)})

    def render(d):
        ctx = {"date_filter": getdate(d),
               "date_debut": getdate(f"{ANNEE}-03-01"), "date_fin": getdate(f"{ANNEE}-03-31"),
               "nb_jours": 31, "mois": 3, "annee": ANNEE, "jour": int(d[-2:])}
        _, data = _effectif(ctx)
        return {row["ligne"]: row for row in data}

    d15 = render(f"{ANNEE}-03-15")
    d16 = render(f"{ANNEE}-03-16")
    _check(d15["Effectif Final"]["Total"] == d16["Effectif Initial"]["Total"],
           f"chain ok ({d15['Effectif Final']['Total']})",
           f"broken: {d15['Effectif Final']['Total']} != {d16['Effectif Initial']['Total']}", r)


# ─── Production par Lot ──────────────────────────────────────────────────────

def _state_with_lot(cat, lact, lot):
    s = _state(cat, lact=lact, gest="VIDE")
    s["lot"] = lot
    return s

def test_production_lot_basic(r):
    _log("_production_lot — Effectif + 2 day rows + Moyenne", "HEAD")
    _cleanup()
    # Keys in snapshot MUST match Animal.name that Traite.animal will reference
    a1, a2, b1 = f"{PREFIX}A1", f"{PREFIX}A2", f"{PREFIX}B1"
    day_state = {
        a1: _state_with_lot("VACHE", "EN_PRODUCTION", "LotA"),
        a2: _state_with_lot("VACHE", "EN_PRODUCTION", "LotA"),
        b1: _state_with_lot("VACHE", "EN_PRODUCTION", "LotB"),
    }
    _snap(f"{ANNEE}-03-14", day_state)
    _snap(f"{ANNEE}-03-15", day_state)

    # Production day D-1 (14) = 40L LotA, 10L LotB; day D (15) = 60L LotA, 12L LotB
    _traite(a1, f"{ANNEE}-03-14", 20)
    _traite(a2, f"{ANNEE}-03-14", 20)
    _traite(b1, f"{ANNEE}-03-14", 10)
    _traite(a1, f"{ANNEE}-03-15", 30)
    _traite(a2, f"{ANNEE}-03-15", 30)
    _traite(b1, f"{ANNEE}-03-15", 12)

    ctx = {"date_filter": getdate(f"{ANNEE}-03-15"),
           "date_debut": getdate(f"{ANNEE}-03-01"), "date_fin": getdate(f"{ANNEE}-03-31"), "nb_jours": 31}
    _, data = _production_lot(ctx)
    by_label = {row["jour"]: row for row in data}

    _check(by_label["Effectif"]["LotA"] == 2 and by_label["Effectif"]["LotB"] == 1, "effectif per lot", f"{by_label['Effectif']}", r)
    _check(by_label["14/03"]["LotA"] == 40 and by_label["14/03"]["LotB"] == 10, "D-1 prod", f"{by_label['14/03']}", r)
    _check(by_label["15/03"]["LotA"] == 60 and by_label["15/03"]["LotB"] == 12, "D prod", f"{by_label['15/03']}", r)
    # Moyenne = prod(D) / effectif(D): LotA = 60/2 = 30, LotB = 12/1 = 12
    _check(by_label["Moyenne / lot"]["LotA"] == 30.0, "moy LotA = prod(D)/eff", f"{by_label['Moyenne / lot']}", r)
    _check(by_label["Moyenne / lot"]["LotB"] == 12.0, "moy LotB = prod(D)/eff", f"{by_label['Moyenne / lot']}", r)
    # Total moyenne = 72/3 = 24
    _check(by_label["Moyenne / lot"]["total"] == 24.0, "moy total = 72/3", f"{by_label['Moyenne / lot']}", r)


def test_production_lot_historical_lot_move(r):
    _log("_production_lot — cow moves lot; past report keeps past membership", "HEAD")
    _cleanup()
    x = f"{PREFIX}X"
    snap_animals = {x: _state_with_lot("VACHE", "EN_PRODUCTION", "LotA")}
    _snap(f"{ANNEE}-03-14", snap_animals)
    _snap(f"{ANNEE}-03-15", snap_animals)
    _traite(x, f"{ANNEE}-03-15", 40)

    ctx = {"date_filter": getdate(f"{ANNEE}-03-15"),
           "date_debut": getdate(f"{ANNEE}-03-01"), "date_fin": getdate(f"{ANNEE}-03-31"), "nb_jours": 31}
    _, data = _production_lot(ctx)
    by_label = {row["jour"]: row for row in data}
    _check("LotA" in by_label["Effectif"] and "LotZ" not in by_label["Effectif"],
           "report uses past lot (A), not current (Z)", f"{by_label['Effectif']}", r)
    _check(by_label["15/03"].get("LotA") == 40, "prod attributed to past lot", f"{by_label['15/03']}", r)


# ─── freeze_yesterday ────────────────────────────────────────────────────────

def test_freeze_roundtrip(r):
    _log("freeze_day — writes + round-trips state", "HEAD")
    _cleanup()
    _animal("FR1", categorie="VACHE", etat_lactation="EN_PRODUCTION", etat_gestation="VIDE")
    S.freeze_day(f"{ANNEE}-03-20")
    snap = S.read_snapshot(f"{ANNEE}-03-20")
    _check(snap is not None, "stored", "missing", r)
    _check(f"{PREFIX}FR1" in snap["animals"], "animal in JSON", f"{list(snap['animals'].keys())[:3]}", r)
    _check(snap["aggregates"]["Vaches - Lact."] >= 1, "aggregate includes animal", f"{snap['aggregates']}", r)


# ─── Runner ──────────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / EFFECTIF — TESTS")
    print("=" * 60)
    r = {"pass": 0, "fail": 0}
    try:
        _cleanup()
        test_resolve_col(r)
        test_aggregate(r)
        test_diff_velage(r)
        test_diff_tarissement(r)
        test_diff_insemination(r)
        test_diff_vente(r)
        test_diff_mortalite(r)
        test_diff_achat(r)
        test_diff_manual_cat(r)
        test_effectif_single_day(r)
        test_effectif_gap_initial(r)
        test_effectif_chain_invariant(r)
        test_production_lot_basic(r)
        test_production_lot_historical_lot_move(r)
        test_freeze_roundtrip(r)
    finally:
        _cleanup()
    total = r["pass"] + r["fail"]
    print(f"\n  RÉSULTATS: {r['pass']}/{total} passés, {r['fail']} échoués\n")
    return r
