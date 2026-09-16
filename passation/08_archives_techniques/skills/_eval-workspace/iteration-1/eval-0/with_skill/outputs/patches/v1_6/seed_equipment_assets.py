"""Seed the farm's tracked equipment as ERPNext Asset records.

EQUIPMENT (spec entity) is realized with ERPNext core `Asset`, NOT a custom
DocType (see references/spec-to-implementation-map.md §3). This idempotent patch
creates the four physical machines under the "Matériel Agricole HMD" Asset
Category so they exist on every install. Re-runs on every `bench migrate` are
no-ops because each Asset is only inserted when missing (house patch pattern,
mirroring hmd_agro/patches/v1_0/init_hmd_configuration.py).

Maintenance interventions on these assets are recorded as `Asset Maintenance` /
`Asset Maintenance Log` (ERPNext core) — no custom Intervention DocType.
"""
import frappe

ASSET_CATEGORY = "Matériel Agricole HMD"

# Stable asset_name values; ERPNext autonames Asset by ACC-ASS-####, so we
# de-dupe on asset_name to keep the patch idempotent.
EQUIPMENT = [
    {"asset_name": "Tracteur 1", "asset_quantity": 1},
    {"asset_name": "Tracteur 2", "asset_quantity": 1},
    {"asset_name": "Machine à Traire", "asset_quantity": 1},
    {"asset_name": "Tank à Lait", "asset_quantity": 1},
]


def execute():
    """Create any missing equipment Asset. Idempotent: skips assets that already
    exist (matched by asset_name)."""
    if not frappe.db.exists("DocType", "Asset"):
        # ERPNext (which ships Asset) not installed on this site — nothing to do.
        return

    # Ensure the category exists (normally imported via the Asset Category
    # fixture; create a minimal non-depreciable one here as a safety net so the
    # patch is self-contained on a bare site).
    if not frappe.db.exists("Asset Category", ASSET_CATEGORY):
        cat = frappe.get_doc(
            {
                "doctype": "Asset Category",
                "asset_category_name": ASSET_CATEGORY,
                "non_depreciable_category": 1,
            }
        )
        cat.insert(ignore_permissions=True)

    created = False
    for spec in EQUIPMENT:
        if frappe.db.exists("Asset", {"asset_name": spec["asset_name"]}):
            continue
        asset = frappe.get_doc(
            {
                "doctype": "Asset",
                "asset_name": spec["asset_name"],
                "asset_category": ASSET_CATEGORY,
                "asset_quantity": spec["asset_quantity"],
                # is_existing_asset=1 + maintenance_required so the asset can be
                # tracked/maintained without a Purchase Receipt or depreciation.
                "is_existing_asset": 1,
                "maintenance_required": 1,
                "available_for_use_date": frappe.utils.nowdate(),
            }
        )
        asset.flags.ignore_mandatory = True
        asset.insert(ignore_permissions=True)
        created = True

    if created:
        frappe.db.commit()
