"""TASK B3 — initialize `equipement_cout_horaire_defaut` in HMD Configuration.

Same rationale as v1_1/v1_7: after migrate, Currency/Float fields land as 0.0
in tabSingles (not the JSON default), so `get_config` would return 0 and the
coût horaire resolver would silently fall back to its code default without
the value being visible (or editable) in HMD Configuration. Seed 25 DT/h once.

Idempotent: only sets the field while it is None/0 (uninitialized).
"""
import frappe

DEFAULTS = {
    # TASK B3 — coût horaire équipement (résolveur maintenance_utils.cout_horaire)
    "equipement_cout_horaire_defaut": 25.0,
}


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    changed = False
    for field, value in DEFAULTS.items():
        current = doc.get(field)
        if current is None or current == 0:
            doc.set(field, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
