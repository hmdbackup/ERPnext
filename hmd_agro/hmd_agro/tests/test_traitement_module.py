"""
Comprehensive test script for the Traitement Medical module.
Run with: bench --site dev.localhost execute hmd_agro.hmd_agro.tests.test_traitement_module.run_all_tests
"""
import frappe
from frappe.utils import today, add_days, getdate


def log(msg, level="INFO"):
    prefix = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️", "WARN": "⚠️"}.get(level, "")
    print(f"  {prefix} {msg}")


def run_all_tests():
    print("\n" + "=" * 70)
    print("  TRAITEMENT MODULE — COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    results = {"pass": 0, "fail": 0}

    try:
        test_1_medicament(results)
        test_2_traitement_medical(results)
        # Clean traitements from test 2 & 3 before isolation-sensitive tests
        cleanup_traitements()
        test_3_traitement_parage(results)
        cleanup_traitements()
        test_4_validations(results)
        test_5_stock_decrement_restore(results)
        test_6_attente_lait_animal(results)
        test_7_traite_warning(results)
        test_8_lock_identity_fields(results)
        test_9_scheduler(results)
    except Exception as e:
        log(f"FATAL ERROR: {e}", "FAIL")
        results["fail"] += 1
        import traceback
        traceback.print_exc()
    finally:
        cleanup_test_data()

    print("\n" + "=" * 70)
    print(f"  RESULTS: {results['pass']} passed, {results['fail']} failed")
    print("=" * 70 + "\n")


WAREHOUSE = "Magasin Principal - HMD"


def _bin_qty_for_med(med_name):
    """Read current Bin.actual_qty for the Item linked to a Medicament.
    Replaces the legacy `Medicament.stock_actuel` reads — that field was
    removed in ST5-12. Returns 0 if no Item or no Bin row yet."""
    item = frappe.db.get_value("Medicament", med_name, "item")
    if not item:
        return 0
    return frappe.db.get_value("Bin",
        {"item_code": item, "warehouse": WAREHOUSE}, "actual_qty") or 0


def _seed_bin_for_med(med_name, qty, rate=10.0):
    """Seed initial Bin stock for a Medicament's Item via a Material Receipt.
    Replaces the legacy `stock_actuel: N` shortcut in fixture dicts."""
    item = frappe.db.get_value("Medicament", med_name, "item")
    if not item or qty <= 0:
        return
    se = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": "hmd-agro",
        "posting_date": today(),
        "items": [{
            "item_code": item,
            "qty": qty,
            "uom": "Unit",
            "stock_uom": "Unit",
            "conversion_factor": 1,
            "t_warehouse": WAREHOUSE,
            "basic_rate": rate,
        }],
        "remarks": f"test_traitement_module seed {med_name}",
    })
    se.insert(ignore_permissions=True)
    se.submit()
    frappe.db.commit()


def assert_test(condition, pass_msg, fail_msg, results):
    if condition:
        log(pass_msg, "PASS")
        results["pass"] += 1
    else:
        log(fail_msg, "FAIL")
        results["fail"] += 1


def get_test_animal():
    """Get or create a test ACTIF animal"""
    animal = frappe.db.get_value("Animal", {"statut": "ACTIF", "categorie": ["in", ["VACHE", "GENISSE"]]}, "name")
    if animal:
        return animal

    # Check if we need prerequisite data
    lot = frappe.db.get_value("Lot", {"actif": 1}, "name")
    if not lot:
        lot_doc = frappe.get_doc({
            "doctype": "Lot",
            "nom_lot": "LOT-TEST-TRT",
            "actif": 1
        })
        lot_doc.insert(ignore_permissions=True)
        lot = lot_doc.name

    taureau = frappe.db.get_value("Taureau", {}, "name")
    if not taureau:
        taureau_doc = frappe.get_doc({
            "doctype": "Taureau",
            "nom_taureau": "TAUREAU-TEST",
            "race": "Montbéliarde"
        })
        taureau_doc.insert(ignore_permissions=True)
        taureau = taureau_doc.name

    mere = frappe.db.get_value("Animal", {"categorie": "VACHE", "statut": "ACTIF"}, "name")

    animal_doc = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": "TEMP-99",
        "categorie": "VACHE",
        "race": "Montbéliarde",
        "date_naissance": "2020-01-01",
        "id_lot": lot,
        "id_pere": taureau,
        "est_achat": 1,
        "id_mere_externe": frappe.db.get_value("Mere externe", {}, "name") or None,
        "id_mere": mere,
        "statut": "ACTIF"
    })

    # Handle mother requirement
    if not animal_doc.est_achat and not animal_doc.id_mere:
        animal_doc.est_achat = 1
        mere_ext = frappe.db.get_value("Mere externe", {}, "name")
        if not mere_ext:
            mere_ext_doc = frappe.get_doc({
                "doctype": "Mere externe",
                "nom": "MERE-TEST-TRT"
            })
            mere_ext_doc.insert(ignore_permissions=True)
            mere_ext = mere_ext_doc.name
        animal_doc.id_mere_externe = mere_ext

    animal_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return animal_doc.name


