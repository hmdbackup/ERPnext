"""
Sprint 5 — Phase A — Step 4: Aliment → Item migration.

For each existing Aliment:
  1. Create an ERPNext Item (item_code = ALI-{nom_aliment})
  2. Set Aliment.item = the new Item

No opening Stock Entry — Aliment never had stock tracking. Stock starts at 0.
Receipt workflow comes in Phase B.

Idempotent.

Run:
    bench --site hmd.localhost execute \\
        hmd_agro.hmd_agro.setup.aliment_migration.migrate_aliments
"""
import frappe

# Aliment.type_aliment → Item Group name
TYPE_TO_ITEM_GROUP = {
    "CONCENTRE": "Concentré",
    "FOURRAGE": "Fourrage",
    "MINERAL": "Minéral",
    "ENSILAGE": "Ensilage",
    "PAILLE": "Paille",
    "SUPPLEMENT": "Supplément",
}

# Aliment.unite → ERPNext UOM name
UNITE_TO_UOM = {
    "KG": "Kg",
    "GRAMME": "Gram",
}


def _migrate_one_aliment(ali, verbose=False):
    """Per-record migration: ensure Item exists + link Aliment.item to it.
    No opening Stock Entry — Aliment never had stock tracking; receipts come
    from the Réception Rapide UI in Phase B.

    Used by both:
      - migrate_aliments() bulk runner (existing records)
      - Aliment.after_insert() hook (newly created records)
    """
    from hmd_agro.hmd_agro.utils.stock_utils import ensure_item_default

    actions = {"created_item": 0, "linked": 0, "skipped_existing_item": 0,
               "skipped_already_migrated": 0, "defaults_synced": 0}

    if ali.get("item"):
        if verbose:
            print(f"  [skip]      {ali.nom_aliment} (déjà migré → {ali.item})")
        if ensure_item_default(ali.item):
            actions["defaults_synced"] = 1
            if verbose:
                print(f"              ↳ item_defaults synced")
        actions["skipped_already_migrated"] = 1
        return actions

    item_code = f"ALI-{ali.nom_aliment}"
    item_group = TYPE_TO_ITEM_GROUP.get(ali.type_aliment, "Aliment")
    uom = UNITE_TO_UOM.get(ali.unite, "Unit")

    if frappe.db.exists("Item", item_code):
        if verbose:
            print(f"  [link]      {ali.nom_aliment} → Item {item_code} déjà existant, lien seulement")
        actions["skipped_existing_item"] = 1
    else:
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": ali.nom_aliment,
            "item_group": item_group,
            "stock_uom": uom,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 0,
            "standard_rate": ali.get("prix_unitaire") or 0,
            # Required by feed_distribution.py — daily Material Issues will
            # frequently push Bin below 0 between supplier deliveries. Mirrors
            # what init_feed_distribution.py applies to existing ALI-* Items.
            # MED-* and SEM-* deliberately do NOT set this (consumption is
            # tied to actual events: Traitement/Insémination — never overshoots).
            "allow_negative_stock": 1,
            "description": (f"Aliment migré depuis HMD Agro "
                            f"(type: {ali.type_aliment}, MS: {ali.get('ms_pct')}%)"),
        })
        item.insert(ignore_permissions=True)
        if verbose:
            print(f"  [create]    Item {item_code}  (groupe={item_group}, "
                  f"uom={uom}, prix={ali.get('prix_unitaire')} TND)")
        actions["created_item"] = 1

    frappe.db.set_value("Aliment", ali.name, "item", item_code)
    actions["linked"] = 1
    if ensure_item_default(item_code):
        actions["defaults_synced"] = 1
    return actions


@frappe.whitelist()
def migrate_aliments():
    """Create Items for all Aliments not yet migrated."""
    print("\n" + "=" * 60)
    print("  Sprint 5 — Aliment → Item Migration")
    print("=" * 60)

    aliments = frappe.get_all("Aliment",
        fields=["name", "nom_aliment", "type_aliment", "unite",
                "prix_unitaire", "ms_pct", "item"],
        order_by="nom_aliment")

    print(f"\n  Aliments trouvés: {len(aliments)}\n")

    stats = {"created_item": 0, "linked": 0,
             "skipped_already_migrated": 0, "skipped_existing_item": 0,
             "defaults_synced": 0}

    for ali in aliments:
        actions = _migrate_one_aliment(ali, verbose=True)
        for k, v in actions.items():
            stats[k] = stats.get(k, 0) + v

    frappe.db.commit()

    print("\n" + "=" * 60)
    print(f"  Items créés:               {stats['created_item']}")
    print(f"  Aliments liés:             {stats['linked']}")
    print(f"  Déjà migrés (skip):        {stats['skipped_already_migrated']}")
    print(f"  Item existant (lien seul): {stats['skipped_existing_item']}")
    print(f"  Item Defaults sync:        {stats['defaults_synced']}")
    print("=" * 60 + "\n")

    return stats
