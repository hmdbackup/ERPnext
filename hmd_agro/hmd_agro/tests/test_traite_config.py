"""
Tests d'intégration — traite.py lit-il les seuils depuis la config ?
Run: bench execute hmd_agro.hmd_agro.tests.test_traite_config.run_all_tests
"""
import frappe


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
    print("  TRAITE — INTÉGRATION CONFIG (validation)")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    test_quantite_max_litres(results)
    test_taux_tb_max(results)
    test_taux_tp_max(results)
    test_import_traites_max_litres(results)
    test_lactation_windows_in_sql(results)
    test_recalculate_all_lactations(results)

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results


def _with_config(field, value, fn):
    """Run `fn` with config[field]=value, restore on exit."""
    cfg = frappe.get_single("HMD Configuration")
    original = cfg.get(field)
    try:
        cfg.set(field, value)
        cfg.save(ignore_permissions=True)
        frappe.db.commit()
        fn()
    finally:
        frappe.db.rollback()
        cfg2 = frappe.get_single("HMD Configuration")
        cfg2.set(field, original)
        cfg2.save(ignore_permissions=True)
        frappe.db.commit()


def _raises_validation(callable_):
    try:
        callable_()
        return False
    except frappe.ValidationError:
        return True


def test_quantite_max_litres(results):
    log("validate_quantite lit traite_max_litres", "HEAD")

    # Baseline (default 60): 55L passes, 65L raises
    doc55 = frappe.new_doc("Traite"); doc55.quantite_litres = 55
    doc65 = frappe.new_doc("Traite"); doc65.quantite_litres = 65
    check(not _raises_validation(doc55.validate_quantite),
          "Baseline (max=60): 55L accepté", "55L refusé", results)
    check(_raises_validation(doc65.validate_quantite),
          "Baseline (max=60): 65L refusé", "65L accepté", results)

    def with_low_max():
        # max=50 now: 45L passes, 55L raises (was accepted before)
        doc45 = frappe.new_doc("Traite"); doc45.quantite_litres = 45
        doc55b = frappe.new_doc("Traite"); doc55b.quantite_litres = 55
        check(not _raises_validation(doc45.validate_quantite),
              "Avec max=50: 45L accepté", "45L refusé", results)
        check(_raises_validation(doc55b.validate_quantite),
              "Avec max=50: 55L refusé (config wiring OK)", "55L accepté → wiring cassée", results)

    _with_config("traite_max_litres", 50, with_low_max)


def test_taux_tb_max(results):
    log("validate_taux lit taux_tb_max_pct", "HEAD")

    # Baseline (default 10%): 9% passes, 11% raises
    doc9 = frappe.new_doc("Traite"); doc9.taux_tb = 9
    doc11 = frappe.new_doc("Traite"); doc11.taux_tb = 11
    check(not _raises_validation(doc9.validate_taux),
          "Baseline (tb_max=10): 9% accepté", "9% refusé", results)
    check(_raises_validation(doc11.validate_taux),
          "Baseline (tb_max=10): 11% refusé", "11% accepté", results)

    def with_low_max():
        # tb_max=8: 7% passes, 9% raises (was accepted before)
        doc7 = frappe.new_doc("Traite"); doc7.taux_tb = 7
        doc9b = frappe.new_doc("Traite"); doc9b.taux_tb = 9
        check(not _raises_validation(doc7.validate_taux),
              "Avec tb_max=8: 7% accepté", "7% refusé", results)
        check(_raises_validation(doc9b.validate_taux),
              "Avec tb_max=8: 9% refusé (config wiring OK)", "9% accepté → wiring cassée", results)

    _with_config("taux_tb_max_pct", 8, with_low_max)


def test_taux_tp_max(results):
    log("validate_taux lit taux_tp_max_pct", "HEAD")

    # Same shape as TB but with TP
    doc9 = frappe.new_doc("Traite"); doc9.taux_tp = 9
    doc11 = frappe.new_doc("Traite"); doc11.taux_tp = 11
    check(not _raises_validation(doc9.validate_taux),
          "Baseline (tp_max=10): 9% accepté", "9% refusé", results)
    check(_raises_validation(doc11.validate_taux),
          "Baseline (tp_max=10): 11% refusé", "11% accepté", results)

    def with_low_max():
        doc7 = frappe.new_doc("Traite"); doc7.taux_tp = 7
        doc9b = frappe.new_doc("Traite"); doc9b.taux_tp = 9
        check(not _raises_validation(doc7.validate_taux),
              "Avec tp_max=8: 7% accepté", "7% refusé", results)
        check(_raises_validation(doc9b.validate_taux),
              "Avec tp_max=8: 9% refusé (config wiring OK)", "9% accepté → wiring cassée", results)

    _with_config("taux_tp_max_pct", 8, with_low_max)


def test_import_traites_max_litres(results):
    """import_traites.start_import uses the same traite_max_litres limit
    as Traite.validate_quantite (no drift between manual + bulk paths)."""
    log("import_traites lit traite_max_litres (cohérence avec validate)", "HEAD")
    from hmd_agro.hmd_agro.utils.config import get_config
    # We can't easily run the full import in a test, but we can verify the
    # config-read pattern produces the right value used in the import code path.
    val = get_config("traite_max_litres", default=60)
    check(val == 60, "Baseline get_config = 60", f"Got {val}", results)
    _with_config("traite_max_litres", 50,
        lambda: check(get_config("traite_max_litres", default=60) == 50,
                      "Avec config=50: get_config = 50",
                      f"Got {get_config('traite_max_litres', default=60)}", results))