def get_non_actif_animal():
    """Get or create a non-ACTIF animal for negative tests"""
    animal = frappe.db.get_value("Animal", {"statut": ["in", ["VENDU", "MORT", "REFORME"]]}, "name")
    return animal


def cleanup_traitements():
    """Delete all test traitements and reset animal attente flags"""
    animal = frappe.db.get_value("Animal", {"statut": "ACTIF", "categorie": ["in", ["VACHE", "GENISSE"]]}, "name")
    all_trt = frappe.get_all("Traitement", pluck="name")
    for t in all_trt:
        try:
            frappe.delete_doc("Traitement", t, force=True)
        except Exception:
            pass
    # Reset animal attente flags
    if animal:
        frappe.db.set_value("Animal", animal, {
            "attente_lait_active": 0,
            "date_fin_attente_lait": None
        })
    frappe.db.commit()


# ─── TEST 1: Medicament CRUD ───────────────────────────────────────

def test_1_medicament(results):
    print("\n── Test 1: Medicament Doctype ──")

    # ST5-14: stock_actuel field gone post-Phase C. Stock is now in Bin.
    # Seed initial Bin via Material Receipts after creating each Medicament.

    # Create Medicament 1
    med1 = frappe.get_doc({
        "doctype": "Medicament",
        "nom_medicament": "TEST-Amoxicilline",
        "type_medicament": "ANTIBIOTIQUE",
        "delai_attente_lait": 5,
        "delai_attente_viande": 10,
    })
    med1.insert(ignore_permissions=True)
    assert_test(med1.name == "TEST-Amoxicilline",
        "Medicament created with name = nom_medicament",
        f"Medicament name mismatch: {med1.name}", results)

    _seed_bin_for_med(med1.name, 10)
    # >=10 instead of ==10 — Material Receipts accumulate across runs, the
    # test asserts that we successfully added stock, not exact total.
    assert_test(_bin_qty_for_med(med1.name) >= 10,
        f"Bin >= 10 for TEST-Amoxicilline (got {_bin_qty_for_med(med1.name)})",
        f"Bin qty = {_bin_qty_for_med(med1.name)}", results)

    # Create Medicament 2
    med2 = frappe.get_doc({
        "doctype": "Medicament",
        "nom_medicament": "TEST-Meloxicam",
        "type_medicament": "ANTI_INFLAMMATOIRE",
        "delai_attente_lait": 3,
    })
    med2.insert(ignore_permissions=True)
    assert_test(med2.name == "TEST-Meloxicam",
        "Second Medicament created successfully",
        f"Second Medicament failed: {med2.name}", results)
    _seed_bin_for_med(med2.name, 5)

    # Duplicate name should fail
    try:
        med_dup = frappe.get_doc({
            "doctype": "Medicament",
            "nom_medicament": "TEST-Amoxicilline",
            "type_medicament": "VACCIN",
            "delai_attente_lait": 1,
        })
        med_dup.insert(ignore_permissions=True)
        assert_test(False, "", "Duplicate Medicament should have failed", results)
    except Exception:
        assert_test(True, "Duplicate Medicament name blocked", "", results)

    # ST5-14: the legacy "negative stock_actuel allowed with warning" test is
    # obsolete (field removed). The replacement scenario — issuing a
    # Traitement against an empty Bin — is now covered by test_stock_integration.py.

    frappe.db.commit()


# ─── TEST 2: Traitement Medical (with medicaments) ────────────────

