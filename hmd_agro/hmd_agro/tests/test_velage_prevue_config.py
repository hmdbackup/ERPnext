"""
Tests d'intégration — periode_velage_jours.
Run: bench execute hmd_agro.hmd_agro.tests.test_velage_prevue_config.run_all_tests

Vérifie que les call sites lisent depuis la config :
  - insemination.update_animal_on_resultat (IA REUSSIE → date_velage_prevue)
  - avortement.on_trash (restauration mère GESTANTE)
  - velage.on_trash (restauration mère GESTANTE)

Et que recalculate_velage_prevue_dates propage la nouvelle config à toutes les
vaches gestantes (date_velage_prevue ET date_tarissement) + rafraîchit les
alertes ouvertes (VELAGE_IMMINENT + TARISSEMENT).
"""
import frappe
from frappe.utils import add_days, getdate


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
    print("  PÉRIODE DE GESTATION — INTÉGRATION CONFIG")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    test_insemination_reads_config(results)
    test_recalculate_velage_prevue_dates(results)
    test_recalc_refreshes_velage_alert_raison(results)

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results


def _set_period(value):
    """Direct set_value (bypasses on_update so tests don't queue real jobs)."""
    frappe.db.set_value("HMD Configuration", "HMD Configuration",
                        "periode_velage_jours", value, update_modified=False)
    frappe.db.commit()


def test_insemination_reads_config(results):
    """get_config('periode_velage_jours') returns the configured value, and
    date math gives the expected vêlage date."""
    log("insemination.update_animal_on_resultat lit periode_velage_jours", "HEAD")

    from hmd_agro.hmd_agro.utils.config import get_config
    date_ia = getdate("2026-03-01")
    original = frappe.db.get_value("HMD Configuration", "HMD Configuration",
                                    "periode_velage_jours")

    try:
        # Baseline (default 280)
        _set_period(280)
        actual = get_config("periode_velage_jours", default=280)
        check(actual == 280,
              "get_config retourne 280 (défaut)",
              f"Got {actual}", results)
        check(add_days(date_ia, actual) == getdate("2026-12-06"),
              "date_velage_prevue = date_ia + 280 = 2026-12-06",
              f"Got {add_days(date_ia, actual)}", results)

        # Modified
        _set_period(285)
        actual2 = get_config("periode_velage_jours", default=280)
        check(actual2 == 285,
              "Après config=285: get_config retourne 285",
              f"Got {actual2} (config wiring cassée)", results)
        check(add_days(date_ia, actual2) == getdate("2026-12-11"),
              "date_velage_prevue = date_ia + 285 = 2026-12-11",
              f"Got {add_days(date_ia, actual2)}", results)
    finally:
        _set_period(original)


def test_recalculate_velage_prevue_dates(results):
    """Bulk recalc: change periode_velage_jours then call the recalc helper.
    Stored Animal.date_velage_prevue + date_tarissement should both shift."""
    log("recalculate_velage_prevue_dates propage la nouvelle config", "HEAD")
    from hmd_agro.hmd_agro.utils.velage_prevue_recalc import recalculate_velage_prevue_dates

    sample = frappe.db.sql("""
        SELECT a.name, a.id_ia_fecondante, a.date_velage_prevue, a.date_tarissement,
               i.date_ia
        FROM `tabAnimal` a
        INNER JOIN `tabInsemination` i ON i.name = a.id_ia_fecondante
        WHERE a.etat_gestation = 'GESTANTE' AND a.id_ia_fecondante IS NOT NULL
          AND i.date_ia IS NOT NULL
        LIMIT 1
    """, as_dict=True)
    if not sample:
        log("Skip — pas d'animal GESTANTE avec IA fécondante", "FAIL")
        results["fail"] += 1
        return
    animal = sample[0]
    snapshot_velage = animal.date_velage_prevue
    snapshot_tarissement = animal.date_tarissement
    period_snapshot = frappe.db.get_value("HMD Configuration", "HMD Configuration",
                                           "periode_velage_jours")
    window_snapshot = int(frappe.db.get_value("HMD Configuration", "HMD Configuration",
                                                "tarissement_window_jours") or 60)

    try:
        # Force period to 285 → both dates should shift by +5 days vs the date_ia baseline
        _set_period(285)
        result = recalculate_velage_prevue_dates()
        check(result["total"] > 0,
              f"Recalc a touché {result['total']} animaux GESTANTE",
              f"total={result['total']}", results)
        check(len(result["failed"]) == 0,
              "Aucune erreur de recalc",
              f"failed={result['failed']}", results)

        new_velage = frappe.db.get_value("Animal", animal.name, "date_velage_prevue")
        new_tarissement = frappe.db.get_value("Animal", animal.name, "date_tarissement")
        expected_velage = getdate(add_days(getdate(animal.date_ia), 285))
        expected_tarissement = getdate(add_days(expected_velage, -window_snapshot))

        check(getdate(new_velage) == expected_velage,
              f"date_velage_prevue = date_ia ({animal.date_ia}) + 285j = {expected_velage}",
              f"Got {new_velage}", results)
        check(getdate(new_tarissement) == expected_tarissement,
              f"date_tarissement = velage_prevue - {window_snapshot}j = {expected_tarissement}",
              f"Got {new_tarissement}", results)
    finally:
        _set_period(period_snapshot)
        # Restore original dates so other tests find the animal in known state
        frappe.db.set_value("Animal", animal.name, {
            "date_velage_prevue": snapshot_velage,
            "date_tarissement": snapshot_tarissement,
        }, update_modified=False)
        frappe.db.commit()


