"""
Cascade & Delete rules test suite — tests deletion blocking, cascading effects,
and state restoration when records are deleted.

Run with: bench execute hmd_agro.hmd_agro.tests.test_cascade_delete.run_all_tests
"""
import frappe
import time
from frappe.utils import today, add_days

RUN_ID = str(int(time.time()))[-6:]


def log(msg, level="INFO"):
    prefix = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️ ", "WARN": "⚠️ ", "HEAD": "━━"}.get(level, "")
    print(f"  {prefix} {msg}")


def assert_test(condition, pass_msg, fail_msg, results):
    if condition:
        log(pass_msg, "PASS")
        results["pass"] += 1
    else:
        log(fail_msg, "FAIL")
        results["fail"] += 1


def run_all_tests():
    print("\n" + "=" * 70)
    print(f"  CASCADE & DELETE — TEST SUITE (run {RUN_ID})")
    print("=" * 70)

    results = {"pass": 0, "fail": 0}
    ctx = {}

    try:
        setup_base(ctx)

        test_delete_velage(results, ctx)
        test_delete_insemination_reussie(results, ctx)
        test_delete_insemination_blocked_by_velage(results, ctx)
        test_delete_lactation_blocked_by_traite(results, ctx)
        test_delete_traitement_restores_stock(results, ctx)
        test_animal_exit_closes_all(results, ctx)

    except Exception as e:
        log(f"FATAL ERROR: {e}", "FAIL")
        results["fail"] += 1
        import traceback
        traceback.print_exc()
    finally:
        cleanup(ctx)

    print("\n" + "=" * 70)
    print(f"  RESULTS: {results['pass']} passed, {results['fail']} failed")
    print("=" * 70 + "\n")


def setup_base(ctx):
    log("Setting up base data...", "HEAD")

    bat = f"DBAT-{RUN_ID}"
    frappe.get_doc({"doctype": "Batiment", "nom_batiment": bat, "type_batiment": "ELEVAGE", "actif": 1}).insert(ignore_permissions=True)
    ctx["batiment"] = bat

    lot = f"DLOT-{RUN_ID}"
    frappe.get_doc({"doctype": "Lot", "nom": lot, "batiment": bat, "superficie_m2": 100, "capacite_optimale": 20, "capacite_maximale": 30, "actif": 1}).insert(ignore_permissions=True)
    ctx["lot"] = lot

    bull = f"DBULL-{RUN_ID}"
    frappe.get_doc({"doctype": "Taureau", "nom_taureau": bull, "code_taureau": f"DC{RUN_ID}", "race": "Holstein"}).insert(ignore_permissions=True)
    ctx["taureau"] = bull

    # ST5-14 (Phase C): legacy quantite_recue/quantite_restante/stock_actuel
    # removed in ST5-12. Stock now lives in Batch.batch_qty (Semence) and
    # Bin.actual_qty (Medicament). Seed via Material Receipts below.
    sem = frappe.get_doc({"doctype": "Semence", "taureau": bull, "type_semence": "CONVENTIONNELLE", "date_reception": today()})
    sem.insert(ignore_permissions=True)
    ctx["semence"] = sem.name
    sem_item = frappe.db.get_value("Semence", sem.name, "item")
    if sem_item:
        se = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
            "company": "hmd-agro", "posting_date": today(),
            "items": [{
                "item_code": sem_item, "qty": 50, "uom": "Paillette",
                "stock_uom": "Paillette", "conversion_factor": 1,
                "t_warehouse": "Magasin Principal - HMD",
                "batch_no": sem.name, "basic_rate": 1,
            }],
            "remarks": f"test_cascade_delete seed {sem.name}",
        })
        se.insert(ignore_permissions=True); se.submit()

    med = f"DMED-{RUN_ID}"
    frappe.get_doc({"doctype": "Medicament", "nom_medicament": med, "type_medicament": "ANTIBIOTIQUE", "delai_attente_lait": 5}).insert(ignore_permissions=True)
    ctx["med"] = med
    med_item = frappe.db.get_value("Medicament", med, "item")
    if med_item:
        se = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
            "company": "hmd-agro", "posting_date": today(),
            "items": [{
                "item_code": med_item, "qty": 20, "uom": "Unit",
                "stock_uom": "Unit", "conversion_factor": 1,
                "t_warehouse": "Magasin Principal - HMD", "basic_rate": 10,
            }],
            "remarks": f"test_cascade_delete seed {med}",
        })
        se.insert(ignore_permissions=True); se.submit()

    mere = frappe.db.get_value("Mere externe", {}, "name")
    if not mere:
        doc = frappe.get_doc({"doctype": "Mere externe"})
        doc.insert(ignore_permissions=True)
        mere = doc.name
    ctx["mere_externe"] = mere

    ctx["animals"] = []
    frappe.db.commit()
    log("Base data ready")