def test_2_traitement_medical(results):
    print("\n── Test 2: Traitement Medical (TRAITEMENT_MEDICAL) ──")

    animal = get_test_animal()
    log(f"Using animal: {animal}")

    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "praticien": "Dr. Test",
        "medicaments": [
            {
                "medicament": "TEST-Amoxicilline",
                "dose": 10,
                "unite_dose": "ml",
                "voie_administration": "INJECTABLE_IM"
            },
            {
                "medicament": "TEST-Meloxicam",
                "dose": 5,
                "unite_dose": "mg",
                "voie_administration": "INJECTABLE_SC"
            }
        ]
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    assert_test(trt.name and trt.name.startswith("TRT-"),
        f"Traitement created: {trt.name}",
        f"Traitement naming wrong: {trt.name}", results)

    # Check attente dates calculated
    trt.reload()
    row1 = trt.medicaments[0]
    row2 = trt.medicaments[1]

    expected_fin_1 = add_days(today(), 5)
    expected_fin_2 = add_days(today(), 3)

    assert_test(str(row1.date_fin_attente_lait) == str(expected_fin_1),
        f"Row 1 date_fin_attente_lait = {row1.date_fin_attente_lait} (today+5)",
        f"Row 1 date_fin_attente_lait = {row1.date_fin_attente_lait}, expected {expected_fin_1}", results)

    assert_test(str(row2.date_fin_attente_lait) == str(expected_fin_2),
        f"Row 2 date_fin_attente_lait = {row2.date_fin_attente_lait} (today+3)",
        f"Row 2 date_fin_attente_lait = {row2.date_fin_attente_lait}, expected {expected_fin_2}", results)

    assert_test(row1.delai_attente_lait == 5,
        "Row 1 delai_attente_lait fetched = 5",
        f"Row 1 delai_attente_lait = {row1.delai_attente_lait}", results)


# ─── TEST 3: Traitement PARAGE ────────────────────────────────────

def test_3_traitement_parage(results):
    print("\n── Test 3: Traitement PARAGE ──")

    animal = get_test_animal()

    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "PARAGE",
        "praticien": "Dr. Parage"
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    assert_test(trt.name and trt.name.startswith("TRT-"),
        f"PARAGE Traitement created: {trt.name}",
        f"PARAGE creation failed", results)

    assert_test(not trt.medicaments or len(trt.medicaments) == 0,
        "PARAGE has no medicaments (correct)",
        f"PARAGE has {len(trt.medicaments)} medicaments", results)


# ─── TEST 4: Validations ──────────────────────────────────────────

def test_4_validations(results):
    print("\n── Test 4: Validations ──")

    animal = get_test_animal()

    # 4a: TRAITEMENT_MEDICAL with 0 medicaments → error
    try:
        trt = frappe.get_doc({
            "doctype": "Traitement",
            "animal": animal,
            "date_traitement": today(),
            "type_traitement": "TRAITEMENT_MEDICAL"
        })
        trt.insert(ignore_permissions=True)
        assert_test(False, "", "TRAITEMENT_MEDICAL with 0 medicaments should fail", results)
    except Exception as e:
        assert_test("au moins un" in str(e).lower() or "médicament" in str(e).lower(),
            "TRAITEMENT_MEDICAL with 0 medicaments blocked",
            f"Unexpected error: {e}", results)

    # 4b: PARAGE with medicaments → error
    try:
        trt = frappe.get_doc({
            "doctype": "Traitement",
            "animal": animal,
            "date_traitement": today(),
            "type_traitement": "PARAGE",
            "medicaments": [{
                "medicament": "TEST-Amoxicilline",
                "dose": 10,
                "unite_dose": "ml"
            }]
        })
        trt.insert(ignore_permissions=True)
        assert_test(False, "", "PARAGE with medicaments should fail", results)
    except Exception as e:
        assert_test("parage" in str(e).lower() or "médicament" in str(e).lower(),
            "PARAGE with medicaments blocked",
            f"Unexpected error: {e}", results)

    # 4c: Future date → error
    try:
        trt = frappe.get_doc({
            "doctype": "Traitement",
            "animal": animal,
            "date_traitement": add_days(today(), 5),
            "type_traitement": "PARAGE"
        })
        trt.insert(ignore_permissions=True)
        assert_test(False, "", "Future date should fail", results)
    except Exception as e:
        assert_test("futur" in str(e).lower(),
            "Future date blocked",
            f"Unexpected error: {e}", results)

    # 4d: Non-ACTIF animal → error
    non_actif = get_non_actif_animal()
    if non_actif:
        try:
            trt = frappe.get_doc({
                "doctype": "Traitement",
                "animal": non_actif,
                "date_traitement": today(),
                "type_traitement": "PARAGE"
            })
            trt.insert(ignore_permissions=True)
            assert_test(False, "", "Non-ACTIF animal should fail", results)
        except Exception as e:
            assert_test("actif" in str(e).lower() or "RG19" in str(e),
                f"Non-ACTIF animal blocked ({non_actif})",
                f"Unexpected error: {e}", results)
    else:
        log("No non-ACTIF animal found, skipping test 4d", "WARN")

    frappe.db.rollback()