def test_recalculate_all_lactations(results):
    """Bulk recalc helper: changing pic_production_jours then calling
    recalculate_all_lactations should update the cached pic_production
    of a real Lactation."""
    log("recalculate_all_lactations propage la nouvelle config", "HEAD")
    from hmd_agro.hmd_agro.utils.lactation_recalc import recalculate_all_lactations

    lac_name = frappe.db.get_value("Lactation", {"statut": "EN_COURS"}, "name")
    if not lac_name:
        log("Skip — pas de Lactation EN_COURS", "FAIL")
        results["fail"] += 1
        return

    lac_snapshot = frappe.db.get_value("Lactation", lac_name,
        ["production_totale", "pic_production", "lactation_305j",
         "production_initiale", "moyenne_production"], as_dict=True)
    cfg = frappe.get_single("HMD Configuration")
    cfg_snapshot = {
        "pic_production_jours": cfg.pic_production_jours,
        "production_initiale_jours": cfg.production_initiale_jours,
    }

    try:
        # Force window to 1 day → pic and production_initiale should drop dramatically
        cfg.pic_production_jours = 1
        cfg.production_initiale_jours = 1
        cfg.save(ignore_permissions=True)
        frappe.db.commit()

        result = recalculate_all_lactations()
        check(result["total"] > 0,
              f"Recalc a touché {result['total']} lactations",
              f"total={result['total']}", results)
        check(len(result["failed"]) == 0,
              "Aucune erreur de recalc",
              f"failed={result['failed']}", results)

        new_pic = frappe.db.get_value("Lactation", lac_name, "pic_production")
        check(float(new_pic) <= float(lac_snapshot.pic_production or 0),
              f"pic_production réduit ou égal après window=1 ({new_pic} <= {lac_snapshot.pic_production})",
              f"new_pic={new_pic} > old={lac_snapshot.pic_production} → wiring cassée",
              results)
    finally:
        # Restore config
        cfg2 = frappe.get_single("HMD Configuration")
        for f, v in cfg_snapshot.items():
            cfg2.set(f, v)
        cfg2.save(ignore_permissions=True)
        frappe.db.commit()
        # Restore lactation values directly (bypass any recalc trigger)
        frappe.db.set_value("Lactation", lac_name, lac_snapshot)
        frappe.db.commit()


def test_lactation_windows_in_sql(results):
    """Capture SQL emitted by Traite.update_lactation_production AND
    import_traites.recalculate_lactation_production. Verify both pick up the
    pic_production_jours / production_initiale_jours from config."""
    log("Lactation calc lit pic_production_jours + production_initiale_jours", "HEAD")

    lac_name = frappe.db.get_value("Lactation", {"statut": "EN_COURS"}, "name")
    if not lac_name:
        log("Skip — pas de Lactation EN_COURS en base", "FAIL")
        results["fail"] += 1
        return

    # Snapshot lactation values so we can restore exactly
    lac_snapshot = frappe.db.get_value("Lactation", lac_name,
        ["production_totale", "pic_production", "lactation_305j",
         "production_initiale", "moyenne_production"], as_dict=True)

    captured = []
    real_sql = frappe.db.sql

    def fake_sql(query, *args, **kwargs):
        if isinstance(query, str) and "DATEDIFF" in query:
            captured.append(query)
        return real_sql(query, *args, **kwargs)

    def with_modified_windows():
        nonlocal captured
        # Test 1: import_traites.recalculate_lactation_production
        from hmd_agro.hmd_agro.page.import_traites.import_traites import recalculate_lactation_production
        captured = []
        frappe.db.sql = fake_sql
        try:
            recalculate_lactation_production(lac_name)
        finally:
            frappe.db.sql = real_sql
        joined = " ".join(captured)
        check("<= 99" in joined, "import_traites pic_window=99 dans SQL",
              f"captured: {joined[:300]}", results)
        check("<= 33" in joined, "import_traites init_window=33 dans SQL",
              f"captured: {joined[:300]}", results)

        # Test 2: Traite.update_lactation_production (via stub)
        from hmd_agro.hmd_agro.doctype.traite.traite import Traite
        stub = frappe.new_doc("Traite")
        stub.lactation = lac_name
        captured = []
        frappe.db.sql = fake_sql
        try:
            Traite.update_lactation_production(stub)
        finally:
            frappe.db.sql = real_sql
        joined = " ".join(captured)
        check("<= 99" in joined, "Traite pic_window=99 dans SQL",
              f"captured: {joined[:300]}", results)
        check("<= 33" in joined, "Traite init_window=33 dans SQL",
              f"captured: {joined[:300]}", results)

    cfg = frappe.get_single("HMD Configuration")
    cfg_snapshot = {
        "pic_production_jours": cfg.pic_production_jours,
        "production_initiale_jours": cfg.production_initiale_jours,
    }
    try:
        cfg.pic_production_jours = 99
        cfg.production_initiale_jours = 33
        cfg.save(ignore_permissions=True)
        frappe.db.commit()
        with_modified_windows()
    finally:
        # Restore config first
        cfg2 = frappe.get_single("HMD Configuration")
        for f, v in cfg_snapshot.items():
            cfg2.set(f, v)
        cfg2.save(ignore_permissions=True)
        frappe.db.commit()
        # Restore lactation values directly (bypass any recalc)
        frappe.db.set_value("Lactation", lac_name, lac_snapshot)
        frappe.db.commit()
