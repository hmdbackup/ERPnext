"""
Sprint 5 — Phase A — Step 1: ERPNext Stock module foundation.

Creates UOMs, Item Group taxonomy, and the single Magasin Principal warehouse.
Idempotent: skips anything that already exists. Re-runnable safely.

Run:
    bench --site hmd.localhost execute \\
        hmd_agro.hmd_agro.setup.stock_foundation.create_stock_foundation
"""
import frappe

COMPANY = "hmd-agro"

UOMS = ["Dose", "Paillette"]

ITEM_GROUPS = [
    # (name, parent, is_group)
    ("Médicament", "All Item Groups", 1),
    ("Antibiotique", "Médicament", 0),
    ("Anti-inflammatoire", "Médicament", 0),
    ("Antiparasitaire", "Médicament", 0),
    ("Vaccin", "Médicament", 0),
    ("Hormone", "Médicament", 0),
    ("Vitamine", "Médicament", 0),
    ("Autre Médicament", "Médicament", 0),
    ("Aliment", "All Item Groups", 1),
    ("Concentré", "Aliment", 0),
    ("Fourrage", "Aliment", 0),
    ("Minéral", "Aliment", 0),
    ("Ensilage", "Aliment", 0),
    ("Paille", "Aliment", 0),
    ("Supplément", "Aliment", 0),
    ("Semence", "All Item Groups", 1),
    ("Semence Conventionnelle", "Semence", 0),
    ("Semence Sexée", "Semence", 0),
]

WAREHOUSES = [
    # (name, is_group)
    ("Magasin Principal", 0),
]


@frappe.whitelist()
def create_stock_foundation():
    """Bootstrap ERPNext Stock module objects required by HMD Agro."""
    print("\n" + "=" * 60)
    print("  Sprint 5 — Stock Foundation Setup")
    print("=" * 60)

    company = frappe.get_doc("Company", COMPANY)
    print(f"  Company: {company.name} (abbr={company.abbr}, currency={company.default_currency})\n")

    created = {"uom": 0, "item_group": 0, "warehouse": 0}
    skipped = {"uom": 0, "item_group": 0, "warehouse": 0}

    # 1. UOMs
    print("  ── UOMs ──")
    for uom in UOMS:
        if frappe.db.exists("UOM", uom):
            print(f"     [skip]   {uom}")
            skipped["uom"] += 1
        else:
            frappe.get_doc({"doctype": "UOM", "uom_name": uom, "must_be_whole_number": 1}).insert(
                ignore_permissions=True
            )
            print(f"     [create] {uom}")
            created["uom"] += 1

    # 2. Item Groups (parents must exist before children — list is ordered)
    print("\n  ── Item Groups ──")
    for name, parent, is_group in ITEM_GROUPS:
        if frappe.db.exists("Item Group", name):
            print(f"     [skip]   {name}")
            skipped["item_group"] += 1
        else:
            frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": parent,
                "is_group": is_group,
            }).insert(ignore_permissions=True)
            print(f"     [create] {name} (parent={parent}, group={is_group})")
            created["item_group"] += 1

    # 3. Warehouses (suffix '- {abbr}' added by ERPNext)
    print("\n  ── Warehouses ──")
    parent_wh = f"All Warehouses - {company.abbr}"
    for name, is_group in WAREHOUSES:
        full_name = f"{name} - {company.abbr}"
        if frappe.db.exists("Warehouse", full_name):
            print(f"     [skip]   {full_name}")
            skipped["warehouse"] += 1
        else:
            frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": name,
                "company": company.name,
                "parent_warehouse": parent_wh,
                "is_group": is_group,
            }).insert(ignore_permissions=True)
            print(f"     [create] {full_name}")
            created["warehouse"] += 1

    # ST5-11 (2026-05-17): allow fractional Unit so Traitement.qty_consumed
    # can be e.g. 0.5 (half a flacon). Pre-Phase C the Unit UOM had
    # must_be_whole_number=1 (ERPNext default), which blocked fractional
    # stock movements with the error "la quantité ne peut pas être une fraction".
    if frappe.db.exists("UOM", "Unit"):
        whole = frappe.db.get_value("UOM", "Unit", "must_be_whole_number")
        if whole:
            frappe.db.set_value("UOM", "Unit", "must_be_whole_number", 0,
                                 update_modified=False)
            print("  ── UOM 'Unit'.must_be_whole_number → 0 (fractional allowed)")

    frappe.db.commit()

    print("\n" + "=" * 60)
    print(f"  Created: {created['uom']} UOMs, {created['item_group']} Item Groups, "
          f"{created['warehouse']} Warehouses")
    print(f"  Skipped: {skipped['uom']} UOMs, {skipped['item_group']} Item Groups, "
          f"{skipped['warehouse']} Warehouses")
    print("=" * 60 + "\n")

    return {"created": created, "skipped": skipped}
