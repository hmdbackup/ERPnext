"""
Sprint 5 — Médicament → Item migration (post-Phase C).

For each Medicament:
  1. Create an ERPNext Item (item_code = MED-{nom_medicament}) with
     standard_rate = Médicament.prix_unitaire and allow_negative_stock=1
  2. Set Medicament.item = the new Item
  3. Push item_defaults (company + default_warehouse) via ensure_item_default()
  4. Sync Item.standard_rate to current prix_unitaire (idempotent — covers
     re-runs after a price was added to a previously-migrated Médicament).

New Items start at Bin = 0; stock is brought in via Purchase Receipts.
(Pre-Phase C the migration also created an opening Stock Entry from the
legacy `stock_actuel` field — that field was removed in ST5-12.)

Run:
    bench --site hmd.localhost execute \\
        hmd_agro.hmd_agro.setup.medicament_migration.migrate_medicaments
"""
import frappe
from frappe.utils import today

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)
DEFAULT_UOM = "Unit"

# Medicament.type_medicament → Item Group name
TYPE_TO_ITEM_GROUP = {
    "ANTIBIOTIQUE": "Antibiotique",
    "ANTI_INFLAMMATOIRE": "Anti-inflammatoire",
    "ANTIPARASITAIRE": "Antiparasitaire",
    "VACCIN": "Vaccin",
    "HORMONE": "Hormone",
    "VITAMINE": "Vitamine",
    "AUTRE": "Autre Médicament",
}


def _migrate_one_medicament(med, verbose=False):
    """Per-record migration: ensure Item exists + link Medicament.item to it.
    Idempotent. Returns a dict of action flags.

    Used by both:
      - migrate_medicaments() bulk runner (existing records)
      - Medicament.after_insert() hook (newly created records)

    Post-Phase C: no opening Stock Entry creation — Items start at Bin=0,
    stock is brought in via Purchase Receipts.
    """
    from hmd_agro.hmd_agro.utils.stock_utils import (
        ensure_item_default, ensure_item_allow_negative_stock,
    )

    actions = {"created_item": 0, "created_opening": 0, "linked": 0,
               "skipped_existing_item": 0, "skipped_already_migrated": 0,
               "defaults_synced": 0, "price_synced": 0, "neg_stock_synced": 0}

    prix = float(med.get("prix_unitaire") or 0)

    if med.get("item"):
        if verbose:
            print(f"  [skip]      {med.nom_medicament} (déjà migré → {med.item})")
        if ensure_item_default(med.item):
            actions["defaults_synced"] = 1
            if verbose:
                print(f"              ↳ item_defaults synced")
        if _sync_item_standard_rate(med.item, prix):
            actions["price_synced"] = 1
            if verbose:
                print(f"              ↳ Item.standard_rate synced ({prix} TND)")
        if ensure_item_allow_negative_stock(med.item):
            actions["neg_stock_synced"] = 1
            if verbose:
                print(f"              ↳ allow_negative_stock = 1 (ST5-13)")
        actions["skipped_already_migrated"] = 1
        return actions

    item_code = f"MED-{med.nom_medicament}"
    item_group = TYPE_TO_ITEM_GROUP.get(med.type_medicament, "Médicament")

    if frappe.db.exists("Item", item_code):
        if verbose:
            print(f"  [link]      {med.nom_medicament} → Item {item_code} déjà existant, lien seulement")
        actions["skipped_existing_item"] = 1
    else:
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": med.nom_medicament,
            "item_group": item_group,
            "stock_uom": DEFAULT_UOM,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 0,
            "standard_rate": prix,
            # ST5-13: real-world Traitements must record even when system
            # stock is stale (forgotten Purchase Receipt, miscount, etc.).
            # Mirrors what aliment_migration does for ALI-*.
            "allow_negative_stock": 1,
            "description": f"Médicament migré depuis HMD Agro (type: {med.type_medicament})",
        })
        item.insert(ignore_permissions=True)
        if verbose:
            print(f"  [create]    Item {item_code} (groupe={item_group}, prix={prix} TND)")
        actions["created_item"] = 1

    # ST5-12 (Phase C): the legacy `stock_actuel` field is gone. New
    # Médicaments start at Bin=0 until a Purchase Receipt is posted.
    # Historical opening Stock Entries (from the original Phase A backfill)
    # are preserved in the immutable Stock Ledger.

    frappe.db.set_value("Medicament", med.name, "item", item_code)
    actions["linked"] = 1
    if ensure_item_default(item_code):
        actions["defaults_synced"] = 1
    if _sync_item_standard_rate(item_code, prix):
        actions["price_synced"] = 1
    if ensure_item_allow_negative_stock(item_code):
        actions["neg_stock_synced"] = 1
    return actions


def _sync_item_standard_rate(item_code, rate):
    """Update Item.standard_rate if it differs. Idempotent. Returns True on write."""
    current = frappe.db.get_value("Item", item_code, "standard_rate") or 0
    if float(current) == float(rate or 0):
        return False
    frappe.db.set_value("Item", item_code, "standard_rate", rate or 0)
    return True


@frappe.whitelist()
def migrate_medicaments():
    """Create Items + opening Stock Entries for all Médicaments not yet migrated."""
    print("\n" + "=" * 60)
    print("  Sprint 5 — Médicament → Item Migration")
    print("=" * 60)

    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse '{WAREHOUSE}' n'existe pas. Lancez stock_foundation d'abord.")

    medicaments = frappe.get_all("Medicament",
        fields=["name", "nom_medicament", "type_medicament",
                "prix_unitaire", "item"],
        order_by="nom_medicament")

    print(f"\n  Médicaments trouvés: {len(medicaments)}\n")

    stats = {"created_item": 0, "created_opening": 0, "linked": 0,
             "skipped_already_migrated": 0, "skipped_existing_item": 0,
             "defaults_synced": 0, "price_synced": 0, "neg_stock_synced": 0}

    for med in medicaments:
        actions = _migrate_one_medicament(med, verbose=True)
        for k, v in actions.items():
            stats[k] = stats.get(k, 0) + v

    frappe.db.commit()

    print("\n" + "=" * 60)
    print(f"  Items créés:               {stats['created_item']}")
    print(f"  Stock d'ouverture créés:   {stats['created_opening']}")
    print(f"  Médicaments liés:          {stats['linked']}")
    print(f"  Déjà migrés (skip):        {stats['skipped_already_migrated']}")
    print(f"  Item existant (lien seul): {stats['skipped_existing_item']}")
    print(f"  Item Defaults sync:        {stats['defaults_synced']}")
    print(f"  Prix unitaires sync:       {stats['price_synced']}")
    print(f"  allow_negative_stock sync: {stats['neg_stock_synced']}")
    print("=" * 60 + "\n")

    return stats
