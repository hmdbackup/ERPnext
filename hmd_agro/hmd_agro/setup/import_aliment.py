"""Reconcile Aliment records against the farm's Rapport Mensuel feed list.

Source: Rapport Mensuel Janvier.xlsx / Décombre.xlsx — identical 12-feed list,
referenced all 31 days of each month, same prices in both files.

Three idempotent operations (all dry_run-aware):
  1. ADD 5 feeds used by the farm but missing from the system.
  2. UPDATE prices of existing feeds to the Rapport Mensuel values (current farm
     reality). Updates BOTH Aliment.prix_unitaire AND the linked Item.standard_rate
     — Aliment.on_update only syncs reorder_level, never price, so the Item rate
     must be set explicitly.
  3. FIX the "Bicarbonate de Soduim" typo → "Bicarbonate de sodium" (renames the
     Aliment doc + its ALI-* Item; safe because stock is 0).

CMV is intentionally left alone — it is a standalone mineral mix, not part of the
daily ration sheets, so it never appears in Rapport Mensuel.

ms_pct (matière sèche %) is NOT in the Excels — left blank on new feeds for the
supervisor to fill in.

Run:
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_aliment.run --kwargs '{"dry_run": 1}'

Set dry_run=0 to commit.
"""
import frappe

# Feeds present in Rapport Mensuel but absent from the system.
NEW_ALIMENTS = [
    {"nom": "7 Expert", "type": "CONCENTRE", "prix": 1.246},
    {"nom": "Machia Genisse", "type": "CONCENTRE", "prix": 1.091},
    {"nom": "Machia Starter", "type": "CONCENTRE", "prix": 1.218},
    {"nom": "Ensilage Vece/Triticale/Avoine", "type": "ENSILAGE", "prix": 0.12},
    {"nom": "Foin de Luzerne", "type": "FOURRAGE", "prix": 0.83},
]

# {system nom_aliment: Rapport Mensuel price}. Excludes the renamed Bicarbonate
# (handled in RENAME_FIX) and CMV (not in Excels).
PRICE_UPDATES = {
    "Soja": 1.4,
    "Mais": 1.0,
    "Dreche de Brasserie": 0.19,
    "Ensilage Mais": 0.4,
    "Foin d'Avoine": 0.58,
    "Paille de Ble": 0.55,
}

# (old_name, new_name, new_price) — typo correction + price refresh.
RENAME_FIX = ("Bicarbonate de Soduim", "Bicarbonate de sodium", 1.547)


def run(dry_run=True):
    dry_run = int(dry_run)
    log = []
    added = updated = renamed = 0

    # --- 1. ADD missing feeds ---
    for a in NEW_ALIMENTS:
        if frappe.db.exists("Aliment", a["nom"]):
            log.append(f"[skip-add]   {a['nom']} already exists")
            continue
        log.append(f"[ADD]        {a['nom']} ({a['type']}, {a['prix']} DT/KG) -> auto Item ALI-{a['nom']}")
        if not dry_run:
            frappe.get_doc({
                "doctype": "Aliment",
                "nom_aliment": a["nom"],
                "type_aliment": a["type"],
                "unite": "KG",
                "prix_unitaire": a["prix"],
            }).insert(ignore_permissions=True)
        added += 1

    # --- 2. UPDATE prices (Aliment + Item.standard_rate) ---
    for nom, new_price in PRICE_UPDATES.items():
        if not frappe.db.exists("Aliment", nom):
            log.append(f"[WARN-price] target '{nom}' not found")
            continue
        old = frappe.db.get_value("Aliment", nom, "prix_unitaire")
        if old == new_price:
            log.append(f"[skip-price] {nom} already {new_price}")
            continue
        item = frappe.db.get_value("Aliment", nom, "item")
        log.append(f"[PRICE]      {nom}: {old} -> {new_price}  (Item {item})")
        if not dry_run:
            frappe.db.set_value("Aliment", nom, "prix_unitaire", new_price)
            if item:
                frappe.db.set_value("Item", item, "standard_rate", new_price)
        updated += 1

    # --- 3. FIX typo rename (Aliment + Item) ---
    old_name, new_name, new_price = RENAME_FIX
    if frappe.db.exists("Aliment", old_name):
        old_item = frappe.db.get_value("Aliment", old_name, "item")
        new_item = f"ALI-{new_name}"
        log.append(f"[RENAME]     Aliment '{old_name}' -> '{new_name}'; "
                   f"Item '{old_item}' -> '{new_item}'; price -> {new_price}")
        if not dry_run:
            frappe.rename_doc("Aliment", old_name, new_name, force=True)
            if old_item and frappe.db.exists("Item", old_item):
                frappe.rename_doc("Item", old_item, new_item, force=True)
                # rename_doc cascades the Link, but set explicitly to be safe
                frappe.db.set_value("Aliment", new_name, "item", new_item)
                frappe.db.set_value("Item", new_item, "item_name", new_name)
            target_item = new_item if frappe.db.exists("Item", new_item) else old_item
            frappe.db.set_value("Aliment", new_name, "prix_unitaire", new_price)
            if target_item:
                frappe.db.set_value("Item", target_item, "standard_rate", new_price)
        renamed += 1
    elif frappe.db.exists("Aliment", new_name):
        log.append(f"[skip-rename] already '{new_name}'")
    else:
        log.append(f"[WARN-rename] source '{old_name}' not found")

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Aliment reconcile")
    for line in log:
        print(f"  {line}")
    print(f"\nSummary: added={added}, prices_updated={updated}, renamed={renamed}")
    return {"added": added, "updated": updated, "renamed": renamed}