def make_animal(ctx, suffix, categorie="VACHE"):
    animal_id = f"92{RUN_ID}{suffix:02d}"
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": animal_id,
        "categorie": categorie, "race": "Holstein",
        "date_naissance": "2020-01-01",
        "date_entree": "2020-06-01",  # required when est_achat=1
        "est_achat": 1, "id_mere_externe": ctx["mere_externe"],
        "id_pere": ctx["taureau"], "id_lot": ctx["lot"],
        "statut": "ACTIF"
    })
    doc.insert(ignore_permissions=True)
    ctx["animals"].append(animal_id)
    frappe.db.commit()
    return animal_id


# ═══════════════════════════════════════════════════════════════════
# TEST 1: DELETE VELAGE — restores mother, deletes calf & lactation
# ═══════════════════════════════════════════════════════════════════

def test_delete_velage(results, ctx):
    print("\n── Delete Velage ──")

    animal = make_animal(ctx, 1)

    # Setup: lactation + IA + REUSSIE + velage
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": "2024-01-01", "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -280),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)
    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    vel = frappe.get_doc({
        "doctype": "Velage", "animal": animal, "date_velage": today(),
        "type_velage": "FACILE", "nombre_veaux": "1",
        "sexe_veau1": "F", "vivant_veau1": 1, "poids_veau1": 30
    })
    vel.insert(ignore_permissions=True)
    frappe.db.commit()
    vel.reload()

    calf = vel.id_veau1
    new_lac = vel.lactation
    assert_test(calf is not None, f"Setup: calf created ({calf})", "No calf", results)
    assert_test(new_lac is not None, f"Setup: lactation created ({new_lac})", "No lac", results)

    # Verify mother is VIDE
    etat = frappe.db.get_value("Animal", animal, "etat_gestation")
    assert_test(etat == "VIDE", "Setup: mother VIDE", f"etat: {etat}", results)

    # DELETE velage
    frappe.delete_doc("Velage", vel.name)
    frappe.db.commit()

    # Mother should be GESTANTE again
    a = frappe.db.get_value("Animal", animal,
        ["etat_gestation", "id_ia_fecondante"], as_dict=True)
    assert_test(a.etat_gestation == "GESTANTE", "Mother → GESTANTE after delete", f"etat: {a.etat_gestation}", results)
    assert_test(a.id_ia_fecondante == ia.name, "id_ia_fecondante restored", f"ia: {a.id_ia_fecondante}", results)

    # Calf should be deleted
    assert_test(not frappe.db.exists("Animal", calf), "Calf deleted", "Calf still exists", results)

    # Lactation should be deleted
    assert_test(not frappe.db.exists("Lactation", new_lac), "Lactation deleted", "Lac still exists", results)

    # Birth pesee should be deleted
    pesee = frappe.db.exists("Pesee", {"animal": calf})
    assert_test(not pesee, "Birth pesee deleted", "Pesee still exists", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 2: DELETE INSEMINATION REUSSIE — restores animal + semence
# ═══════════════════════════════════════════════════════════════════

def test_delete_insemination_reussie(results, ctx):
    print("\n── Delete Insemination (REUSSIE) ──")

    animal = make_animal(ctx, 10)

    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": "2024-01-01", "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    # ST5-14: read Batch.batch_qty instead of legacy Semence.quantite_restante
    stock_before = frappe.db.get_value("Batch", ctx["semence"], "batch_qty") or 0

    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -30),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)

    # Stock decremented
    stock_after_insert = frappe.db.get_value("Batch", ctx["semence"], "batch_qty") or 0
    assert_test(stock_after_insert == stock_before - 1, "Stock decremented on IA insert", f"{stock_before}→{stock_after_insert}", results)

    # Mark REUSSIE
    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    etat = frappe.db.get_value("Animal", animal, "etat_gestation")
    assert_test(etat == "GESTANTE", "Animal GESTANTE after REUSSIE", f"etat: {etat}", results)

    # DELETE IA
    frappe.delete_doc("Insemination", ia.name)
    frappe.db.commit()

    # Animal restored to VIDE
    a = frappe.db.get_value("Animal", animal,
        ["etat_gestation", "id_ia_fecondante", "date_velage_prevue"], as_dict=True)
    assert_test(a.etat_gestation == "VIDE", "Animal → VIDE after IA delete", f"etat: {a.etat_gestation}", results)
    assert_test(a.id_ia_fecondante is None, "id_ia_fecondante cleared", "", results)
    assert_test(a.date_velage_prevue is None, "date_velage_prevue cleared", "", results)

    # Semence restored
    stock_after_delete = frappe.db.get_value("Batch", ctx["semence"], "batch_qty") or 0
    assert_test(stock_after_delete == stock_before, f"Semence stock restored ({stock_after_delete})", f"stock: {stock_after_delete}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 3: DELETE INSEMINATION BLOCKED BY VELAGE
# ═══════════════════════════════════════════════════════════════════

def test_delete_insemination_blocked_by_velage(results, ctx):
    print("\n── Delete Insemination — Blocked by Velage ──")

    animal = make_animal(ctx, 20)

    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": "2024-01-01", "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -280),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)
    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    vel = frappe.get_doc({
        "doctype": "Velage", "animal": animal, "date_velage": today(),
        "type_velage": "FACILE", "nombre_veaux": "1",
        "sexe_veau1": "M", "vivant_veau1": 0
    })
    vel.insert(ignore_permissions=True)
    frappe.db.commit()

    # Try to delete IA — should be blocked
    try:
        frappe.delete_doc("Insemination", ia.name)
        assert_test(False, "", "Delete IA with velage should fail", results)
    except Exception:
        assert_test(True, "Delete IA blocked (velage depends on it)", "", results)
    frappe.db.rollback()