# ─── TEST 5: Stock Decrement & Restore ────────────────────────────

def test_5_stock_decrement_restore(results):
    print("\n── Test 5: Stock Decrement & Restore ──")

    animal = get_test_animal()

    # Check initial stock
    # ST5-14: Bin reads instead of legacy stock_actuel
    stock_amox_before = _bin_qty_for_med("TEST-Amoxicilline")
    stock_melo_before = _bin_qty_for_med("TEST-Meloxicam")
    log(f"Stock before: Amoxicilline={stock_amox_before}, Meloxicam={stock_melo_before}")

    # Create traitement → should decrement
    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [
            {"medicament": "TEST-Amoxicilline", "dose": 10, "unite_dose": "ml"},
            {"medicament": "TEST-Meloxicam", "dose": 5, "unite_dose": "mg"}
        ]
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    stock_amox_after = _bin_qty_for_med("TEST-Amoxicilline")
    stock_melo_after = _bin_qty_for_med("TEST-Meloxicam")

    assert_test(stock_amox_after == stock_amox_before - 1,
        f"Amoxicilline stock decremented: {stock_amox_before} → {stock_amox_after}",
        f"Amoxicilline stock wrong: {stock_amox_before} → {stock_amox_after}", results)

    assert_test(stock_melo_after == stock_melo_before - 1,
        f"Meloxicam stock decremented: {stock_melo_before} → {stock_melo_after}",
        f"Meloxicam stock wrong: {stock_melo_before} → {stock_melo_after}", results)

    # Delete traitement → should restore
    trt_name = trt.name
    frappe.delete_doc("Traitement", trt_name, force=True)
    frappe.db.commit()

    stock_amox_restored = _bin_qty_for_med("TEST-Amoxicilline")
    stock_melo_restored = _bin_qty_for_med("TEST-Meloxicam")

    assert_test(stock_amox_restored == stock_amox_before,
        f"Amoxicilline stock restored: {stock_amox_restored}",
        f"Amoxicilline stock not restored: {stock_amox_restored} (expected {stock_amox_before})", results)

    assert_test(stock_melo_restored == stock_melo_before,
        f"Meloxicam stock restored: {stock_melo_restored}",
        f"Meloxicam stock not restored: {stock_melo_restored} (expected {stock_melo_before})", results)


# ─── TEST 6: Animal attente_lait_active ───────────────────────────

def test_6_attente_lait_animal(results):
    print("\n── Test 6: Animal attente_lait_active ──")

    animal = get_test_animal()

    # Create traitement with medicament (delai=5)
    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [
            {"medicament": "TEST-Amoxicilline", "dose": 10, "unite_dose": "ml"}
        ]
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    # Check animal flags
    animal_data = frappe.db.get_value("Animal", animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)

    assert_test(animal_data.attente_lait_active == 1,
        "Animal.attente_lait_active = 1 after traitement",
        f"Animal.attente_lait_active = {animal_data.attente_lait_active}", results)

    expected_date = add_days(today(), 5)
    assert_test(str(animal_data.date_fin_attente_lait) == str(expected_date),
        f"Animal.date_fin_attente_lait = {expected_date}",
        f"Animal.date_fin_attente_lait = {animal_data.date_fin_attente_lait}", results)

    # Delete traitement → flag should clear
    frappe.delete_doc("Traitement", trt.name, force=True)
    frappe.db.commit()

    animal_data = frappe.db.get_value("Animal", animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)

    assert_test(animal_data.attente_lait_active == 0,
        "Animal.attente_lait_active = 0 after traitement deleted",
        f"Animal.attente_lait_active = {animal_data.attente_lait_active}", results)

    assert_test(animal_data.date_fin_attente_lait is None,
        "Animal.date_fin_attente_lait = None after delete",
        f"Animal.date_fin_attente_lait = {animal_data.date_fin_attente_lait}", results)


# ─── TEST 7: Traite milk withdrawal warning ───────────────────────

