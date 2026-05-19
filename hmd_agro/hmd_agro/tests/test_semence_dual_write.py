"""
Sprint 5 — Phase C — Insémination → Stock Entry test (Stock Module only).

Pre-Phase C this file tested the dual-write coherence between
`Semence.quantite_restante` and `Batch.batch_qty`. Post-Phase C, the legacy
field is gone and the Stock Entry path is the single source of truth.

This rewrite covers the new Phase C behaviours:

  1. Insémination posts a Material Issue with batch_no = Semence.name → Bin -1
  2. Insémination delete posts a compensating Material Receipt → Bin restored
  3. Batch picker (`_pick_semence_batch`): FIFO oldest-first AMONG batches
     with Bin>0; falls back to oldest batch overall when all are depleted
  4. With allow_negative_stock=1 on SEM-*, a depleted batch still records the
     Insémination — the supervisor's "record real events" stance

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_semence_dual_write.run
"""
import frappe
from frappe.utils import today, add_days

PREFIX = "TEST-INS-"
WAREHOUSE = "Magasin Principal - HMD"


def _batch_qty(batch_id):
    """Per-batch stock — Batch.batch_qty is auto-maintained by ERPNext.
    In v15 the tabBin table no longer carries batch_no (Serial-and-Batch
    Bundle replaced it); this is the canonical per-batch read."""
    return frappe.db.get_value("Batch", batch_id, "batch_qty") or 0


def _bin_qty_item(item_code):
    """Item-level total across all batches."""
    return frappe.db.get_value("Bin",
        {"item_code": item_code, "warehouse": WAREHOUSE},
        "actual_qty") or 0


