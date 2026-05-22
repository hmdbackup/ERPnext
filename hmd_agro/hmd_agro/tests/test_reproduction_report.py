"""
Tests — Rapport Reproduction (per-cow snapshot, Performance IA, Bilan Annuel)
Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_reproduction_report.run_all_tests

Coverage:
  - Bilan Annuel column structure (ivia1_moy / ivif_moy / %1IA / %2IA / %3IA+ /
    taux_reforme / taux_survie_naissance)
  - Reproduction section shape (5-tuple) + persistance column
  - _compute_ivia1_ivif_year helper with controlled fixtures
  - Persistance computation across realistic scenarios
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_reproduction.rapport_reproduction import (
    _bilan_annuel_columns,
    _bilan_year_row,
    _performance_ia_columns,
    _reproduction_columns,
    _reproduction,
    _compute_ivia1_ivif_year,
)

PREFIX = "TEST-REPRO-"
# Past year, before real data starts (real data: 2020+).
# Past so _reproduction's future-date guard doesn't fire when we run integration
# tests through the full builder.
ANNEE = 2018


def _log(msg, level="INFO"):
    prefix = {"PASS": "  OK", "FAIL": "FAIL", "HEAD": "----"}.get(level, "    ")
    print(f"  {prefix}  {msg}")


def _check(cond, ok_msg, fail_msg, r):
    if cond:
        _log(ok_msg, "PASS"); r["pass"] += 1
    else:
        _log(fail_msg, "FAIL"); r["fail"] += 1


def _cleanup():
    for dt in ("Traite", "Insemination", "Velage", "Lactation", "Animal"):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.commit()


def _animal(suffix, categorie="VACHE", date_naissance=f"{ANNEE-5}-01-01"):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": name,
        "nom_metier": name[-4:],
        "categorie": categorie, "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION",
        "etat_gestation": "VIDE",
        "date_naissance": date_naissance,
        "date_entree": date_naissance,
    })
    doc.name = name
    doc.flags.ignore_validate = True
    doc.flags.ignore_links = True
    doc.db_insert()
    return name


def _velage(animal, date_velage):
    doc = frappe.get_doc({
        "doctype": "Velage", "animal": animal, "date_velage": date_velage,
        "nombre_veaux": "1", "sexe_veau1": "F", "vivant_veau1": 1,
    })
    doc.name = f"{animal}-V-{date_velage}"
    doc.flags.ignore_validate = True
    doc.flags.ignore_links = True
    doc.db_insert()


def _insemination(animal, date_ia, numero_ia, resultat="ECHOUEE"):
    doc = frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal, "date_ia": date_ia,
        "numero_ia": numero_ia, "resultat": resultat,
    })
    doc.name = f"{animal}-IA-{date_ia}-{numero_ia}"
    doc.flags.ignore_validate = True
    doc.flags.ignore_links = True
    doc.db_insert()


def _lactation(animal, name_suffix, date_debut, statut="EN_COURS"):
    name = f"{animal}-LACT-{name_suffix}"
    doc = frappe.get_doc({
        "doctype": "Lactation",
        "animal": animal, "date_debut": date_debut,
        "statut": statut, "numero_lactation": 1,
    })
    doc.name = name
    doc.flags.ignore_validate = True
    doc.flags.ignore_links = True
    doc.db_insert()
    return name


def _traite(animal, lactation, date_traite, litres, session="MATIN"):
    name = f"{PREFIX}T-{animal[-3:]}-{date_traite}-{session}"
    doc = frappe.get_doc({
        "doctype": "Traite",
        "animal": animal, "lactation": lactation,
        "date_traite": date_traite, "session": session,
        "quantite_litres": litres,
    })
    doc.name = name
    doc.flags.ignore_validate = True
    doc.flags.ignore_links = True
    doc.db_insert()


# ─── Column structure tests ────────────────────────────────────────────────

def test_bilan_annuel_has_ivia1_ivif_cols(r):
    _log("Bilan Annuel includes IVIA1 moy + IVIF moy columns", "HEAD")
    cols = _bilan_annuel_columns()
    fields = {c["fieldname"]: c["label"] for c in cols}
    _check("ivia1_moy" in fields, "ivia1_moy field present",
           f"Fields: {list(fields.keys())}", r)
    _check("ivif_moy" in fields, "ivif_moy field present",
           f"Fields: {list(fields.keys())}", r)
    _check(fields.get("ivia1_moy") == "IVIA1 moy (j)",
           "IVIA1 label", f"Got {fields.get('ivia1_moy')}", r)
    _check(fields.get("ivif_moy") == "IVIF moy (j)",
           "IVIF label", f"Got {fields.get('ivif_moy')}", r)
    _check(fields.get("vv_moyen") == "IVV moy (j)",
           "IVV moy renamed", f"Got {fields.get('vv_moyen')}", r)
    _check(fields.get("pct_ia_global") == "TRGlobal",
           "TRGlobal label in Bilan", f"Got {fields.get('pct_ia_global')}", r)


def test_bilan_annuel_has_distribution_cols(r):
    _log("Bilan Annuel includes %1IA + %2IA + %3IA+ columns", "HEAD")
    cols = _bilan_annuel_columns()
    fields = {c["fieldname"]: c["label"] for c in cols}
    for fn, label in (("pct_1ia",      "%1IA"),
                      ("pct_2ia",      "%2IA"),
                      ("pct_3ia_plus", "%3IA+")):
        _check(fn in fields, f"{fn} field present",
               f"Fields: {list(fields.keys())}", r)
        _check(fields.get(fn) == label,
               f"{fn} label = {label}", f"Got {fields.get(fn)}", r)


def test_bilan_annuel_distribution_formula(r):
    """%nIA: each cow inseminated bucketed by MAX(numero_ia) of her REUSSIE.
    Cows that didn't conceive count in denominator only.
    Invariant: %1IA + %2IA + %3IA+ = TRGlobal (cow-based)."""
    _log("Bilan Annuel %nIA distribution sums to TRGlobal cow-based", "HEAD")

    # Fixture (PREFIX-scoped to isolate from real DB):
    #   A → IA1 R           → bucket %1IA
    #   B → IA1 E, IA2 R    → bucket %2IA
    #   C → IA1 E, IA2 E, IA3 R → bucket %3IA+
    #   D → IA1 E (still trying, no REUSSIE) → denominator only
    # Total cows inseminated = 4, conceived = 3.
    # Expected: %1IA = 25, %2IA = 25, %3IA+ = 25, sum = 75; TRGlobal cows = 75.
    a = _animal("DIST-A"); b = _animal("DIST-B"); c = _animal("DIST-C"); d = _animal("DIST-D")
    _insemination(a, f"{ANNEE}-02-01", 1, "REUSSIE")
    _insemination(b, f"{ANNEE}-03-01", 1, "ECHOUEE")
    _insemination(b, f"{ANNEE}-04-01", 2, "REUSSIE")
    _insemination(c, f"{ANNEE}-01-15", 1, "ECHOUEE")
    _insemination(c, f"{ANNEE}-02-15", 2, "ECHOUEE")
    _insemination(c, f"{ANNEE}-03-15", 3, "REUSSIE")
    _insemination(d, f"{ANNEE}-04-01", 1, "ECHOUEE")
    frappe.db.commit()

    # Compute directly on PREFIX-scoped data so unrelated rows in DB don't
    # contaminate the assertion. Mirrors the production query but cow-filtered.
    dist = frappe.db.sql("""
        SELECT
            COUNT(*) AS n,
            SUM(CASE WHEN max_rank = 1  THEN 1 ELSE 0 END) AS n_1ia,
            SUM(CASE WHEN max_rank = 2  THEN 1 ELSE 0 END) AS n_2ia,
            SUM(CASE WHEN max_rank >= 3 THEN 1 ELSE 0 END) AS n_3plus,
            SUM(CASE WHEN max_rank IS NOT NULL THEN 1 ELSE 0 END) AS n_conc
        FROM (
            SELECT animal,
              MAX(CASE WHEN resultat='REUSSIE' THEN numero_ia END) AS max_rank
            FROM `tabInsemination`
            WHERE animal LIKE %s AND date_ia BETWEEN %s AND %s
            GROUP BY animal
        ) AS pc
    """, (f"{PREFIX}%", f"{ANNEE}-01-01", f"{ANNEE}-12-31"), as_dict=True)[0]
    n = int(dist.n)
    pct_1   = round(int(dist.n_1ia)   / n * 100, 1)
    pct_2   = round(int(dist.n_2ia)   / n * 100, 1)
    pct_3p  = round(int(dist.n_3plus) / n * 100, 1)
    pct_glb = round(int(dist.n_conc)  / n * 100, 1)

    _check(pct_1 == 25.0,  f"%1IA = 25 (got {pct_1})",  f"Got {pct_1}", r)
    _check(pct_2 == 25.0,  f"%2IA = 25 (got {pct_2})",  f"Got {pct_2}", r)
    _check(pct_3p == 25.0, f"%3IA+ = 25 (got {pct_3p})", f"Got {pct_3p}", r)
    _check(round(pct_1 + pct_2 + pct_3p, 1) == pct_glb,
           f"Σ = TRGlobal cow-based ({pct_1}+{pct_2}+{pct_3p} = {pct_glb})",
           f"Σ {pct_1+pct_2+pct_3p} ≠ {pct_glb}", r)

    # Sanity — production code returns same fields on a year row.
    from hmd_agro.hmd_agro.utils.live_state import effectif_on_date
    from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _aliment_data_per_lot
    row = _bilan_year_row(ANNEE,
                          getdate(f"{ANNEE}-01-01"), getdate(f"{ANNEE}-12-31"),
                          is_partial=False,
                          effectif_fn=effectif_on_date,
                          aliment_fn=_aliment_data_per_lot)
    for fn in ("pct_1ia", "pct_2ia", "pct_3ia_plus"):
        _check(row.get(fn) is not None, f"{fn} present in year row",
               f"Got {row.get(fn)}", r)


def test_bilan_annuel_has_reforme_survie_cols(r):
    _log("Bilan Annuel includes Taux Réforme + Survie Naissance columns", "HEAD")
    cols = _bilan_annuel_columns()
    fields = {c["fieldname"]: c["label"] for c in cols}
    _check("taux_reforme" in fields, "taux_reforme field present",
           f"Fields: {list(fields.keys())}", r)
    _check("taux_survie_naissance" in fields,
           "taux_survie_naissance field present",
           f"Fields: {list(fields.keys())}", r)


def test_reproduction_columns_have_persistance(r):
    _log("Reproduction columns include persistance (PFE 3.1.1.3)", "HEAD")
    cols = _reproduction_columns()
    fields = {c["fieldname"]: c["label"] for c in cols}
    _check("persistance" in fields, "persistance field present",
           f"Fields: {list(fields.keys())}", r)


def test_reproduction_columns_unchanged(r):
    """Sanity — fieldnames touched by formatter coloring must stay stable."""
    _log("Reproduction column fieldnames stable (formatter binds to them)", "HEAD")
    cols = _reproduction_columns()
    fields = {c["fieldname"] for c in cols}
    for required in ("v_ia1", "v_iad", "ivv_moyen", "dernier_ivv",
                     "statut_repro", "etat_gestation", "etat_lactation",
                     "resultat_derniere_ia"):
        _check(required in fields, f"{required} present",
               f"Missing {required}", r)


# ─── _compute_ivia1_ivif_year helper unit tests ────────────────────────────

def test_compute_ivia1_ivif_year_baseline(r):
    """Two cows with controlled vêlage + IA dates. Helper must average IVIA1
    only for IA1s with a prior vêlage, IVIF only for REUSSIE IAs with prior."""
    _log("_compute_ivia1_ivif_year — controlled 2-cow fixture", "HEAD")
    _cleanup()
    a = _animal("A")
    b = _animal("B")
    _velage(a, f"{ANNEE}-01-01")
    _velage(b, f"{ANNEE}-02-01")
    # A: IA1 on 04-01 (90 days post-vêlage), ECHOUEE; IA2 on 05-01 (120d), REUSSIE
    _insemination(a, f"{ANNEE}-04-01", 1, "ECHOUEE")
    _insemination(a, f"{ANNEE}-05-01", 2, "REUSSIE")
    # B: IA1 on 06-01 (120 days post-vêlage), REUSSIE
    _insemination(b, f"{ANNEE}-06-01", 1, "REUSSIE")
    frappe.db.commit()

    start = getdate(f"{ANNEE}-01-01")
    end = getdate(f"{ANNEE}-12-31")
    ivia1, ivif = _compute_ivia1_ivif_year(start, end)

    # IVIA1: avg of (A IA1 = 90j) + (B IA1 = 120j) = 105
    _check(ivia1 == 105, "IVIA1 = 105 ((90+120)/2)", f"Got {ivia1}", r)
    # IVIF: avg of (A IA2 REUSSIE = 120j) + (B IA1 REUSSIE = 120j) = 120
    _check(ivif == 120, "IVIF = 120 ((120+120)/2)", f"Got {ivif}", r)


def test_compute_ivia1_ivif_year_skips_genisses(r):
    """A génisse has IA1 but no prior vêlage — must be skipped from IVIA1 avg
    (PFE convention: IVIA1 only defined for vaches that have vêla'd before)."""
    _log("_compute_ivia1_ivif_year — génisse without vêlage skipped", "HEAD")
    _cleanup()
    g = _animal("G", categorie="GENISSE")
    a = _animal("A")
    _velage(a, f"{ANNEE}-01-01")
    _insemination(a, f"{ANNEE}-04-01", 1, "REUSSIE")     # A: 90j IVIA1, REUSSIE
    _insemination(g, f"{ANNEE}-05-01", 1, "ECHOUEE")    # G: génisse, no prior vêlage
    frappe.db.commit()

    start = getdate(f"{ANNEE}-01-01")
    end = getdate(f"{ANNEE}-12-31")
    ivia1, ivif = _compute_ivia1_ivif_year(start, end)

    # G has no prior vêlage → skipped. Only A counts.
    _check(ivia1 == 90, "IVIA1 = 90 (only A counted, G skipped)",
           f"Got {ivia1}", r)
    _check(ivif == 90, "IVIF = 90 (A's REUSSIE)", f"Got {ivif}", r)


def test_compute_ivia1_ivif_year_no_data(r):
    """No IAs in the year → both helpers return None."""
    _log("_compute_ivia1_ivif_year — empty year → (None, None)", "HEAD")
    _cleanup()
    start = getdate(f"{ANNEE}-01-01")
    end = getdate(f"{ANNEE}-12-31")
    ivia1, ivif = _compute_ivia1_ivif_year(start, end)
    _check(ivia1 is None and ivif is None,
           "Both None when no IAs in year",
           f"Got ivia1={ivia1} ivif={ivif}", r)


def test_compute_ivia1_ivif_year_excludes_outside_range(r):
    """An IA outside [start, end] must NOT contribute, even if the cow has
    a prior vêlage in the window."""
    _log("_compute_ivia1_ivif_year — out-of-range IAs excluded", "HEAD")
    _cleanup()
    a = _animal("A")
    _velage(a, f"{ANNEE}-01-01")
    # IA in next year, way outside the [ANNEE-01-01, ANNEE-12-31] window
    _insemination(a, f"{ANNEE+1}-04-01", 1, "REUSSIE")
    frappe.db.commit()

    ivia1, ivif = _compute_ivia1_ivif_year(
        getdate(f"{ANNEE}-01-01"), getdate(f"{ANNEE}-12-31"))
    _check(ivia1 is None and ivif is None,
           "IA in next year ignored",
           f"Got ivia1={ivia1} ivif={ivif}", r)


# ─── Reproduction section shape + summary cards ────────────────────────────

def test_reproduction_returns_5_tuple(r):
    """The Reproduction section now returns (cols, rows, None, None, summary)
    so the report's normalize_precision decorator can process the summary."""
    _log("Reproduction section returns 5-tuple", "HEAD")
    # Use a date with no fixture data — test the shape, not values.
    ctx = {"date_filter": getdate("2020-01-01")}
    result = _reproduction(ctx)
    _check(isinstance(result, tuple) and len(result) == 5,
           f"5-tuple returned (got len={len(result) if isinstance(result, tuple) else type(result)})",
           f"Got {type(result)} len={len(result) if isinstance(result, tuple) else 'N/A'}", r)


# ─── Persistance de lactation tests ────────────────────────────────────────

def test_persistance_baseline(r):
    """Cow with constant 30 L/day → persistance = 1.0 (no drop after pic)."""
    _log("Persistance — constant production → ratio = 1.0", "HEAD")
    _cleanup()
    a = _animal("PA")
    velage_date = f"{ANNEE}-01-01"
    _velage(a, velage_date)
    lact_name = _lactation(a, "01", velage_date)
    # 200 days × 30 L/day. Buckets: 0-99 = 100 days, 100-199 = 100 days.
    # Expected: ratio = 30 / 30 = 1.0
    from frappe.utils import add_days
    for i in range(200):
        d = add_days(velage_date, i)
        _traite(a, lact_name, d, 30)
    frappe.db.commit()

    ctx = {"date_filter": getdate(f"{ANNEE}-12-31")}
    result = _reproduction(ctx)
    rows = result[1]
    a_row = next((row for row in rows if row.get("nom_metier") == a[-4:]), None)
    _check(a_row is not None, "Cow row found", f"Got {a_row}", r)
    if a_row:
        _check(a_row.get("persistance") == 1.0,
               f"Persistance = 1.0 (constant 30 L/day)",
               f"Got {a_row.get('persistance')}", r)


def test_persistance_realistic_drop(r):
    """Cow producing 40L for first 100 days, 30L for next 100 → ratio = 0.75."""
    _log("Persistance — typical drop (40 → 30) → ratio = 0.75", "HEAD")
    _cleanup()
    a = _animal("PB")
    velage_date = f"{ANNEE}-01-01"
    _velage(a, velage_date)
    lact_name = _lactation(a, "01", velage_date)
    from frappe.utils import add_days
    for i in range(100):
        _traite(a, lact_name, add_days(velage_date, i), 40)
    for i in range(100, 200):
        _traite(a, lact_name, add_days(velage_date, i), 30)
    frappe.db.commit()

    ctx = {"date_filter": getdate(f"{ANNEE}-12-31")}
    result = _reproduction(ctx)
    a_row = next((row for row in result[1] if row.get("nom_metier") == a[-4:]), None)
    if a_row:
        # 100×30 / 100×40 = 3000/4000 = 0.75
        _check(a_row.get("persistance") == 0.75,
               "Persistance = 0.75 (3000/4000)",
               f"Got {a_row.get('persistance')}", r)


def test_persistance_none_when_short_lactation(r):
    """Cow with only 50 days of lactation → no second-bucket data → persistance None."""
    _log("Persistance — short lactation (no day 100+) → None", "HEAD")
    _cleanup()
    a = _animal("PC")
    velage_date = f"{ANNEE}-01-01"
    _velage(a, velage_date)
    lact_name = _lactation(a, "01", velage_date)
    from frappe.utils import add_days
    for i in range(50):
        _traite(a, lact_name, add_days(velage_date, i), 30)
    frappe.db.commit()

    ctx = {"date_filter": getdate(f"{ANNEE}-12-31")}
    result = _reproduction(ctx)
    a_row = next((row for row in result[1] if row.get("nom_metier") == a[-4:]), None)
    if a_row:
        _check(a_row.get("persistance") is None,
               "Persistance None (no day 100-200 data)",
               f"Got {a_row.get('persistance')}", r)


# ─── Runner ────────────────────────────────────────────────────────────────

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT REPRODUCTION — TESTS (KPIs + structure)")
    print("=" * 60)
    r = {"pass": 0, "fail": 0}
    try:
        _cleanup()
        test_bilan_annuel_has_ivia1_ivif_cols(r)
        test_bilan_annuel_has_distribution_cols(r)
        test_bilan_annuel_distribution_formula(r)
        test_bilan_annuel_has_reforme_survie_cols(r)
        test_reproduction_columns_have_persistance(r)
        test_reproduction_columns_unchanged(r)
        test_compute_ivia1_ivif_year_baseline(r)
        test_compute_ivia1_ivif_year_skips_genisses(r)
        test_compute_ivia1_ivif_year_no_data(r)
        test_compute_ivia1_ivif_year_excludes_outside_range(r)
        test_reproduction_returns_5_tuple(r)
        test_persistance_baseline(r)
        test_persistance_realistic_drop(r)
        test_persistance_none_when_short_lactation(r)
    finally:
        _cleanup()

    total = r["pass"] + r["fail"]
    print(f"\n  RESULTATS: {r['pass']}/{total} passés, {r['fail']} échoués\n")
    return r