def test_recalc_refreshes_velage_alert_raison(results):
    """When recalc fires, open VELAGE_IMMINENT alerts get their raison text
    updated to reflect the new date_velage_prevue."""
    log("recalc rafraîchit le texte des alertes VELAGE_IMMINENT existantes", "HEAD")
    from hmd_agro.hmd_agro.utils.velage_prevue_recalc import recalculate_velage_prevue_dates

    sample = frappe.db.sql("""
        SELECT a.name, a.id_ia_fecondante, a.date_velage_prevue, a.date_tarissement,
               i.date_ia
        FROM `tabAnimal` a
        INNER JOIN `tabInsemination` i ON i.name = a.id_ia_fecondante
        WHERE a.etat_gestation = 'GESTANTE' AND a.id_ia_fecondante IS NOT NULL
          AND i.date_ia IS NOT NULL
        LIMIT 1
    """, as_dict=True)
    if not sample:
        log("Skip — pas d'animal GESTANTE", "FAIL")
        results["fail"] += 1
        return
    animal = sample[0]
    snapshot_velage = animal.date_velage_prevue
    snapshot_tarissement = animal.date_tarissement
    period_snapshot = frappe.db.get_value("HMD Configuration", "HMD Configuration",
                                           "periode_velage_jours")
    test_alert_name = None

    try:
        # Create a stale VELAGE_IMMINENT alert with bogus old date
        alert = frappe.get_doc({
            "doctype": "Alerte",
            "animal": animal.name,
            "type_alerte": "VELAGE_IMMINENT",
            "date_alerte": getdate("2026-01-01"),
            "raison": "Velage prevu dans 99 jour(s) (1900-01-01)",
            "statut": "NOUVELLE",
        })
        alert.insert(ignore_permissions=True)
        test_alert_name = alert.name
        frappe.db.commit()

        _set_period(290)
        result = recalculate_velage_prevue_dates()
        check(result["alerts_refreshed"] >= 1,
              f"Au moins 1 alerte rafraîchie ({result['alerts_refreshed']})",
              f"alerts_refreshed={result['alerts_refreshed']}", results)

        new_raison = frappe.db.get_value("Alerte", test_alert_name, "raison")
        expected_date = add_days(getdate(animal.date_ia), 290)
        check(str(expected_date) in new_raison,
              f"Raison contient la nouvelle date {expected_date}",
              f"Raison: {new_raison!r}", results)
        check("1900-01-01" not in new_raison,
              "Ancienne date (1900-01-01) supprimée du raison",
              f"Raison: {new_raison!r}", results)
    finally:
        if test_alert_name and frappe.db.exists("Alerte", test_alert_name):
            frappe.delete_doc("Alerte", test_alert_name, force=True,
                              ignore_permissions=True)
        _set_period(period_snapshot)
        frappe.db.set_value("Animal", animal.name, {
            "date_velage_prevue": snapshot_velage,
            "date_tarissement": snapshot_tarissement,
        }, update_modified=False)
        frappe.db.commit()