def _cleanup():
    """Raw DB delete of test fixtures (test-only, no audit-trail concerns)."""
    test_item_pattern = f"SEM-{PREFIX}%"
    se_names = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE %s OR remarks LIKE %s
    """, (f"%{PREFIX}%", f"%batch {PREFIX}%"))
    for (n,) in se_names:
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", n)
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", n)
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code LIKE %s",
                  test_item_pattern)
    frappe.db.sql("DELETE FROM `tabBin` WHERE item_code LIKE %s", test_item_pattern)
    for ia in frappe.get_all("Insemination", filters={"name": ["like", f"%{PREFIX}%"]}):
        frappe.db.sql("DELETE FROM `tabInsemination` WHERE name=%s", ia.name)
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    sem_names = [r[0] for r in frappe.db.sql(
        "SELECT name FROM `tabSemence` WHERE name LIKE %s", f"%{PREFIX}%")]
    for sn in sem_names:
        frappe.db.sql("DELETE FROM `tabSemence` WHERE name=%s", sn)
        frappe.db.sql("DELETE FROM `tabBatch` WHERE name=%s", sn)
    # Item child tables before Item
    frappe.db.sql("DELETE FROM `tabItem Price` WHERE item_code LIKE %s",
                   test_item_pattern)
    frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent LIKE %s",
                   test_item_pattern)
    frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent LIKE %s",
                   test_item_pattern)
    frappe.db.sql("DELETE FROM `tabItem` WHERE name LIKE %s", test_item_pattern)
    frappe.db.sql("DELETE FROM `tabTaureau` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _insert_test_animal(identification_tn):
    """Minimal Animal — bypass mère/père validation (genealogy irrelevant)."""
    animal = frappe.new_doc("Animal")
    animal.update({
        "identification_tn": identification_tn,
        "nom_metier": identification_tn,
        "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF",
        "etat_lactation": "EN_PRODUCTION",
        "etat_gestation": "VIDE",
        "date_naissance": "2020-01-01",
    })
    animal.flags.ignore_validate = True
    animal.flags.ignore_mandatory = True
    animal.insert(ignore_permissions=True)
    return animal


def _post_receipt_for_batch(item_code, batch_no, qty, rate):
    """Helper: seed initial stock for a batch via Material Receipt."""
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": "hmd-agro",
        "posting_date": today(),
        "items": [{
            "item_code": item_code,
            "qty": qty,
            "uom": "Paillette",
            "stock_uom": "Paillette",
            "conversion_factor": 1,
            "t_warehouse": WAREHOUSE,
            "batch_no": batch_no,
            "basic_rate": rate,
        }],
        "remarks": f"{PREFIX}seed-{batch_no}",
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


def run():
    import traceback
    print("\n" + "=" * 70)
    print("  Sprint 5 — Phase C — Insémination → Stock Entry (single-path)")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}

    _cleanup()

    # ── Setup: Taureau + 2 Semence batches (different reception dates so we
    # can test FIFO oldest-first ordering)
    taureau = frappe.get_doc({
        "doctype": "Taureau", "nom_taureau": f"{PREFIX}BULL",
        "code_taureau": f"{PREFIX}001", "race": "Holstein",
    })
    taureau.name = f"{PREFIX}BULL"
    taureau.db_insert()

    # Older batch (will be FIFO-preferred)
    sem_old = frappe.get_doc({
        "doctype": "Semence",
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_reception": add_days(today(), -30),
        "date_expiration": "2030-01-01",
        "prix_unitaire": 50,
    })
    sem_old.flags.ignore_mandatory = True
    sem_old.insert(ignore_permissions=True)

    # Newer batch
    sem_new = frappe.get_doc({
        "doctype": "Semence",
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_reception": today(),
        "date_expiration": "2030-01-01",
        "prix_unitaire": 60,
    })
    sem_new.flags.ignore_mandatory = True
    sem_new.insert(ignore_permissions=True)
    frappe.db.commit()

    item_code = f"SEM-{taureau.name}-CONV"
    _check(frappe.db.exists("Item", item_code),
        f"Item {item_code} auto-created by after_insert hook", results)
    _check(frappe.db.exists("Batch", sem_old.name),
        f"Batch {sem_old.name} auto-created", results)
    _check(frappe.db.exists("Batch", sem_new.name),
        f"Batch {sem_new.name} auto-created", results)

    # Seed both batches with stock
    _post_receipt_for_batch(item_code, sem_old.name, qty=5, rate=50)
    _post_receipt_for_batch(item_code, sem_new.name, qty=5, rate=60)
    _check(_batch_qty(sem_old.name) == 5,
        f"Bin[old]={_batch_qty(sem_old.name)}", results)
    _check(_batch_qty(sem_new.name) == 5,
        f"Bin[new]={_batch_qty(sem_new.name)}", results)

    # Distinct animals per phase — Insémination validator blocks same-animal
    # back-to-back IAs while one is still in EN_ATTENTE state.
    animal1 = _insert_test_animal(f"{PREFIX}A1")
    animal2 = _insert_test_animal(f"{PREFIX}A2")
    animal3 = _insert_test_animal(f"{PREFIX}A3")
    frappe.db.commit()

    # ── 1. First Insémination → should hit OLDEST batch (FIFO)
    print("\n  Phase 1: Insémination → FIFO oldest batch first\n")
    ia1 = frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal1.name,
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_ia": today(),
        "resultat": "EN_ATTENTE",
    })
    ia1.insert(ignore_permissions=True)
    frappe.db.commit()
    _check(_batch_qty(sem_old.name) == 4,
        f"Old batch decremented (Bin={_batch_qty(sem_old.name)})", results)
    _check(_batch_qty(sem_new.name) == 5,
        f"New batch untouched (Bin={_batch_qty(sem_new.name)})", results)

    # ── 2. Delete Insémination → Material Receipt on most-recent batch (new)
    print("\n  Phase 2: Delete → Material Receipt on most-recent batch\n")
    frappe.delete_doc("Insemination", ia1.name, ignore_permissions=True)
    frappe.db.commit()
    # Restore picks "most recent" (newer batch) — FIFO is asymmetric by design
    _check(_batch_qty(sem_new.name) == 6,
        f"Newest batch restored +1 (Bin={_batch_qty(sem_new.name)})",
        results)

    # ── 3. Drain old batch and verify FIFO falls through to the new batch
    print("\n  Phase 3: Drain oldest → FIFO falls through to newer\n")
    drain = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": "hmd-agro",
        "posting_date": today(),
        "items": [{
            "item_code": item_code,
            "qty": 4, "uom": "Paillette", "stock_uom": "Paillette",
            "conversion_factor": 1,
            "s_warehouse": WAREHOUSE,
            "batch_no": sem_old.name,
        }],
        "remarks": f"{PREFIX}drain-old",
    })
    drain.insert(ignore_permissions=True)
    drain.submit()
    frappe.db.commit()
    _check(_batch_qty(sem_old.name) == 0,
        f"Old batch drained (Bin={_batch_qty(sem_old.name)})", results)

    ia2 = frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal2.name,
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_ia": today(),
        "resultat": "EN_ATTENTE",
    })
    ia2.insert(ignore_permissions=True)
    frappe.db.commit()
    # Now FIFO should skip the depleted old batch and pick the new one
    _check(_batch_qty(sem_new.name) == 5,
        f"FIFO fell through to new batch (Bin[new]={_batch_qty(sem_new.name)})",
        results)

    # ── 4. Drain everything → next IA still records (fallback to oldest)
    print("\n  Phase 4: All batches empty → IA records but NO Stock Entry\n")
    # v15 ERPNext enforces batch-level negative stock independently of
    # Item.allow_negative_stock. So when all batches are at qty=0, the picker
    # returns None and decrement_semence_stock returns early without posting
    # a Material Issue. The IA doc itself still saves (after_insert is
    # non-blocking) and the operator sees a red msgprint asking them to
    # post a Purchase Receipt before the IA's stock movement can be recorded.
    drain2 = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": "hmd-agro",
        "posting_date": today(),
        "items": [{
            "item_code": item_code,
            "qty": 5, "uom": "Paillette", "stock_uom": "Paillette",
            "conversion_factor": 1,
            "s_warehouse": WAREHOUSE,
            "batch_no": sem_new.name,
        }],
        "remarks": f"{PREFIX}drain-new",
    })
    drain2.insert(ignore_permissions=True)
    drain2.submit()
    frappe.db.commit()

    ia3 = frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal3.name,
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_ia": today(),
        "resultat": "EN_ATTENTE",
    })
    ia3.insert(ignore_permissions=True)
    frappe.db.commit()

    _check(frappe.db.exists("Insemination", ia3.name),
        "IA doc recorded (non-blocking)", results)
    se_for_ia3 = frappe.db.count("Stock Entry", {
        "remarks": ["like", f"%Insemination {ia3.name}%"],
    })
    _check(se_for_ia3 == 0,
        f"No Stock Entry posted (all batches at 0) — found {se_for_ia3}",
        results)
    # Batches still at 0 (nothing was posted)
    _check(_batch_qty(sem_old.name) == 0 and _batch_qty(sem_new.name) == 0,
        f"Both batches still at 0 (old={_batch_qty(sem_old.name)}, "
        f"new={_batch_qty(sem_new.name)})", results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
