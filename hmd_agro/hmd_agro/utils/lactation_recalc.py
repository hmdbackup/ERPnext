"""Bulk recalculation of all Lactation production aggregates.

Triggered by HMD Configuration.on_update() when pic_production_jours or
production_initiale_jours change. Reuses the per-lactation function from
import_traites so the formulas can never drift from the regular Traite-save
recalc path.

Runs as a background job (enqueued from on_update) — caller doesn't wait.
"""
import frappe


@frappe.whitelist()
def recalculate_all_lactations():
    """Loop every Lactation and re-run its production calculations.
    Per-row failures are logged but don't stop the rest. Publishes a
    realtime event when done so the UI can show a notification."""
    from hmd_agro.hmd_agro.page.import_traites.import_traites import (
        recalculate_lactation_production,
    )

    lactations = frappe.get_all("Lactation", fields=["name"])
    success, failed = 0, []

    for lac in lactations:
        try:
            recalculate_lactation_production(lac.name)
            success += 1
        except Exception as e:
            failed.append(lac.name)
            frappe.log_error(
                f"Lactation recalc failed for {lac.name}: {e}",
                "Lactation Bulk Recalc",
            )

    frappe.db.commit()
    frappe.publish_realtime(
        "lactation_recalc_done",
        {"success": success, "failed": failed, "total": len(lactations)},
    )
    return {"success": success, "failed": failed, "total": len(lactations)}
