# =============================================================================
# Snippet to MERGE into hmd_agro/hooks.py  ->  the existing `fixtures = [ ... ]`
# list. DO NOT replace the list; just add the two by-name lines below alongside
# the existing `Stock Entry-id_lot` entry.
#
# WHY by-name (the critical convention):
#   The bulk Custom Field fixture line already in hooks.py is
#       {"dt": "Custom Field", "filters": [["dt", "in", HMD_DOCTYPES]]}
#   `Asset` and `Asset Maintenance Log` are ERPNext CORE DocTypes -> they are
#   NOT in HMD_DOCTYPES, so that filter does NOT catch these custom fields and
#   they would be WIPED on `bench migrate`. They must be exported explicitly by
#   name, exactly like the SCRUM-123 `Stock Entry-id_lot` line.
#   (See references/erpnext-integration.md, section
#    "The `Stock Entry-id_lot` Custom Field (SCRUM-123)".)
#
# Note: we deliberately do NOT add "Asset"/"Asset Maintenance"/"Asset
# Maintenance Log" to HMD_DOCTYPES — they are ERPNext core, not HMD DocTypes,
# and adding them would mis-scope Property Setter / Custom Field bulk exports.
# =============================================================================

fixtures = [
    {"dt": "Workspace", "filters": [["module", "=", "HMD AGRO"]]},
    {"dt": "Property Setter", "filters": [["doc_type", "in", HMD_DOCTYPES]]},
    {"dt": "Custom Field", "filters": [["dt", "in", HMD_DOCTYPES]]},
    # Stock Entry.id_lot — SCRUM-123 custom field on a non-HMD doctype.
    {"dt": "Custom Field", "filters": [["name", "=", "Stock Entry-id_lot"]]},
    # --- ADD THESE TWO LINES (EQUIPMENT / INTERVENTION custom fields on ----
    # --- ERPNext core Asset DocTypes — by name, same reason as above) ------
    {"dt": "Custom Field", "filters": [["name", "=", "Asset-batiment"]]},
    {"dt": "Custom Field", "filters": [["name", "=", "Asset Maintenance Log-remarque_intervention"]]},
    # ----------------------------------------------------------------------
    # Asset Category fixture so the equipment classification exists on a fresh
    # site. Filter on the one category we manage (do NOT export ERPNext's own
    # default categories).
    {"dt": "Asset Category", "filters": [["name", "=", "Matériel Agricole HMD"]]},
    {"dt": "Number Card", "filters": [["module", "=", "HMD AGRO"]]},
    {"dt": "Dashboard Chart", "filters": [["module", "=", "HMD AGRO"]]},
]
