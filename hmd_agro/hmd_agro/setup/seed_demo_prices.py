"""
Sprint 5 — Step 3: Seed demo Purchase Receipts (as Stock Entry Material
Receipts) at real prices so Bin.valuation_rate becomes non-zero for every
Item. After this runs, every future Material Issue (Traitement decrement,
Insémination decrement, future Aliment ration generator) records a non-zero
stock_value_difference in the SLE — which is what ST5-09 / ST5-10 reports
will aggregate over.

ADDITIVE ONLY: this script only POSTS new Stock Entries. It does NOT modify,
cancel, or delete any existing document. Re-running is safe — entries are
tagged with SEED_MARKER in `remarks` and skipped on subsequent runs.

What gets posted per product type:
  • Médicament : +10 units per Item @ Médicament.prix_unitaire (Item-level)
  • Aliment    : +100 kg/g per Item @ Aliment.prix_unitaire (Item-level)
  • Semence    : +10 paillettes per Batch @ Semence.prix_unitaire (Batch-level)
                 only for batches with Batch.batch_qty > 0 (post-Phase C —
                 pre-Phase C this filtered by the legacy `quantite_restante`)

Skip rules:
  • prix_unitaire == 0   → skipped (don't seed at zero)
  • item field empty     → skipped (not migrated yet — re-run migrations first)
  • already seeded       → skipped (idempotent via SEED_MARKER in remarks)

FIFO note: existing rate-0 stock will still be consumed first on future
Material Issues (FIFO). To see ST5-09 / ST5-10 reports reflect real costs,
either wait for old stock to cycle through, or post fresh real-priced
consumption AFTER this seed runs.

Run:
    docker exec frappe_docker_devcontainer-frappe-1 bash -lc \\
      "cd /workspace/development/frappe-bench && bench --site hmd.localhost execute \\
       hmd_agro.hmd_agro.setup.seed_demo_prices.run"
"""
import frappe
from frappe.utils import today

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_COMPANY as COMPANY,
    DEFAULT_WAREHOUSE as WAREHOUSE,
)
SEED_MARKER = "SPRINT5_DEMO_SEED"

SEED_QTY = {
    "Medicament": 10,
    "Aliment": 100,
    "Semence": 10,
}


def _already_seeded(item_code, batch_no=None):
    """Return True if a submitted Stock Entry tagged with SEED_MARKER exists
    for this item (and batch). Used for idempotency on re-runs."""
    sql = """
        SELECT se.name FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.docstatus = 1
          AND se.remarks LIKE %s
          AND sed.item_code = %s
    """
    params = [f"%{SEED_MARKER}%", item_code]
    if batch_no:
        sql += " AND sed.batch_no = %s"
        params.append(batch_no)
    sql += " LIMIT 1"
    return bool(frappe.db.sql(sql, tuple(params)))


def _post_receipt(item_code, qty, rate, uom, source_label, batch_no=None):
    """Build + insert + submit a single-line Stock Entry Material Receipt.
    Inlined here (does NOT touch utils/stock_utils.create_stock_movement which
    is shared with Traitement/Insémination dual-write code).
    Returns the SE name on success."""
    item_line = {
        "item_code": item_code,
        "qty": qty,
        "uom": uom,
        "stock_uom": uom,
        "conversion_factor": 1,
        "t_warehouse": WAREHOUSE,
        "basic_rate": rate,
        # allow_zero_valuation_rate left at 0 — we want ERPNext to validate
        # that rate>0, since the whole point of this seed is non-zero prices.
    }
    if batch_no:
        item_line["batch_no"] = batch_no

    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": COMPANY,
        "posting_date": today(),
        "items": [item_line],
        "remarks": f"{SEED_MARKER} — {source_label}",
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


