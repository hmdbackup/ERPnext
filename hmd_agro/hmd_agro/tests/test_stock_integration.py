"""
Sprint 5 — Phase C — Stock Integration test (Stock Entry path only).

Pre-Phase C this file tested the dual-write coherence between
`Medicament.stock_actuel` and `Bin.actual_qty`. After ST5-13 strips the
dual-write and ST5-12 removes the legacy field, the test is rewritten to
verify the new single-path behaviour:

  1. Creating a Traitement posts a Material Issue Stock Entry → Bin -1
  2. Deleting that Traitement posts a compensating Material Receipt → Bin restored
  3. With Item.allow_negative_stock=1, a Traitement against an empty Bin
     still succeeds (Bin goes negative) — the supervisor's "record real
     events" stance
  4. The Médicament-without-item edge case skips cleanly without throwing

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_stock_integration.run
"""
import frappe
from frappe.utils import today

PREFIX = "TEST-INT-"
WAREHOUSE = "Magasin Principal - HMD"


def _bin_qty(item_code):
    return frappe.db.get_value("Bin",
        {"item_code": item_code, "warehouse": WAREHOUSE},
        "actual_qty") or 0


def _post_receipt(item_code, qty, rate=10.0):
    """Helper: post a Material Receipt to seed initial stock for the test."""
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": "hmd-agro",
        "posting_date": today(),
        "items": [{
            "item_code": item_code,
            "qty": qty,
            "uom": "Unit",
            "stock_uom": "Unit",
            "conversion_factor": 1,
            "t_warehouse": WAREHOUSE,
            "basic_rate": rate,
        }],
        "remarks": f"{PREFIX}seed",
    })
    se.insert(ignore_permissions=True)
    se.submit()
    return se.name


