"""Stock-module scaffold — prerequisite for Aliment / Medicament / Semence imports.

A fresh ERPNext site (after the setup wizard creates Company `hmd-agro` + default
warehouses) still lacks the HMD-specific stock setup that the auto-created
ALI-/MED-/SEM- Items depend on. This creates it:
  - custom UOMs: Paillette, Dose
  - Item Group tree: Aliment(+6), Médicament(+7), Semence(+2)
  - custom warehouse: Magasin Principal - HMD
  - Stock Settings: default_warehouse + FIFO + Item Code naming

PREREQUISITE: the ERPNext setup wizard must have created Company `hmd-agro`
(abbr HMD, TND, Tunisia) and the `All Warehouses - HMD` group. This script aborts
if the company is missing.

Idempotent / dry-run. Run AFTER the wizard, BEFORE import_aliment.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_stock_setup.run --kwargs '{"dry_run":1}'
"""
import frappe

COMPANY = "hmd-agro"
WAREHOUSE = "Magasin Principal - HMD"
WAREHOUSE_PARENT = "All Warehouses - HMD"

UOMS = ["Paillette", "Dose"]

# parent group -> children (all under "All Item Groups"); names must match the
# accented values the Aliment/Medicament/Semence Item-creation logic expects.
ITEM_GROUPS = {
    "Aliment": ["Concentré", "Ensilage", "Fourrage", "Minéral", "Paille", "Supplément"],
    "Médicament": ["Antibiotique", "Anti-inflammatoire", "Antiparasitaire",
                   "Autre Médicament", "Hormone", "Vaccin", "Vitamine"],
    "Semence": ["Semence Conventionnelle", "Semence Sexée"],
}


def run(dry_run=True):
    dry_run = int(dry_run)
    log = []
    if not frappe.db.exists("Company", COMPANY):
        print(f"[ABORT] Company '{COMPANY}' missing — run the ERPNext setup wizard first.")
        return {"aborted": True}

    # --- UOMs ---
    for u in UOMS:
        if frappe.db.exists("UOM", u):
            log.append(f"[skip] UOM {u}")
            continue
        log.append(f"[ADD]  UOM {u}")
        if not dry_run:
            frappe.get_doc({"doctype": "UOM", "uom_name": u, "enabled": 1}).insert(ignore_permissions=True)

    # --- Item Groups (parents first, then children) ---
    for parent, children in ITEM_GROUPS.items():
        if not frappe.db.exists("Item Group", parent):
            log.append(f"[ADD]  Item Group {parent} (group)")
            if not dry_run:
                frappe.get_doc({"doctype": "Item Group", "item_group_name": parent,
                                "parent_item_group": "All Item Groups", "is_group": 1}).insert(ignore_permissions=True)
        else:
            log.append(f"[skip] Item Group {parent}")
        for child in children:
            if frappe.db.exists("Item Group", child):
                log.append(f"[skip] Item Group {child}")
                continue
            log.append(f"[ADD]  Item Group {child} (under {parent})")
            if not dry_run:
                frappe.get_doc({"doctype": "Item Group", "item_group_name": child,
                                "parent_item_group": parent, "is_group": 0}).insert(ignore_permissions=True)

    # --- Warehouse ---
    if frappe.db.exists("Warehouse", WAREHOUSE):
        log.append(f"[skip] Warehouse {WAREHOUSE}")
    else:
        log.append(f"[ADD]  Warehouse {WAREHOUSE}")
        if not dry_run:
            doc = {"doctype": "Warehouse", "warehouse_name": "Magasin Principal", "company": COMPANY}
            if frappe.db.exists("Warehouse", WAREHOUSE_PARENT):
                doc["parent_warehouse"] = WAREHOUSE_PARENT
            frappe.get_doc(doc).insert(ignore_permissions=True)

    # --- Stock Settings ---
    log.append("[SET]  Stock Settings: default_warehouse, valuation=FIFO, naming=Item Code")
    if not dry_run:
        ss = frappe.get_doc("Stock Settings")
        ss.item_naming_by = "Item Code"
        ss.valuation_method = "FIFO"
        if frappe.db.exists("Warehouse", WAREHOUSE):
            ss.default_warehouse = WAREHOUSE
        ss.flags.ignore_validate = True
        ss.save(ignore_permissions=True)

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Stock setup")
    for line in log:
        print(f"  {line}")
    return {"actions": len(log)}