# ═══════════════════════════════════════════════════════════════════
# TEST 4: DELETE LACTATION BLOCKED BY TRAITE
# ═══════════════════════════════════════════════════════════════════

def test_delete_lactation_blocked_by_traite(results, ctx):
    print("\n── Delete Lactation — Blocked by Traite ──")

    animal = make_animal(ctx, 30)

    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": add_days(today(), -30), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)
    frappe.db.commit()

    traite = frappe.get_doc({
        "doctype": "Traite", "animal": animal,
        "date_traite": today(), "session": "MATIN", "quantite_litres": 10
    })
    traite.insert(ignore_permissions=True)
    frappe.db.commit()

    # Try to delete lactation — should be blocked
    try:
        frappe.delete_doc("Lactation", lac.name)
        assert_test(False, "", "Delete lactation with traites should fail", results)
    except Exception:
        assert_test(True, "Delete lactation blocked (traites exist)", "", results)
    frappe.db.rollback()

    # Delete traite first, then lactation should work
    frappe.delete_doc("Traite", traite.name, force=True)
    frappe.db.commit()

    frappe.delete_doc("Lactation", lac.name)
    frappe.db.commit()
    assert_test(not frappe.db.exists("Lactation", lac.name), "Lactation deleted after traite removed", "Still exists", results)

    # Animal etat_lactation should be cleared
    etat = frappe.db.get_value("Animal", animal, "etat_lactation")
    assert_test(etat == "" or etat is None, "etat_lactation cleared", f"etat: {etat}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 5: DELETE TRAITEMENT — restores medicament stock
# ═══════════════════════════════════════════════════════════════════

def test_delete_traitement_restores_stock(results, ctx):
    print("\n── Delete Traitement — Stock Restore ──")

    animal = make_animal(ctx, 40)
    # ST5-14: read Bin instead of legacy stock_actuel
    _med_item = frappe.db.get_value("Medicament", ctx["med"], "item")
    stock_before = frappe.db.get_value("Bin",
        {"item_code": _med_item, "warehouse": "Magasin Principal - HMD"},
        "actual_qty") or 0

    trt = frappe.get_doc({
        "doctype": "Traitement", "animal": animal,
        "date_traitement": today(), "type_traitement": "TRAITEMENT_MEDICAL",
        "medicaments": [{"medicament": ctx["med"], "dose": 10, "unite_dose": "ml"}]
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    stock_after = frappe.db.get_value("Bin",
        {"item_code": _med_item, "warehouse": "Magasin Principal - HMD"},
        "actual_qty") or 0
    assert_test(stock_after == stock_before - 1, f"Stock decremented: {stock_before}→{stock_after}", "", results)

    # Check attente_lait set
    flag = frappe.db.get_value("Animal", animal, "attente_lait_active")
    assert_test(flag == 1, "attente_lait set", f"flag: {flag}", results)

    # DELETE
    frappe.delete_doc("Traitement", trt.name, force=True)
    frappe.db.commit()

    stock_restored = frappe.db.get_value("Bin",
        {"item_code": _med_item, "warehouse": "Magasin Principal - HMD"},
        "actual_qty") or 0
    assert_test(stock_restored == stock_before, f"Stock restored: {stock_restored}", f"expected {stock_before}", results)

    flag_after = frappe.db.get_value("Animal", animal, "attente_lait_active")
    assert_test(flag_after == 0, "attente_lait cleared after delete", f"flag: {flag_after}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 6: ANIMAL EXIT — closes lactation, IA, alerts
# ═══════════════════════════════════════════════════════════════════

def test_animal_exit_closes_all(results, ctx):
    print("\n── Animal Exit — Full Cascade ──")

    animal = make_animal(ctx, 50)

    # Create EN_COURS lactation
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": add_days(today(), -30), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    # Create pending IA
    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -10),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)

    # Create open alert
    alert = frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "CHALEUR_POST_VELAGE",
        "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
    })
    alert.insert(ignore_permissions=True)
    frappe.db.commit()

    # EXIT animal
    a = frappe.get_doc("Animal", animal)
    a.statut = "VENDU"
    a.date_sortie = today()
    a.flags.ignore_validate = True
    a.save()
    frappe.db.commit()

    # Lactation → INTERROMPUE
    lac.reload()
    assert_test(lac.statut == "INTERROMPUE", "Lactation → INTERROMPUE", f"statut: {lac.statut}", results)

    # IA → ECHOUEE
    ia.reload()
    assert_test(ia.resultat == "ECHOUEE", "Pending IA → ECHOUEE", f"resultat: {ia.resultat}", results)

    # Alert → NON_CONFIRMEE
    alert.reload()
    assert_test(alert.statut == "NON_CONFIRMEE", "Alert → NON_CONFIRMEE", f"statut: {alert.statut}", results)

    # etat_lactation cleared
    etat_lac = frappe.db.get_value("Animal", animal, "etat_lactation")
    assert_test(etat_lac == "" or etat_lac is None, "etat_lactation cleared", f"etat: {etat_lac}", results)


