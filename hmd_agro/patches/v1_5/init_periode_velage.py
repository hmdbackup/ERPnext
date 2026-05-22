"""Seed the new `periode_velage_jours` field on HMD Configuration with the
documented default (280 days = Holstein average) on existing installs.

Without this, `frappe.db.get_single_value("HMD Configuration",
"periode_velage_jours")` returns 0 on systems that already had a row in
tabSingles (because JSON-level defaults aren't materialized for existing
Single rows). 0 would then be picked up by `get_config(..., default=280)`
as a real value → date_velage_prevue = date_ia + 0 = the IA date itself.

Idempotent: only writes if no value is set yet.
"""
import frappe


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return

    current = frappe.db.get_single_value("HMD Configuration", "periode_velage_jours")
    if current:
        return  # already set — leave operator's value alone

    frappe.db.set_single_value("HMD Configuration", "periode_velage_jours", 280)
    frappe.db.commit()
