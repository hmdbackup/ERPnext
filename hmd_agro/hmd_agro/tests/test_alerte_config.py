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
    "verification_j21_jours":    8999,   # j50 must be > j21 (cross-field validation)
    "verification_j50_jours":    9000,
    "tarissement_advance_jours": 60,     # ≤ tarissement_window_jours default 60
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
    test_reporter_alerte_uses_chaleur_cycle(results)
    test_a_revoir_alerte_uses_lead_jours(results)
    test_delvo_encore_contamine_regenerates(results)

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
            (alerte_mod._generate_j21_alerts,          ("d", -8999), "verification_j21_jours"),
            (alerte_mod._generate_j50_alerts,          ("d", -9000), "verification_j50_jours"),
            (alerte_mod._generate_tarissement_alerts,  ("d", 60),    "tarissement_advance_jours"),
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


def _create_test_alert(animal_name, type_alerte, statut):
    """Insert a temporary Alerte for endpoint tests. Returns its name."""
    from frappe.utils import today
    doc = frappe.get_doc({
        "doctype": "Alerte",
        "animal": animal_name,
        "type_alerte": type_alerte,
        "date_alerte": today(),
        "raison": "TEST INTEGRATION CONFIG",
        "statut": statut,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.name


def _delete_alert(name):
    if name and frappe.db.exists("Alerte", name):
        frappe.delete_doc("Alerte", name, force=True, ignore_permissions=True)
        frappe.db.commit()


def _set_config(field, value):
    cfg = frappe.get_single("HMD Configuration")
    cfg.set(field, value)
    cfg.save(ignore_permissions=True)
    frappe.db.commit()


def test_reporter_alerte_uses_chaleur_cycle(results):
    """reporter_alerte schedules the follow-up alert today + chaleur_cycle_jours."""
    log("reporter_alerte lit chaleur_cycle_jours", "HEAD")
    from frappe.utils import add_days, getdate, today

    animal_name = frappe.db.get_value("Animal", {"statut": "ACTIF", "categorie": "GENISSE"}, "name")
    if not animal_name:
        log("Skip — pas de génisse ACTIVE", "FAIL")
        results["fail"] += 1
        return

    cfg = frappe.get_single("HMD Configuration")
    original = cfg.chaleur_cycle_jours
    test_alert = None
    new_alert = None
    try:
        test_alert = _create_test_alert(animal_name, "CHALEUR_GENISSE", "CONFIRMEE")
        _set_config("chaleur_cycle_jours", 30)

        result = alerte_mod.reporter_alerte(test_alert, "MALADE")
        new_alert = result.get("new_alert")

        new_date = frappe.db.get_value("Alerte", new_alert, "date_alerte")
        expected = getdate(add_days(getdate(today()), 30))
        check(getdate(new_date) == expected,
              f"Nouvelle alerte: date_alerte = today+30 = {expected}",
              f"Got {new_date} (config wiring cassée?)", results)
    finally:
        _delete_alert(new_alert)
        _delete_alert(test_alert)
        _set_config("chaleur_cycle_jours", original)


def test_delvo_encore_contamine_regenerates(results):
    """After 'encore contaminée', the next generate_alerts must produce a
    fresh DELVO alert (the old TRAITEE-blocked behavior was a bug)."""
    log("delvo_encore_contamine: nouvelle DELVO créée après extension", "HEAD")
    from frappe.utils import add_days, today

    animal_name = frappe.db.get_value("Animal", {"statut": "ACTIF"}, "name")
    if not animal_name:
        log("Skip — pas d'animal ACTIF", "FAIL")
        results["fail"] += 1
        return

    test_alert = None
    snapshot_attente = frappe.db.get_value(
        "Animal", animal_name,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)

    try:
        # Setup: animal under withdrawal ending today + 1
        frappe.db.set_value("Animal", animal_name, {
            "attente_lait_active": 1,
            "date_fin_attente_lait": add_days(today(), 1),
        })
        # Old DELVO alert that the operator will defer
        test_alert = _create_test_alert(animal_name, "DELVO", "NOUVELLE")

        # Operator clicks "Encore contaminée" with 3 days
        result = alerte_mod.delvo_encore_contamine(test_alert, 3)
        check(result.get("status") == "ok", "delvo_encore_contamine OK", str(result), results)

        # Old alert should now be REPORTEE (was TRAITEE before fix)
        old_status = frappe.db.get_value("Alerte", test_alert, "statut")
        check(old_status == "REPORTEE",
              f"Ancienne alerte → REPORTEE", f"Got {old_status}", results)

        # Animal date_fin pushed back to today + 3
        new_date = frappe.db.get_value("Animal", animal_name, "date_fin_attente_lait")
        from frappe.utils import getdate
        expected_date = getdate(add_days(today(), 3))
        check(getdate(new_date) == expected_date,
              f"date_fin_attente_lait = today+3 = {expected_date}",
              f"Got {new_date}", results)

        # Trigger generator — should NOW create a new NOUVELLE DELVO alert
        # (REPORTEE doesn't block; default delvo_advance_jours=1, animal date is today+3,
        # so we need to also fake-bump the cutoff or set advance high enough).
        # Simplest: temporarily set delvo_advance_jours = 5 so today+3 ≤ today+5.
        cfg = frappe.get_single("HMD Configuration")
        original_advance = cfg.delvo_advance_jours
        try:
            cfg.delvo_advance_jours = 5
            cfg.save(ignore_permissions=True)
            frappe.db.commit()

            alerte_mod._generate_delvo_alerts()
            new_alert = frappe.db.exists("Alerte", {
                "animal": animal_name, "type_alerte": "DELVO",
                "statut": "NOUVELLE", "name": ["!=", test_alert],
            })
            check(bool(new_alert),
                  "Nouvelle alerte DELVO NOUVELLE créée (REPORTEE n'a pas bloqué)",
                  "Aucune nouvelle alerte → REPORTEE bloque encore (régression)",
                  results)
            if new_alert:
                _delete_alert(new_alert)
        finally:
            cfg2 = frappe.get_single("HMD Configuration")
            cfg2.delvo_advance_jours = original_advance
            cfg2.save(ignore_permissions=True)
            frappe.db.commit()
    finally:
        _delete_alert(test_alert)
        frappe.db.set_value("Animal", animal_name, snapshot_attente)
        frappe.db.commit()


def test_a_revoir_alerte_uses_lead_jours(results):
    """a_revoir_alerte affiche l'alerte (nb_jours - alerte_lead_jours) jours plus tôt."""
    log("a_revoir_alerte lit alerte_lead_jours", "HEAD")
    from frappe.utils import add_days, getdate, today

    animal_name = frappe.db.get_value("Animal", {"statut": "ACTIF"}, "name")
    if not animal_name:
        log("Skip — pas d'animal ACTIF", "FAIL")
        results["fail"] += 1
        return

    cfg = frappe.get_single("HMD Configuration")
    original = cfg.alerte_lead_jours
    test_alert = None
    new_alert = None
    try:
        test_alert = _create_test_alert(animal_name, "VERIFICATION_J21", "NOUVELLE")
        _set_config("alerte_lead_jours", 5)

        # nb_jours=20, lead=5 → display_date = today + (20 - 5) = today + 15
        result = alerte_mod.a_revoir_alerte(test_alert, 20)
        new_alert = result.get("new_alert")

        new_date = frappe.db.get_value("Alerte", new_alert, "date_alerte")
        expected = getdate(add_days(getdate(today()), 15))
        check(getdate(new_date) == expected,
              f"Nouvelle alerte: date_alerte = today+15 (nb_jours=20 - lead=5) = {expected}",
              f"Got {new_date} (config wiring cassée?)", results)
    finally:
        _delete_alert(new_alert)
        _delete_alert(test_alert)
        _set_config("alerte_lead_jours", original)