# ═══════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════

def cleanup(ctx):
    log("Cleaning up...", "HEAD")

    animals = ctx.get("animals", [])

    for dt in ["Alerte", "Avortement", "Etat Corporel", "Pesee", "Traite", "Traitement"]:
        for name in frappe.get_all(dt, {"animal": ["in", animals]}, pluck="name"):
            try:
                frappe.delete_doc(dt, name, force=True)
            except Exception:
                pass

    for v in frappe.get_all("Velage", {"animal": ["in", animals]}, pluck="name"):
        try:
            frappe.delete_doc("Velage", v, force=True)
        except Exception:
            pass

    for ia in frappe.get_all("Insemination", {"animal": ["in", animals]}, pluck="name"):
        try:
            frappe.delete_doc("Insemination", ia, force=True)
        except Exception:
            pass

    for l in frappe.get_all("Lactation", {"animal": ["in", animals]}, pluck="name"):
        try:
            frappe.delete_doc("Lactation", l, force=True)
        except Exception:
            pass

    for a in animals:
        if frappe.db.exists("Animal", a):
            for c in frappe.get_all("Animal", {"id_mere": a}, pluck="name"):
                for p in frappe.get_all("Pesee", {"animal": c}, pluck="name"):
                    try:
                        frappe.delete_doc("Pesee", p, force=True)
                    except Exception:
                        pass
                try:
                    frappe.delete_doc("Animal", c, force=True)
                except Exception:
                    pass
            try:
                frappe.delete_doc("Animal", a, force=True)
            except Exception:
                pass

    if ctx.get("med") and frappe.db.exists("Medicament", ctx["med"]):
        try:
            frappe.delete_doc("Medicament", ctx["med"], force=True)
        except Exception:
            pass

    if ctx.get("semence") and frappe.db.exists("Semence", ctx["semence"]):
        try:
            frappe.delete_doc("Semence", ctx["semence"], force=True)
        except Exception:
            pass

    for dt, key in [("Taureau", "taureau"), ("Lot", "lot"), ("Batiment", "batiment")]:
        name = ctx.get(key)
        if name and frappe.db.exists(dt, name):
            try:
                frappe.delete_doc(dt, name, force=True)
            except Exception:
                pass

    frappe.db.commit()
    log("Cleanup complete")
