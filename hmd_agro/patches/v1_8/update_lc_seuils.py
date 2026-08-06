"""FIN — réunion 05/08/2026 : seuils L/C revus (rouge sous 1,8, cible 2,2).

Same rationale as v1_1/init_pfe_seuils: after migrate, Float fields land as
0.0 in tabSingles (not the JSON default), so `get_config` would return 0 and
break the L/C coloring. Two writes here:

  - pfe_lc_cible (new field): seed 2.2 while uninitialized (None/0).
  - pfe_lc_alarm_min: raise 1.5 → 1.8. Only overwritten when the current
    value is None/0 (uninitialized) or still equals the OLD known default
    1.5 — a farm-tuned value is never clobbered.

Idempotent: re-runs are no-ops once the values are set (1.8 is neither
None/0 nor 1.5).
"""
import frappe

OLD_ALARM_MIN = 1.5
NEW_ALARM_MIN = 1.8
CIBLE_DEFAULT = 2.2


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    changed = False

    current_cible = doc.get("pfe_lc_cible")
    if current_cible is None or current_cible == 0:
        doc.set("pfe_lc_cible", CIBLE_DEFAULT)
        changed = True

    current_alarm = doc.get("pfe_lc_alarm_min")
    if current_alarm is None or current_alarm == 0 or current_alarm == OLD_ALARM_MIN:
        doc.set("pfe_lc_alarm_min", NEW_ALARM_MIN)
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
