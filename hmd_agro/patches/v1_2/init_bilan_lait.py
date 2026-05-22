"""Initialize the Bilan Lait threshold fields in HMD Configuration.

Same Frappe Float-default-on-migrate quirk as v1_1: after migrate, Float
fields land at 0.0 in `tabSingles` instead of their JSON `default`. Audit
showed only these two fields were affected (everything else was either
correctly defaulted by v1_0/v1_1 or intentionally customized by the user).

Idempotent: only sets a field if its current value is None or 0. Both
defaults are non-zero, so 0/None means uninitialized.
"""
import frappe


BILAN_LAIT_DEFAULTS = {
    "ecart_lait_seuil_negatif_l": 1.0,
    "ecart_lait_seuil_perte_pct": 5.0,
}


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    changed = False
    for field, value in BILAN_LAIT_DEFAULTS.items():
        current = doc.get(field)
        if current is None or current == 0:
            doc.set(field, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
