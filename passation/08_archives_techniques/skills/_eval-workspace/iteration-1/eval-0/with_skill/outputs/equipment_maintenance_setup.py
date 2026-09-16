"""Optional convenience helpers for equipment maintenance (INTERVENTION).

Proposed location if adopted: hmd_agro/hmd_agro/utils/equipment.py
(shared/reused logic lives under utils/ per SKILL.md "Where does logic go?").

These wrap ERPNext core `Asset Maintenance` / `Asset Maintenance Log` so an
operator can attach a maintenance schedule to an Asset and log a performed
intervention without leaving the HMD workflow. NO custom DocType is involved —
INTERVENTION is ERPNext core (spec-to-implementation-map.md §3).

Conventions applied:
- French user-facing messages via frappe.throw / msgprint; English docstrings.
- get_config not needed here (no thresholds); whitelisted helper pattern mirrors
  traitement.create_bulk_traitement.
"""
import frappe
from frappe import _


@frappe.whitelist()
def ensure_maintenance_schedule(asset, task_name, periodicity="Monthly", assign_to=None):
    """Attach (or extend) an `Asset Maintenance` schedule to `asset`.

    `Asset Maintenance` is the per-asset plan; each row of its
    `asset_maintenance_tasks` child table is one recurring task. Idempotent on
    (asset, task) so re-calling does not duplicate the task.
    """
    if not frappe.db.exists("Asset", asset):
        frappe.throw(_("Équipement introuvable : {0}").format(asset))

    name = frappe.db.get_value("Asset Maintenance", {"asset_name": asset}, "name")
    if name:
        doc = frappe.get_doc("Asset Maintenance", name)
    else:
        item_code = frappe.db.get_value("Asset", asset, "item_code")
        doc = frappe.get_doc(
            {
                "doctype": "Asset Maintenance",
                "asset_name": asset,
                "item_code": item_code,
                "maintenance_team": None,
            }
        )

    already = any(t.maintenance_task == task_name for t in doc.get("asset_maintenance_tasks", []))
    if not already:
        doc.append(
            "asset_maintenance_tasks",
            {
                "maintenance_task": task_name,
                "periodicity": periodicity,
                "maintenance_type": "Preventive Maintenance",
                "assign_to": assign_to,
                "start_date": frappe.utils.nowdate(),
            },
        )
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def log_intervention(asset, task, completion_date=None, description=None, remarque=None):
    """Record a performed maintenance intervention as an `Asset Maintenance Log`.

    This is the literal "maintenance intervention done on the equipment" — one
    log row per completed task. Uses the HMD custom field
    `remarque_intervention` (see custom_fields_asset.json) for the operator note.
    """
    if not frappe.db.exists("Asset", asset):
        frappe.throw(_("Équipement introuvable : {0}").format(asset))

    log = frappe.get_doc(
        {
            "doctype": "Asset Maintenance Log",
            "asset_name": asset,
            "task": task,
            "completion_date": completion_date or frappe.utils.nowdate(),
            "maintenance_status": "Completed",
            "description": description,
            "remarque_intervention": remarque,  # HMD custom field
        }
    )
    log.flags.ignore_mandatory = True
    log.insert(ignore_permissions=True)
    return log.name
