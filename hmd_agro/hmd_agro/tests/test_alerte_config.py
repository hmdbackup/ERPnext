"""
Tests d'intégration — alerte.py lit-il correctement chaque champ de la config ?
Run: bench execute hmd_agro.hmd_agro.tests.test_alerte_config.run_all_tests

Approche : monkey-patch `add_days` et `add_months` dans le module alerte pour
capturer la valeur passée. Les valeurs extrêmes choisies pour la config font
qu'aucun animal ne correspond aux requêtes — donc aucune Alerte créée.
"""
import frappe

from hmd_agro.hmd_agro.doctype.alerte import alerte as alerte_mod


# Extreme values: lookbacks far enough in the past, advances far enough in the
# future, that no real animal falls into the resulting cutoff window.
EXTREME = {
    "chaleur_genisse_age_mois":  240,    # 20 years
    "chaleur_post_velage_jours": 9000,   # ~25 years
    "verification_j21_jours":    9000,
    "verification_j50_jours":    9000,
    "tarissement_advance_jours": 9000,   # cutoff today + 9000 days → no real date_tarissement matches
    "velage_advance_jours":      9000,
    "delvo_advance_jours":       9000,
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
    print("  ALERTE — INTÉGRATION CONFIG")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    test_each_generator_reads_its_config(results)

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results


def test_each_generator_reads_its_config(results):
    log("Chaque _generate_* lit sa propre clé de config", "HEAD")

    captured = []
    real_add_months = alerte_mod.add_months
    real_add_days = alerte_mod.add_days

    def fake_add_months(date, n):
        captured.append(("m", n))
        return real_add_months(date, n)

    def fake_add_days(date, n):
        captured.append(("d", n))
        return real_add_days(date, n)

    cfg = frappe.get_single("HMD Configuration")
    snapshot = {f: cfg.get(f) for f in EXTREME}

    try:
        for f, v in EXTREME.items():
            cfg.set(f, v)
        cfg.save(ignore_permissions=True)
        frappe.db.commit()

        alerte_mod.add_months = fake_add_months
        alerte_mod.add_days = fake_add_days

        # Each generator: clear captured, call, verify the expected (sign, value) tuple is present
        cases = [
            (alerte_mod._generate_genisse_alerts,      ("m", -240),  "chaleur_genisse_age_mois"),
            (alerte_mod._generate_post_velage_alerts,  ("d", -9000), "chaleur_post_velage_jours"),
            (alerte_mod._generate_j21_alerts,          ("d", -9000), "verification_j21_jours"),
            (alerte_mod._generate_j50_alerts,          ("d", -9000), "verification_j50_jours"),
            (alerte_mod._generate_tarissement_alerts,  ("d", 9000),  "tarissement_advance_jours"),
            (alerte_mod._generate_velage_alerts,       ("d", 9000),  "velage_advance_jours"),
            (alerte_mod._generate_delvo_alerts,        ("d", 9000),  "delvo_advance_jours"),
        ]
        for fn, expected_call, field in cases:
            captured.clear()
            fn()
            check(expected_call in captured,
                  f"{fn.__name__} lit {field} → {expected_call}",
                  f"{fn.__name__} : attendu {expected_call} dans captured={captured}",
                  results)
    finally:
        alerte_mod.add_months = real_add_months
        alerte_mod.add_days = real_add_days
        frappe.db.rollback()  # undo any test alerts that managed to insert
        cfg2 = frappe.get_single("HMD Configuration")
        for f, v in snapshot.items():
            cfg2.set(f, v)
        cfg2.save(ignore_permissions=True)
        frappe.db.commit()