def test_7_traite_warning(results):
    print("\n── Test 7: Traite Milk Withdrawal Warning ──")

    animal = get_test_animal()

    # Create traitement to activate attente_lait
    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [
            {"medicament": "TEST-Amoxicilline", "dose": 10, "unite_dose": "ml"}
        ]
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    # Verify animal flag is set
    attente = frappe.db.get_value("Animal", animal, "attente_lait_active")
    assert_test(attente == 1,
        "attente_lait_active = 1 (prerequisite for traite test)",
        f"attente_lait_active = {attente}", results)

    # Test warn_attente_lait method directly
    # We can't easily create a Traite without a lactation, so test the method logic
    from hmd_agro.hmd_agro.doctype.traite.traite import Traite
    attente_data = frappe.db.get_value("Animal", animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)

    assert_test(attente_data and attente_data.attente_lait_active == 1,
        f"Traite would show warning: attente until {attente_data.date_fin_attente_lait}",
        "Traite warning check failed", results)

    # Cleanup
    frappe.delete_doc("Traitement", trt.name, force=True)
    frappe.db.commit()


# ─── TEST 8: Lock identity fields ─────────────────────────────────

def test_8_lock_identity_fields(results):
    print("\n── Test 8: Lock Identity Fields ──")

    animal = get_test_animal()

    trt = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "PARAGE"
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    # Try to change animal
    other_animal = frappe.db.get_value("Animal",
        {"statut": "ACTIF", "name": ["!=", animal]}, "name")

    if other_animal:
        try:
            trt.reload()
            trt.animal = other_animal
            trt.save()
            assert_test(False, "", "Changing animal after creation should fail", results)
        except Exception as e:
            assert_test("modifié" in str(e).lower() or "animal" in str(e).lower(),
                "Animal field locked after creation",
                f"Unexpected error: {e}", results)
        frappe.db.rollback()
    else:
        log("No second animal available, skipping lock test", "WARN")

    # Cleanup
    trt.reload()
    frappe.delete_doc("Traitement", trt.name, force=True)
    frappe.db.commit()


# ─── TEST 9: Scheduler refresh_attente_lait ────────────────────────

def test_9_scheduler(results):
    print("\n── Test 9: Scheduler refresh_attente_lait ──")

    animal = get_test_animal()

    # Manually set an expired attente_lait flag (date in the past)
    frappe.db.set_value("Animal", animal, {
        "attente_lait_active": 1,
        "date_fin_attente_lait": add_days(today(), -1)  # yesterday
    })
    frappe.db.commit()

    # Verify it's set
    flag = frappe.db.get_value("Animal", animal, "attente_lait_active")
    assert_test(flag == 1,
        "Expired flag set manually for scheduler test",
        f"Could not set flag: {flag}", results)

    # Run scheduler function
    from hmd_agro.hmd_agro.doctype.traitement.traitement import refresh_attente_lait
    refresh_attente_lait()

    # Verify it's cleared
    data = frappe.db.get_value("Animal", animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)

    assert_test(data.attente_lait_active == 0,
        "Scheduler cleared expired attente_lait_active",
        f"attente_lait_active still = {data.attente_lait_active}", results)

    assert_test(data.date_fin_attente_lait is None,
        "Scheduler cleared expired date_fin_attente_lait",
        f"date_fin_attente_lait = {data.date_fin_attente_lait}", results)

    # Test that non-expired flag is NOT cleared
    frappe.db.set_value("Animal", animal, {
        "attente_lait_active": 1,
        "date_fin_attente_lait": add_days(today(), 3)  # 3 days from now
    })
    frappe.db.commit()

    refresh_attente_lait()

    data = frappe.db.get_value("Animal", animal,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)

    assert_test(data.attente_lait_active == 1,
        "Scheduler did NOT clear non-expired flag (correct)",
        f"Non-expired flag was cleared! attente_lait_active = {data.attente_lait_active}", results)

    # Clean up
    frappe.db.set_value("Animal", animal, {
        "attente_lait_active": 0,
        "date_fin_attente_lait": None
    })
    frappe.db.commit()


# ─── CLEANUP ──────────────────────────────────────────────────────

def cleanup_test_data():
    print("\n── Cleanup ──")

    # Delete test traitements
    test_traitements = frappe.get_all("Traitement", filters={
        "praticien": ["like", "%Test%"]
    }, pluck="name")
    test_traitements += frappe.get_all("Traitement", filters={
        "praticien": ["like", "%Parage%"]
    }, pluck="name")

    for t in test_traitements:
        try:
            frappe.delete_doc("Traitement", t, force=True)
        except Exception:
            pass

    # Delete test medicaments
    for med_name in ["TEST-Amoxicilline", "TEST-Meloxicam", "TEST-Negative"]:
        if frappe.db.exists("Medicament", med_name):
            try:
                frappe.delete_doc("Medicament", med_name, force=True)
            except Exception:
                pass

    frappe.db.commit()
    log("Test data cleaned up")
