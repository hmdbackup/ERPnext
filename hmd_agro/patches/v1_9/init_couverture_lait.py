"""FIN-S100 — amorce la tolérance de couverture lait dans HMD Configuration.

Les Int/Float d'un Single ne prennent pas le défaut du JSON à la migration
(même raison que v1_1/v1_7) : sans amorçage, `get_config` renverrait 0 et le
moindre jour sans traite déclencherait l'avertissement « données incomplètes ».

Idempotent : n'écrit que si la valeur est encore non initialisée.
"""
import frappe


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    if not doc.meta.has_field("couverture_lait_tolerance_jours"):
        return
    if doc.get("couverture_lait_tolerance_jours") in (None, 0, ""):
        doc.couverture_lait_tolerance_jours = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()
