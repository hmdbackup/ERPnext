"""Sync `reorder_level` (defined on Aliment / Médicament) into the linked
ERPNext Item's `reorder_levels` child table for the configured warehouse.

Why this exists: ERPNext's native `erpnext.stock.reorder_item.reorder_item`
scheduler creates a Material Request automatically whenever an Item's projected
qty falls at-or-below its configured reorder level (Stock Settings.auto_indent
must be on — verified set in this install). The reorder level lives in the
`Item Reorder` child table on Item, NOT on the HMD doctype.

To keep the farmer-facing UI simple (one field, on the Aliment/Médicament form
they already use), we sync the value into Item.reorder_levels on save. The
native scheduler then handles everything else: Material Request creation, email
notifications, integration with Purchase Order/Receipt downstream.
"""
import frappe

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as WAREHOUSE
# When stock falls below the reorder level, ERPNext creates a Material Request
# of this type. "Purchase" → request gets routed to the Buying flow.
MATERIAL_REQUEST_TYPE = "Purchase"


def sync_reorder_level(doctype, name):
    """Read `reorder_level` from the HMD record and upsert/delete the matching
    row in `Item.reorder_levels`.

    Behavior:
      - reorder_level > 0  → upsert Item Reorder row (warehouse, level, qty=level)
      - reorder_level = 0  → delete the row (turns reordering off for this item)
      - no `item` link     → no-op (record not migrated to Item yet)
    """
    record = frappe.db.get_value(
        doctype, name, ["item", "reorder_level"], as_dict=True
    )
    if not record or not record.item:
        return  # No Item link yet (after_insert hook will set it on next save)

    item = frappe.get_doc("Item", record.item)
    existing_idx = None
    for idx, row in enumerate(item.reorder_levels or []):
        if row.warehouse == WAREHOUSE:
            existing_idx = idx
            break

    level = record.reorder_level or 0

    if level <= 0:
        # Disable reordering for this item — drop the row if present
        if existing_idx is not None:
            item.reorder_levels.pop(existing_idx)
            item.save(ignore_permissions=True)
        return

    # Upsert. reorder_qty defaults to the level itself (request enough stock to
    # bring inventory back up to the threshold). Farmers can edit the qty
    # directly on the Item form if they want a different reorder amount.
    if existing_idx is not None:
        row = item.reorder_levels[existing_idx]
        if row.warehouse_reorder_level != level or row.warehouse_reorder_qty != level:
            row.warehouse_reorder_level = level
            row.warehouse_reorder_qty = level
            row.material_request_type = MATERIAL_REQUEST_TYPE
            item.save(ignore_permissions=True)
    else:
        item.append("reorder_levels", {
            "warehouse": WAREHOUSE,
            "warehouse_reorder_level": level,
            "warehouse_reorder_qty": level,
            "material_request_type": MATERIAL_REQUEST_TYPE,
        })
        item.save(ignore_permissions=True)