def _seed_simple(doctype, prefix):
    """Generic loop for Médicament + Aliment (one Item per master record)."""
    print(f"\n  ── {doctype} ──")
    qty = SEED_QTY[doctype]
    masters = frappe.get_all(
        doctype,
        fields=["name", "item", "prix_unitaire"],
        order_by="name",
    )
    stats = {"seeded": 0, "skipped_no_price": 0, "skipped_already_seeded": 0,
             "skipped_no_item": 0, "errors": 0}

    for m in masters:
        if not m.item:
            print(f"     [skip-no-item] {m.name} (champ `item` vide)")
            stats["skipped_no_item"] += 1
            continue
        prix = float(m.prix_unitaire or 0)
        if prix <= 0:
            print(f"     [skip-no-price] {m.name} (prix_unitaire={prix})")
            stats["skipped_no_price"] += 1
            continue
        if _already_seeded(m.item):
            print(f"     [skip-seeded] {m.name} (déjà seedé)")
            stats["skipped_already_seeded"] += 1
            continue

        uom = frappe.db.get_value("Item", m.item, "stock_uom") or "Unit"
        try:
            se_name = _post_receipt(m.item, qty, prix, uom,
                                     source_label=f"{doctype} {m.name}")
            print(f"     [seed]      {m.item:35s} +{qty} {uom} @ {prix} TND → SE={se_name}")
            stats["seeded"] += 1
            frappe.db.commit()  # commit per row so partial runs are preserved
        except Exception as e:
            print(f"     [ERROR]     {m.item}: {type(e).__name__}: {e}")
            stats["errors"] += 1
            frappe.db.rollback()
    return stats


def _seed_semence():
    """Per-batch loop. For each Semence with Batch.batch_qty > 0 and prix>0,
    post a Stock Entry Material Receipt for that batch. ST5-12: pre-Phase C
    this filtered by `Semence.quantite_restante > 0`; now reads `Batch.batch_qty`
    since the legacy column is gone."""
    print(f"\n  ── Semence (par batch) ──")
    qty = SEED_QTY["Semence"]
    masters = frappe.get_all(
        "Semence",
        fields=["name", "item", "prix_unitaire", "taureau"],
        order_by="name",
    )
    stats = {"seeded": 0, "skipped_no_price": 0, "skipped_already_seeded": 0,
             "skipped_no_item": 0, "skipped_empty": 0, "errors": 0}

    for s in masters:
        if not s.item:
            print(f"     [skip-no-item] {s.name}")
            stats["skipped_no_item"] += 1
            continue
        batch_qty = frappe.db.get_value("Batch", s.name, "batch_qty") or 0
        if batch_qty <= 0:
            print(f"     [skip-empty] {s.name} (Batch.batch_qty={batch_qty} — batch exhausted)")
            stats["skipped_empty"] += 1
            continue
        prix = float(s.prix_unitaire or 0)
        if prix <= 0:
            print(f"     [skip-no-price] {s.name} (prix_unitaire={prix})")
            stats["skipped_no_price"] += 1
            continue
        if _already_seeded(s.item, batch_no=s.name):
            print(f"     [skip-seeded] {s.name} (déjà seedé)")
            stats["skipped_already_seeded"] += 1
            continue

        uom = frappe.db.get_value("Item", s.item, "stock_uom") or "Paillette"
        try:
            se_name = _post_receipt(s.item, qty, prix, uom,
                                     source_label=f"Semence {s.name} (batch)",
                                     batch_no=s.name)
            print(f"     [seed]      {s.item:25s} batch={s.name:20s} "
                  f"+{qty} {uom} @ {prix} TND → SE={se_name}")
            stats["seeded"] += 1
            frappe.db.commit()
        except Exception as e:
            print(f"     [ERROR]     {s.name}: {type(e).__name__}: {e}")
            stats["errors"] += 1
            frappe.db.rollback()
    return stats


@frappe.whitelist()
def run():
    print("\n" + "=" * 70)
    print("  Sprint 5 — Step 3: Seed demo prices via Stock Entry Material Receipt")
    print("=" * 70)
    print(f"  Marker (idempotency): {SEED_MARKER}")
    print(f"  Warehouse:            {WAREHOUSE}")
    print(f"  Posting date:         {today()}")

    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse '{WAREHOUSE}' n'existe pas. Lancer stock_foundation d'abord.")

    s_med = _seed_simple("Medicament", "MED-")
    s_ali = _seed_simple("Aliment", "ALI-")
    s_sem = _seed_semence()

    print("\n" + "=" * 70)
    print("  Résumé:")
    for label, stats in [("Médicament", s_med), ("Aliment", s_ali), ("Semence", s_sem)]:
        line = ", ".join(f"{k}={v}" for k, v in stats.items() if v)
        print(f"    {label:12s}: {line or 'aucune action'}")
    print("=" * 70)
    print("  Prochaine étape: re-run verify_native_valuation.run pour confirmer")
    print("  que les Items ont maintenant valuation_rate > 0.")
    print("=" * 70 + "\n")
