"""
Tests unitaires — HMD Configuration
Run: bench execute hmd_agro.hmd_agro.tests.test_hmd_config.run_all_tests
"""
import frappe

from hmd_agro.hmd_agro.utils.config import get_config

# These are the documented constants from the codebase. The Single's defaults
# (and the patch that initializes it) MUST match this table — otherwise an
# inadvertent default change would silently shift behavior across the app.
EXPECTED_DEFAULTS = {
    "chaleur_genisse_age_mois": 14,
    "chaleur_post_velage_jours": 45,
    "verification_j21_jours": 18,
    "tarissement_advance_jours": 7,
    "velage_advance_jours": 15,
    "delvo_advance_jours": 1,
    "chaleur_cycle_jours": 21,
    "alerte_lead_jours": 2,
    "tarissement_window_jours": 60,
    "traite_max_litres": 60,
    "production_initiale_jours": 60,
    "pic_production_jours": 150,
    "taux_tb_max_pct": 10,
    "taux_tp_max_pct": 10,
    "dim_fv_max_multi": 30,
    "dim_thp_max": 120,
    "dim_hp_max": 240,
    "dim_mp_max": 305,
    "dim_primipare_cap": 300,
    "last_third_pct": 66.7,
    "production_drop_alert_pct": -15,
}


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
    print("  HMD CONFIGURATION — TESTS UNITAIRES")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    test_doctype_exists(results)
    test_defaults_match_expected(results)
    test_get_config_falls_back(results)
    test_validate_dim_monotonicity(results)
    test_validate_tarissement_advance_window(results)
    test_validate_alerte_lead_cap(results)
    test_boot_session_payload(results)

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results


def test_doctype_exists(results):
    log("Doctype HMD Configuration existe", "HEAD")
    exists = frappe.db.exists("DocType", "HMD Configuration")
    check(bool(exists), "Doctype trouvé", "Doctype manquant", results)


def test_defaults_match_expected(results):
    log("Valeurs par défaut == constantes documentées", "HEAD")
    doc = frappe.get_single("HMD Configuration")
    for field, expected in EXPECTED_DEFAULTS.items():
        actual = doc.get(field)
        # Float comparison tolerant
        if isinstance(expected, float) or isinstance(actual, float):
            ok = actual is not None and abs(float(actual) - float(expected)) < 0.001
        else:
            ok = actual == expected
        check(ok, f"{field} = {expected}", f"{field}: attendu {expected}, obtenu {actual!r}", results)


def test_get_config_falls_back(results):
    log("get_config() retourne le default si champ absent", "HEAD")
    val = get_config("__champ_inexistant__", default=42)
    check(val == 42, "Champ absent → default 42", f"Got {val!r}", results)

    val = get_config("verification_j21_jours", default=999)
    check(val == 18, "Champ existant → valeur réelle (18, pas 999)", f"Got {val!r}", results)


def test_validate_dim_monotonicity(results):
    log("validate() rejette des bornes DIM non monotones", "HEAD")
    original_thp = frappe.db.get_single_value("HMD Configuration", "dim_thp_max")
    try:
        doc = frappe.get_single("HMD Configuration")
        doc.dim_thp_max = doc.dim_hp_max + 10  # break monotonicity
        try:
            doc.save(ignore_permissions=True)
            check(False, "", "save() aurait dû lever ValidationError", results)
        except frappe.ValidationError:
            check(True, "ValidationError levée pour bornes non monotones", "", results)
    finally:
        # Use a fresh doc — `doc` after failed save may be in a dirty state
        frappe.db.rollback()
        doc2 = frappe.get_single("HMD Configuration")
        doc2.dim_thp_max = original_thp
        doc2.save(ignore_permissions=True)
        frappe.db.commit()


def _try_save_with(field, value, results, label):
    """Attempt to save HMD Configuration with field=value, expect ValidationError."""
    cfg = frappe.get_single("HMD Configuration")
    original = cfg.get(field)
    try:
        cfg.set(field, value)
        try:
            cfg.save(ignore_permissions=True)
            check(False, "", f"{label}: save aurait dû lever ValidationError", results)
        except frappe.ValidationError:
            check(True, label, "", results)
    finally:
        frappe.db.rollback()
        cfg2 = frappe.get_single("HMD Configuration")
        cfg2.set(field, original)
        cfg2.save(ignore_permissions=True)
        frappe.db.commit()


def test_validate_tarissement_advance_window(results):
    log("validate_tarissement_advance_window — advance ≤ window", "HEAD")
    # advance default 7, window default 60. Try setting advance = 90 → reject
    _try_save_with("tarissement_advance_jours", 90, results,
                   "advance=90 (> window=60) → rejeté")


def test_validate_alerte_lead_cap(results):
    log("validate_alerte_lead_cap — alerte_lead_jours ≤ 7", "HEAD")
    _try_save_with("alerte_lead_jours", 8, results,
                   "lead=8 (> 7) → rejeté")
    _try_save_with("alerte_lead_jours", 30, results,
                   "lead=30 (>> 7) → rejeté")


def test_boot_session_payload(results):
    log("boot_session expose le sous-ensemble JS", "HEAD")
    from hmd_agro.boot import boot_session, JS_FIELDS
    bootinfo = {}
    boot_session(bootinfo)
    cfg = bootinfo.get("hmd_config", {})
    check("hmd_config" in bootinfo, "bootinfo.hmd_config présent", "Clé manquante", results)
    for field in JS_FIELDS:
        check(field in cfg, f"  {field} dans payload", f"  {field} absent", results)
