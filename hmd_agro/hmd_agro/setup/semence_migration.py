"""
Sprint 5 — Semence → Item + Batch migration (post-Phase C).

Strategy:
  - One Item per (Taureau, type_semence) — e.g., "SEM-Apollo-CONV"
  - Each Semence record becomes a Batch under that Item
    - batch_id = Semence.name
    - expiry_date = Semence.date_expiration
  - Set Semence.item = the Item code; push item_defaults

New Batches start at Batch.batch_qty = 0; stock is brought in via Purchase
Receipts with batch_no = Semence.name. (Pre-Phase C the migration also
posted an opening Stock Entry from the legacy `quantite_restante` field —
that field was removed in ST5-12.)

Idempotent.

Run:
    bench --site hmd.localhost execute \\
        hmd_agro.hmd_agro.setup.semence_migration.migrate_semences
"""
import frappe
from frappe.utils import today

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)
DEFAULT_UOM = "Paillette"

TYPE_TO_ITEM_GROUP = {
    "CONVENTIONNELLE": "Semence Conventionnelle",
    "SEXEE": "Semence Sexée",
}
TYPE_SHORT = {"CONVENTIONNELLE": "CONV", "SEXEE": "SEX"}


def _item_code(taureau, type_semence):
    return f"SEM-{taureau}-{TYPE_SHORT.get(type_semence, type_semence)}"


def _ensure_item(taureau, type_semence):
    """Create the (Taureau, type_semence) Item if missing. Returns item_code."""
    code = _item_code(taureau, type_semence)
    if frappe.db.exists("Item", code):
        return code, False
    taureau_name = frappe.db.get_value("Taureau", taureau, "nom_taureau") or taureau
    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": code,
        "item_name": f"Semence {taureau_name} ({type_semence})",
        "item_group": TYPE_TO_ITEM_GROUP.get(type_semence, "Semence"),
        "stock_uom": DEFAULT_UOM,
        "is_stock_item": 1,
        "has_batch_no": 1,
        "create_new_batch": 0,  # we create batches explicitly during migration
        "include_item_in_manufacturing": 0,
        # ST5-13: real-world Inséminations must record even when batch stock
        # is stale. Mirrors aliment_migration / medicament_migration.
        "allow_negative_stock": 1,
        "description": f"Semence du taureau {taureau_name}, type {type_semence}",
    })
    item.insert(ignore_permissions=True)
    return code, True


def _ensure_batch(batch_id, item_code, expiry_date):
    """Create Batch if missing."""
    if frappe.db.exists("Batch", batch_id):
        return False
    batch = frappe.get_doc({
        "doctype": "Batch",
        "batch_id": batch_id,
        "item": item_code,
        "expiry_date": expiry_date,
        "manufacturing_date": today(),
    })
    batch.insert(ignore_permissions=True)
    return True


def _migrate_one_semence(s, verbose=False):
    """Per-record migration: ensure (taureau, type_semence) Item exists,
    create a Batch with batch_id=Semence.name, and link Semence.item.

    Used by both:
      - migrate_semences() bulk runner (existing records)
      - Semence.after_insert() hook (newly created records)

    Post-Phase C: no opening Stock Entry — Batches start at qty=0, stock
    is brought in via Purchase Receipts with batch_no = Semence.name.
    """
    from hmd_agro.hmd_agro.utils.stock_utils import (
        ensure_item_default, ensure_item_allow_negative_stock,
    )

    actions = {"items_created": 0, "batches_created": 0,
               "openings_created": 0, "linked": 0,
               "skipped": 0, "defaults_synced": 0, "neg_stock_synced": 0}

    if s.get("item"):
        if verbose:
            print(f"  [skip]      {s.name} (déjà migrée → {s.item})")
        if ensure_item_default(s.item):
            actions["defaults_synced"] = 1
            if verbose:
                print(f"              ↳ item_defaults synced")
        if ensure_item_allow_negative_stock(s.item):
            actions["neg_stock_synced"] = 1
            if verbose:
                print(f"              ↳ allow_negative_stock = 1 (ST5-13)")
        actions["skipped"] = 1
        return actions

    item_code, created_item = _ensure_item(s.taureau, s.type_semence)
    if created_item:
        if verbose:
            print(f"  [item]      {item_code}  ({s.taureau}, {s.type_semence})")
        actions["items_created"] = 1

    if _ensure_batch(s.name, item_code, s.get("date_expiration")):
        if verbose:
            print(f"              ↳ Batch {s.name} (expire {s.get('date_expiration')})")
        actions["batches_created"] = 1

    # ST5-12 (Phase C): the legacy `quantite_restante` field is gone. New
    # Semence batches start at Batch.batch_qty=0 until a Purchase Receipt is
    # posted with batch_no=Semence.name. Historical opening Stock Entries
    # (from the original Phase A backfill) are preserved in the SLE.

    frappe.db.set_value("Semence", s.name, "item", item_code)
    actions["linked"] = 1
    if ensure_item_default(item_code):
        actions["defaults_synced"] = 1
    if ensure_item_allow_negative_stock(item_code):
        actions["neg_stock_synced"] = 1
    return actions


@frappe.whitelist()
def migrate_semences():
    print("\n" + "=" * 60)
    print("  Sprint 5 — Semence → Item + Batch Migration")
    print("=" * 60)

    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse '{WAREHOUSE}' n'existe pas. Lancez stock_foundation d'abord.")

    semences = frappe.get_all("Semence",
        fields=["name", "taureau", "type_semence", "date_reception",
                "date_expiration", "prix_unitaire", "item"],
        order_by="creation")

    print(f"\n  Semences trouvées: {len(semences)}\n")

    stats = {"items_created": 0, "batches_created": 0, "openings_created": 0,
             "linked": 0, "skipped": 0, "defaults_synced": 0,
             "neg_stock_synced": 0}

    for s in semences:
        actions = _migrate_one_semence(s, verbose=True)
        for k, v in actions.items():
            stats[k] = stats.get(k, 0) + v

    frappe.db.commit()

    print("\n" + "=" * 60)
    print(f"  Items créés:                   {stats['items_created']}")
    print(f"  Batches créés:                 {stats['batches_created']}")
    print(f"  Stock Entries d'ouverture:     {stats['openings_created']}")
    print(f"  Semences liées:                {stats['linked']}")
    print(f"  Déjà migrées (skip):           {stats['skipped']}")
    print(f"  Item Defaults sync:            {stats['defaults_synced']}")
    print(f"  allow_negative_stock sync:     {stats['neg_stock_synced']}")
    print("=" * 60 + "\n")

    return stats