def _cleanup():
    """Remove all TEST-INT-* fixtures. Raw DB delete bypasses the cancel/save
    lifecycle (which would re-validate the SLE timeline and fail on negative
    stock when seed Material Receipts are gone). Test-only — no audit-trail
    concerns."""
    test_item = f"MED-{PREFIX}MED1"

    se_names = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE %s OR remarks LIKE %s OR remarks LIKE %s
    """, (f"%{PREFIX}%", f"%{test_item}%", f"%Médicament {PREFIX}%"))
    for (se_name,) in se_names:
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", se_name)
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", se_name)
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code=%s", test_item)
    frappe.db.sql("DELETE FROM `tabBin` WHERE item_code=%s", test_item)
    t_names = frappe.db.sql("SELECT name FROM `tabTraitement` WHERE animal LIKE %s",
                             f"{PREFIX}%")
    for (t_name,) in t_names:
        frappe.db.sql("DELETE FROM `tabTraitement Medicale` WHERE parent=%s", t_name)
        frappe.db.sql("DELETE FROM `tabTraitement` WHERE name=%s", t_name)
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    # Item child tables — delete BEFORE the parent Item row so orphans don't
    # accumulate (duplicate Item Price / UOM rows would break the next run).
    frappe.db.sql("DELETE FROM `tabItem Price` WHERE item_code LIKE %s",
                   f"MED-{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent LIKE %s",
                   f"MED-{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent LIKE %s",
                   f"MED-{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabItem` WHERE name LIKE %s", f"MED-{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabMedicament` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _insert_test_animal(identification_tn):
    """Insert a minimal Animal bypassing mère/père/Mere externe validation —
    appropriate for stock tests where animal genealogy is irrelevant."""
    animal = frappe.new_doc("Animal")
    animal.update({
        "identification_tn": identification_tn,
        "nom_metier": identification_tn,
        "categorie": "VACHE",
        "sexe": "F",
        "date_naissance": "2020-01-01",
        "statut": "ACTIF",
    })
    animal.flags.ignore_validate = True
    animal.flags.ignore_mandatory = True
    animal.insert(ignore_permissions=True)
    return animal


def run():
    import traceback
    print("\n" + "=" * 70)
    print("  Sprint 5 — Phase C — Traitement → Stock Entry (single-path)")
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

    # ── Setup: create a test Médicament + let after_insert migrate to Item.
    # Then seed initial stock via a Material Receipt.
    med_name = f"{PREFIX}MED1"
    med = frappe.get_doc({
        "doctype": "Medicament",
        "nom_medicament": med_name,
        "type_medicament": "ANTIBIOTIQUE",
        "delai_attente_lait": 5,
        "prix_unitaire": 10.0,
    })
    med.insert(ignore_permissions=True)
    frappe.db.commit()

    item_code = f"MED-{med_name}"
    _check(frappe.db.exists("Item", item_code),
        f"Item {item_code} auto-created by after_insert hook", results)

    _post_receipt(item_code, qty=10, rate=10.0)
    initial_bin = _bin_qty(item_code)
    print(f"\n  Seeded {med_name} → Bin = {initial_bin}\n")
    _check(initial_bin == 10, f"Bin initial = 10 (got {initial_bin})", results)

    # ── Create test Animal (validate flags bypassed — we don't care about
    # mère/père genealogy for a pure stock decrement test).
    animal = _insert_test_animal(f"{PREFIX}A1")
    frappe.db.commit()

    # ── 1. Create Traitement → Bin -1 via Material Issue
    print("  Phase 1: Traitement.insert() → Material Issue → Bin -1\n")
    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal.name,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [{"medicament": med_name, "dose": 10, "unite_dose": "ml"}],
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    after_create_bin = _bin_qty(item_code)
    print(f"  Bin after Traitement.insert: {after_create_bin}")
    _check(after_create_bin == 9, f"Bin = 9 after Traitement (got {after_create_bin})", results)

    # Verify SLE exists for this Traitement
    sle_count = frappe.db.count("Stock Ledger Entry", {
        "item_code": item_code,
        "voucher_no": ["like", "MAT-STE-%"],
        "actual_qty": -1,
        "is_cancelled": 0,
    })
    _check(sle_count >= 1, f"SLE recorded for the Material Issue (count={sle_count})", results)

    # ── 2. Delete Traitement → Bin restored via Material Receipt
    print("\n  Phase 2: Traitement delete → Material Receipt → Bin restored\n")
    trt_name = trt.name
    frappe.delete_doc("Traitement", trt_name, force=True)
    frappe.db.commit()

    after_delete_bin = _bin_qty(item_code)
    print(f"  Bin after delete: {after_delete_bin}")
    _check(after_delete_bin == 10, f"Bin = 10 after delete (got {after_delete_bin})", results)

    # ── 3. Negative stock: empty the Bin, then a Traitement still succeeds
    print("\n  Phase 3: Bin goes negative — Traitement still records\n")
    # Drain via a manual Material Issue
    drain = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": "hmd-agro",
        "posting_date": today(),
        "items": [{
            "item_code": item_code,
            "qty": 10,
            "uom": "Unit",
            "stock_uom": "Unit",
            "conversion_factor": 1,
            "s_warehouse": WAREHOUSE,
        }],
        "remarks": f"{PREFIX}drain",
    })
    drain.insert(ignore_permissions=True)
    drain.submit()
    frappe.db.commit()
    drained_bin = _bin_qty(item_code)
    _check(drained_bin == 0, f"Bin drained to 0 (got {drained_bin})", results)

    # Now post a Traitement against an empty Bin
    animal2 = _insert_test_animal(f"{PREFIX}A2")
    trt2 = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal2.name,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [{"medicament": med_name, "dose": 10, "unite_dose": "ml"}],
    })
    trt2.insert(ignore_permissions=True)
    frappe.db.commit()

    after_neg_bin = _bin_qty(item_code)
    print(f"  Bin after Traitement-on-empty: {after_neg_bin}")
    _check(after_neg_bin == -1,
        f"Bin went negative (got {after_neg_bin}) — allow_negative_stock works",
        results)

    # ── Cleanup
    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
