"""
ERPNext Stock module helpers — used by Traitement (Médicament), Insémination
(Semence), and future Aliment integrations.
"""
import frappe
from frappe.utils import today

DEFAULT_COMPANY = "hmd-agro"
DEFAULT_WAREHOUSE = "Magasin Principal - HMD"
DEFAULT_UOM = "Unit"


def ensure_item_default(item_code, company=DEFAULT_COMPANY, warehouse=DEFAULT_WAREHOUSE):
    """Make sure `Item.item_defaults` has a row for `company` pointing at
    `warehouse`. Idempotent: no-op if already correct, updates if mismatched,
    appends if missing. Returns True iff a write happened.

    Why: without this row, ERPNext falls back to `Stock Settings.default_warehouse`
    when a user creates a Stock Entry / Purchase Receipt via UI. That fallback
    used to be `Stores - HMD`, causing a draft PR to silently land stock in the
    wrong warehouse. Per-Item defaults make the warehouse choice explicit and
    survive a future change to Stock Settings."""
    item = frappe.get_doc("Item", item_code)
    for row in (item.item_defaults or []):
        if row.company == company:
            if row.default_warehouse == warehouse:
                return False
            row.default_warehouse = warehouse
            item.save(ignore_permissions=True)
            return True
    item.append("item_defaults", {
        "company": company,
        "default_warehouse": warehouse,
    })
    item.save(ignore_permissions=True)
    return True


def create_stock_movement(item_code, qty, purpose, warehouse, remark,
                          posting_date=None, company=None, uom=None, batch_no=None):
    """
    Submit a single-line Stock Entry.

    Args:
        item_code:    ERPNext Item code (e.g., "MED-Amoxicilline")
        qty:          quantity (positive number)
        purpose:      "Material Issue" (consumption) or "Material Receipt" (intake)
        warehouse:    warehouse name (e.g., "Magasin Principal - HMD")
        remark:       human-readable trace (e.g., "Traitement TRT-2026-00931")
        posting_date: defaults to today
        company:      defaults to "hmd-agro"
        uom:          defaults to "Unit"
        batch_no:     optional batch ID (required for Items with has_batch_no=1, e.g., Semence)

    Returns:
        the submitted Stock Entry name (e.g., "MAT-STE-2026-00006")

    Notes:
        - Uses allow_zero_valuation_rate=1 because we don't track cost yet.
          Phase B will add real valuation when receipt prices are entered.
        - Stock Entry is submitted (not draft) so Bin updates immediately.
    """
    company = company or DEFAULT_COMPANY
    uom = uom or DEFAULT_UOM

    item_line = {
        "item_code": item_code,
        "qty": qty,
        "uom": uom,
        "stock_uom": uom,
        "conversion_factor": 1,
        "basic_rate": 0,
        "allow_zero_valuation_rate": 1,
    }
    if batch_no:
        item_line["batch_no"] = batch_no
    if purpose == "Material Issue":
        item_line["s_warehouse"] = warehouse
    elif purpose == "Material Receipt":
        item_line["t_warehouse"] = warehouse
    else:
        frappe.throw(f"create_stock_movement: purpose '{purpose}' inconnu")

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": purpose,
        "company": company,
        "posting_date": posting_date or today(),
        "items": [item_line],
        "remarks": remark,
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name
