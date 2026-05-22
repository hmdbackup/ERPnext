"""Run every test suite and audit script and report pass/fail counts.
One-shot — used after a multi-day cleanup to confirm green state."""
import importlib
import traceback


# (module path, function name) — covers all tests/ + setup audits
SUITES = [
    # Our new / refactored
    ("hmd_agro.hmd_agro.tests.test_feed_correction", "run"),
    ("hmd_agro.hmd_agro.tests.test_correction_propagates_to_report", "run"),
    ("hmd_agro.hmd_agro.tests.test_feed_distribution", "run"),
    ("hmd_agro.hmd_agro.tests.test_cost_flow", "run"),
    ("hmd_agro.hmd_agro.tests.test_stock_integration", "run"),
    ("hmd_agro.hmd_agro.tests.test_semence_dual_write", "run"),
    # Reports
    ("hmd_agro.hmd_agro.tests.test_indicateurs_report", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_alimentation_report", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_reproduction_report", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_effectif_report", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_production_lot_report", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_allotement_report", "run_all_tests"),
    # Domain
    ("hmd_agro.hmd_agro.tests.test_alert_system", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_traitement_module", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_full_flow", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_cascade_delete", "run_all_tests"),
    # Config
    ("hmd_agro.hmd_agro.tests.test_hmd_config", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_alerte_config", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_tarissement_config", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_velage_prevue_config", "run_all_tests"),
    ("hmd_agro.hmd_agro.tests.test_traite_config", "run_all_tests"),
    # Audits
    ("hmd_agro.hmd_agro.setup.flow_audit", "run"),
]


def run():
    print("\n" + "═" * 76)
    print("  FULL TEST SWEEP")
    print("═" * 76)
    total_pass = 0
    total_fail = 0
    suite_results = []

    for mod_path, fname in SUITES:
        short = mod_path.rsplit(".", 1)[-1]
        try:
            mod = importlib.import_module(mod_path)
            fn = getattr(mod, fname, None)
            if fn is None:
                suite_results.append((short, "?", "?", "(no run fn)"))
                continue
            r = fn() or {}
            p = r.get("pass", 0)
            f = r.get("fail", 0)
            total_pass += p
            total_fail += f
            verdict = "✓" if f == 0 else "✗"
            suite_results.append((short, p, f, verdict))
        except Exception as e:
            err = type(e).__name__
            suite_results.append((short, 0, 1, f"CRASH {err}"))
            total_fail += 1

    print("\n" + "═" * 76)
    print(f"  {'Suite':45s} {'pass':>6} {'fail':>6}  status")
    print("  " + "─" * 72)
    for name, p, f, v in suite_results:
        print(f"  {name:45s} {p:>6} {f:>6}  {v}")
    print("  " + "─" * 72)
    print(f"  {'TOTAL':45s} {total_pass:>6} {total_fail:>6}")
    print("═" * 76)
    return {"pass": total_pass, "fail": total_fail}
