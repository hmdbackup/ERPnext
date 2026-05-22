"""Initialize the new PFE seuils fields in HMD Configuration.

After migrate, Frappe stores Float fields as 0.0 (not the JSON `default`),
so `get_config(...)` returns 0.0 and breaks the indicator color logic in
the Indicateurs report. This patch sets each new field to its PFE default.

Idempotent: only sets a field if its current value is None or 0 (which on
a fresh install means uninitialized — these defaults are non-zero).
"""
import frappe


PFE_DEFAULTS = {
    "pfe_lc_optimal_min": 2.0,
    "pfe_lc_optimal_max": 2.4,
    "pfe_lc_alarm_min": 1.5,
    "pfe_lc_alarm_max": 3.0,
    "pfe_efficacite_min": 1.4,
    "pfe_efficacite_orange_min": 1.0,
    "pfe_persistance_min": 0.85,
    "pfe_persistance_max": 0.95,
    "pfe_persistance_alarm_min": 0.7,
    "pfe_persistance_alarm_max": 1.10,
    "pfe_3ia_plus_max": 15.0,
    "pfe_3ia_plus_orange_max": 25.0,
}


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    changed = False
    for field, value in PFE_DEFAULTS.items():
        current = doc.get(field)
        # All PFE defaults are non-zero, so 0/None means uninitialized.
        if current is None or current == 0:
            doc.set(field, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
