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
    survive a future change to Stock Settings.

    Implementation note (ST5-13): writes go through child-table SQL/db_insert
    rather than `Item.save()`. The full save cycle re-runs ERPNext's Item
    validate, which on repeated saves duplicates the stock_uom row in the
    `Item.uoms` table — broke test_stock_integration during Phase C. db ops
    bypass that lifecycle and produce identical visible state."""
    existing = frappe.db.get_value(
        "Item Default",
        {"parent": item_code, "company": company},
        ["name", "default_warehouse"],
        as_dict=True,
    )
    if existing:
        if existing.default_warehouse == warehouse:
            return False
        frappe.db.set_value("Item Default", existing.name,
                            "default_warehouse", warehouse, update_modified=False)
        return True
    max_idx = (frappe.db.sql(
        "SELECT COALESCE(MAX(idx), 0) FROM `tabItem Default` WHERE parent=%s",
        item_code,
    )[0][0]) or 0
    new_doc = frappe.new_doc("Item Default")
    new_doc.parent = item_code
    new_doc.parenttype = "Item"
    new_doc.parentfield = "item_defaults"
    new_doc.company = company
    new_doc.default_warehouse = warehouse
    new_doc.idx = (max_idx or 0) + 1
    new_doc.db_insert()
    return True


def ensure_item_allow_negative_stock(item_code):
    """Set `Item.allow_negative_stock = 1` if not already. Idempotent.
    Returns True iff a write happened.

    Why: production stance — Traitement and Insémination represent real-world
    events that already happened. The system must record them even if our
    Bin count is stale (forgot to enter a Purchase Receipt, miscount, etc.).
    Refusing the operation would force the user to fudge the data. Instead,
    let Bin go negative; the native reorder Material Request (wired via
    ST5-08 + utils/reorder_sync.py) handles replenishment proactively when
    stock falls to reorder_level. Applies uniformly to ALI-, MED-, SEM-.
    """
    current = frappe.db.get_value("Item", item_code, "allow_negative_stock")
    if current:
        return False
    frappe.db.set_value("Item", item_code, "allow_negative_stock", 1)
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
