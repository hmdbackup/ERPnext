"""
Comprehensive test suite for the entire HMD AGRO application.
Each run creates fresh test data with unique IDs — no leftover state.

Run with: bench execute hmd_agro.hmd_agro.tests.test_full_flow.run_all_tests
"""
import frappe
import time
from frappe.utils import today, add_days, getdate


# Unique suffix per run to avoid collisions
RUN_ID = str(int(time.time()))[-6:]
ANIMAL_ID = f"90{RUN_ID}01"  # 10-digit ID
ANIMAL_EXIT_ID = f"90{RUN_ID}02"


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
    print(f"  HMD AGRO — FULL TEST SUITE (run {RUN_ID})")
    print("=" * 70)

    results = {"pass": 0, "fail": 0}
    ctx = {}  # shared context between tests

    try:
        setup_prerequisites(ctx)

        test_animal_achat(results, ctx)
        test_animal_validation(results, ctx)
        test_insemination(results, ctx)
        test_insemination_validation(results, ctx)
        test_insemination_reussie(results, ctx)
        test_velage(results, ctx)
        test_lactation(results, ctx)
        test_traite(results, ctx)
        test_traite_validation(results, ctx)
        test_pesee(results, ctx)
        test_etat_corporel(results, ctx)
        test_traitement_medical(results, ctx)
        test_traitement_parage(results, ctx)
        test_traitement_attente_lait(results, ctx)
        test_avortement(results, ctx)
        test_alert_system(results, ctx)
        test_animal_exit(results, ctx)
        test_lock_identity(results, ctx)
        test_semence_stock(results, ctx)

    except Exception as e:
        log(f"FATAL ERROR: {e}", "FAIL")
        results["fail"] += 1
        import traceback
        traceback.print_exc()
    finally:
        cleanup_all(ctx)

    print("\n" + "=" * 70)
    print(f"  RESULTS: {results['pass']} passed, {results['fail']} failed")
    print("=" * 70 + "\n")


# ═══════════════════════════════════════════════════════════════════
# SETUP & HELPERS
# ═══════════════════════════════════════════════════════════════════

def setup_prerequisites(ctx):
    log("Setting up prerequisites...", "HEAD")

    # Batiment
    bat_name = f"TBAT-{RUN_ID}"
    frappe.get_doc({
        "doctype": "Batiment", "nom_batiment": bat_name,
        "type_batiment": "ELEVAGE", "actif": 1
    }).insert(ignore_permissions=True)
    ctx["batiment"] = bat_name

    # Lot
    lot_name = f"TLOT-{RUN_ID}"
    frappe.get_doc({
        "doctype": "Lot", "nom": lot_name,
        "batiment": bat_name, "superficie_m2": 100,
        "capacite_optimale": 20, "capacite_maximale": 30, "actif": 1
    }).insert(ignore_permissions=True)
    ctx["lot"] = lot_name

    # Taureau
    bull_name = f"TBULL-{RUN_ID}"
    frappe.get_doc({
        "doctype": "Taureau", "nom_taureau": bull_name,
        "code_taureau": f"TC{RUN_ID}", "race": "Holstein"
    }).insert(ignore_permissions=True)
    ctx["taureau"] = bull_name

    # ST5-14 (Phase C): legacy quantite_recue/quantite_restante/stock_actuel
    # gone in ST5-12. Stock now lives in Batch.batch_qty / Bin.actual_qty.
    # Seed via Material Receipts after fixture insert.
    def _seed_stock(item_code, qty, uom, batch_no=None, rate=1):
        if not item_code:
            return
        line = {
            "item_code": item_code, "qty": qty, "uom": uom, "stock_uom": uom,
            "conversion_factor": 1,
            "t_warehouse": "Magasin Principal - HMD", "basic_rate": rate,
        }
        if batch_no:
            line["batch_no"] = batch_no
        se = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
            "company": "hmd-agro", "posting_date": today(),
            "items": [line], "remarks": f"test_full_flow seed {item_code}",
        })
        se.insert(ignore_permissions=True); se.submit()

    # Semence
    sem = frappe.get_doc({
        "doctype": "Semence", "taureau": bull_name,
        "type_semence": "CONVENTIONNELLE",
        "date_reception": today(),
    })
    sem.insert(ignore_permissions=True)
    ctx["semence"] = sem.name
    _seed_stock(frappe.db.get_value("Semence", sem.name, "item"),
                 20, "Paillette", batch_no=sem.name)

    # Medicaments
    med1_name = f"TMED1-{RUN_ID}"
    frappe.get_doc({
        "doctype": "Medicament", "nom_medicament": med1_name,
        "type_medicament": "ANTIBIOTIQUE", "delai_attente_lait": 5,
    }).insert(ignore_permissions=True)
    ctx["med1"] = med1_name
    _seed_stock(frappe.db.get_value("Medicament", med1_name, "item"),
                 10, "Unit", rate=10)

    med2_name = f"TMED2-{RUN_ID}"
    frappe.get_doc({
        "doctype": "Medicament", "nom_medicament": med2_name,
        "type_medicament": "VACCIN", "delai_attente_lait": 0,
    }).insert(ignore_permissions=True)
    ctx["med2"] = med2_name
    _seed_stock(frappe.db.get_value("Medicament", med2_name, "item"),
                 50, "Unit", rate=10)

    # Mere externe
    mere_ext = frappe.db.get_value("Mere externe", {}, "name")
    if not mere_ext:
        doc = frappe.get_doc({"doctype": "Mere externe"})
        doc.insert(ignore_permissions=True)
        mere_ext = doc.name
    ctx["mere_externe"] = mere_ext

    frappe.db.commit()
    log(f"Prerequisites ready (animal IDs: {ANIMAL_ID}, {ANIMAL_EXIT_ID})")


# ═══════════════════════════════════════════════════════════════════
# PART 1: ANIMAL
# ═══════════════════════════════════════════════════════════════════

def test_animal_achat(results, ctx):
    print("\n── Part 1a: Animal (Achat) ──")

    doc = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": ANIMAL_ID,
        "categorie": "VACHE",
        "race": "Holstein",
        "date_naissance": "2020-06-15",
        "date_entree": "2020-12-01",  # required when est_achat=1
        "est_achat": 1,
        "id_mere_externe": ctx["mere_externe"],
        "id_pere": ctx["taureau"],
        "id_lot": ctx["lot"],
        "statut": "ACTIF"
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["animal"] = doc.name

    assert_test(doc.name == ANIMAL_ID, "Animal created with ID TN as name", f"Name: {doc.name}", results)
    assert_test(doc.nom_metier == ANIMAL_ID[-4:], "nom_metier = last 4 digits", f"nom_metier: {doc.nom_metier}", results)
    assert_test(doc.sexe == "F", "Sexe auto-set to F for VACHE", f"sexe: {doc.sexe}", results)
    assert_test(doc.etat_gestation == "VIDE", "etat_gestation defaults to VIDE", f"etat_gestation: {doc.etat_gestation}", results)


def test_animal_validation(results, ctx):
    print("\n── Part 1b: Animal Validations ──")

    # Bad identification format
    try:
        frappe.get_doc({
            "doctype": "Animal", "identification_tn": "BADID",
            "categorie": "VACHE", "race": "Holstein", "date_naissance": "2020-01-01",
            "est_achat": 1, "id_mere_externe": ctx["mere_externe"],
            "id_pere": ctx["taureau"], "id_lot": ctx["lot"]
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Bad ID format should fail", results)
    except Exception:
        assert_test(True, "Bad identification format blocked", "", results)
    frappe.db.rollback()

    # Future birth date
    try:
        frappe.get_doc({
            "doctype": "Animal", "identification_tn": "TEMP-70",
            "categorie": "VACHE", "race": "Holstein",
            "date_naissance": add_days(today(), 5),
            "est_achat": 1, "id_mere_externe": ctx["mere_externe"],
            "id_pere": ctx["taureau"], "id_lot": ctx["lot"]
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Future birth date should fail", results)
    except Exception:
        assert_test(True, "Future birth date blocked", "", results)
    frappe.db.rollback()

    # Non-achat without mother
    try:
        frappe.get_doc({
            "doctype": "Animal", "identification_tn": "TEMP-71",
            "categorie": "VACHE", "race": "Holstein", "date_naissance": "2020-01-01",
            "est_achat": 0, "id_pere": ctx["taureau"], "id_lot": ctx["lot"]
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Non-achat without mother should fail", results)
    except Exception:
        assert_test(True, "Non-achat without mother blocked", "", results)
    frappe.db.rollback()


# ═══════════════════════════════════════════════════════════════════
# PART 2: INSEMINATION
# ═══════════════════════════════════════════════════════════════════

def test_insemination(results, ctx):
    print("\n── Part 2a: Insemination ──")

    animal = ctx["animal"]

    # Create lactation first (needed for VACHE IA)
    lac = frappe.get_doc({
        "doctype": "Lactation", "animal": animal,
        "date_debut": "2024-01-01", "statut": "EN_COURS"
    })
    lac.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["lactation_pre_velage"] = lac.name

    # IA date: 280 days ago so velage can happen today
    ia_date = add_days(today(), -280)

    ia = frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal,
        "taureau": ctx["taureau"],
        "date_ia": ia_date,
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["ia"] = ia.name

    assert_test(ia.resultat == "EN_ATTENTE", "IA created with EN_ATTENTE", f"resultat: {ia.resultat}", results)
    assert_test(ia.lactation is not None, "IA auto-linked to lactation", f"lactation: {ia.lactation}", results)

    # Check semence stock decremented
    # ST5-14: Batch.batch_qty post-Phase C
    semence = frappe.db.get_value("Batch", ctx["semence"], "batch_qty") or 0
    assert_test(semence == 19, "Semence stock decremented (20→19)", f"stock: {semence}", results)


def test_insemination_validation(results, ctx):
    print("\n── Part 2b: Insemination Validations ──")

    animal = ctx["animal"]

    # Duplicate pending IA
    try:
        frappe.get_doc({
            "doctype": "Insemination", "animal": animal,
            "taureau": ctx["taureau"], "date_ia": today(),
            "type_semence": "CONVENTIONNELLE"
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Duplicate pending IA should fail", results)
    except Exception:
        assert_test(True, "Duplicate pending IA blocked", "", results)
    frappe.db.rollback()

    # Future date
    try:
        frappe.get_doc({
            "doctype": "Insemination", "animal": animal,
            "taureau": ctx["taureau"], "date_ia": add_days(today(), 5)
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Future IA date should fail", results)
    except Exception:
        assert_test(True, "Future IA date blocked", "", results)
    frappe.db.rollback()


def test_insemination_reussie(results, ctx):
    print("\n── Part 2c: Insemination → REUSSIE ──")

    animal = ctx["animal"]
    doc = frappe.get_doc("Insemination", ctx["ia"])
    doc.resultat = "REUSSIE"
    doc.save()
    frappe.db.commit()

    a = frappe.db.get_value("Animal", animal,
        ["etat_gestation", "id_ia_fecondante", "date_velage_prevue", "date_tarissement"], as_dict=True)

    assert_test(a.etat_gestation == "GESTANTE", "Animal → GESTANTE", f"etat_gestation: {a.etat_gestation}", results)
    assert_test(a.id_ia_fecondante == doc.name, "id_ia_fecondante set", f"id: {a.id_ia_fecondante}", results)
    assert_test(a.date_velage_prevue is not None, "date_velage_prevue set", "", results)
    assert_test(a.date_tarissement is not None, "date_tarissement set", "", results)

    expected_velage = add_days(doc.date_ia, 280)
    assert_test(str(a.date_velage_prevue) == str(expected_velage),
        f"date_velage_prevue = date_ia + 280 ({expected_velage})", f"got: {a.date_velage_prevue}", results)


# ═══════════════════════════════════════════════════════════════════
# PART 3: VELAGE
# ═══════════════════════════════════════════════════════════════════

def test_velage(results, ctx):
    print("\n── Part 3: Velage ──")

    animal = ctx["animal"]

    vel = frappe.get_doc({
        "doctype": "Velage",
        "animal": animal,
        "date_velage": today(),
        "type_velage": "FACILE",
        "nombre_veaux": "1",
        "sexe_veau1": "F",
        "vivant_veau1": 1,
        "poids_veau1": 35
    })
    vel.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["velage"] = vel.name

    assert_test(vel.name is not None, f"Velage created: {vel.name}", "Velage failed", results)

    vel.reload()
    ctx["calf"] = vel.id_veau1
    assert_test(vel.id_veau1 is not None, f"Calf created: {vel.id_veau1}", "No calf", results)

    if vel.id_veau1:
        calf = frappe.get_doc("Animal", vel.id_veau1)
        assert_test(calf.categorie == "VELLE", "Calf = VELLE (female)", f"categorie: {calf.categorie}", results)
        assert_test(calf.id_mere == animal, "Calf id_mere = mother", f"id_mere: {calf.id_mere}", results)

        pesee = frappe.db.exists("Pesee", {"animal": vel.id_veau1, "type_pesee": "NAISSANCE"})
        assert_test(pesee is not None, "Birth pesee created", "No birth pesee", results)

    ctx["lactation"] = vel.lactation
    assert_test(vel.lactation is not None, f"Lactation created: {vel.lactation}", "No lactation", results)

    a = frappe.db.get_value("Animal", animal,
        ["etat_gestation", "id_ia_fecondante", "etat_lactation"], as_dict=True)
    assert_test(a.etat_gestation == "VIDE", "Mother → VIDE", f"etat: {a.etat_gestation}", results)
    assert_test(a.id_ia_fecondante is None, "id_ia_fecondante cleared", "", results)
    assert_test(a.etat_lactation == "EN_PRODUCTION", "etat_lactation = EN_PRODUCTION", f"etat: {a.etat_lactation}", results)


# ═══════════════════════════════════════════════════════════════════
# PART 4: LACTATION
# ═══════════════════════════════════════════════════════════════════

def test_lactation(results, ctx):
    print("\n── Part 4: Lactation ──")

    animal = ctx["animal"]
    lac = ctx.get("lactation")
    assert_test(lac is not None, f"Active lactation: {lac}", "No lactation", results)
    if not lac:
        return

    doc = frappe.get_doc("Lactation", lac)
    assert_test(doc.statut == "EN_COURS", "Statut = EN_COURS", f"statut: {doc.statut}", results)

    # Duplicate EN_COURS blocked
    try:
        frappe.get_doc({
            "doctype": "Lactation", "animal": animal,
            "date_debut": today(), "statut": "EN_COURS"
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Duplicate EN_COURS should fail", results)
    except Exception:
        assert_test(True, "Duplicate EN_COURS blocked", "", results)
    frappe.db.rollback()


# ═══════════════════════════════════════════════════════════════════
# PART 5: TRAITE
# ═══════════════════════════════════════════════════════════════════

def test_traite(results, ctx):
    print("\n── Part 5a: Traite ──")

    animal = ctx["animal"]
    lac = ctx.get("lactation")
    if not lac:
        log("No lactation, skipping", "WARN")
        return

    t1 = frappe.get_doc({
        "doctype": "Traite", "animal": animal,
        "date_traite": today(), "session": "MATIN", "quantite_litres": 12.5
    })
    t1.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["traite1"] = t1.name

    assert_test(t1.lactation == lac, "Auto-linked to lactation", f"lactation: {t1.lactation}", results)

    lac_doc = frappe.get_doc("Lactation", lac)
    assert_test(lac_doc.production_totale >= 12.5, "production_totale updated", f"total: {lac_doc.production_totale}", results)

    t2 = frappe.get_doc({
        "doctype": "Traite", "animal": animal,
        "date_traite": today(), "session": "SOIR", "quantite_litres": 10.0
    })
    t2.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["traite2"] = t2.name
    assert_test(True, "SOIR traite created", "", results)


def test_traite_validation(results, ctx):
    print("\n── Part 5b: Traite Validations ──")

    animal = ctx["animal"]

    # Duplicate session
    try:
        frappe.get_doc({
            "doctype": "Traite", "animal": animal,
            "date_traite": today(), "session": "MATIN", "quantite_litres": 5
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Duplicate session should fail", results)
    except Exception:
        assert_test(True, "Duplicate session blocked", "", results)
    frappe.db.rollback()

    # Negative quantity
    try:
        frappe.get_doc({
            "doctype": "Traite", "animal": animal,
            "date_traite": add_days(today(), -1), "session": "MATIN", "quantite_litres": -5
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Negative qty should fail", results)
    except Exception:
        assert_test(True, "Negative quantity blocked", "", results)
    frappe.db.rollback()

    # Quantity > 60
    try:
        frappe.get_doc({
            "doctype": "Traite", "animal": animal,
            "date_traite": add_days(today(), -1), "session": "MATIN", "quantite_litres": 65
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Qty >60 should fail", results)
    except Exception:
        assert_test(True, "Quantity >60 blocked", "", results)
    frappe.db.rollback()


# ═══════════════════════════════════════════════════════════════════
# PART 6: PESEE
# ═══════════════════════════════════════════════════════════════════

def test_pesee(results, ctx):
    print("\n── Part 6: Pesee ──")

    animal = ctx["animal"]

    p = frappe.get_doc({
        "doctype": "Pesee", "animal": animal,
        "date_pesee": today(), "poids_kg": 550, "type_pesee": "MENSUELLE"
    })
    p.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["pesee"] = p.name

    assert_test(p.name is not None, f"Pesee created", "Failed", results)

    poids = frappe.db.get_value("Animal", animal, "dernier_poids")
    assert_test(poids == 550, "dernier_poids = 550", f"dernier_poids: {poids}", results)

    p.reload()
    assert_test(p.age_jours is not None and p.age_jours > 0, f"age_jours = {p.age_jours}", "age not set", results)

    # Future date blocked
    try:
        frappe.get_doc({
            "doctype": "Pesee", "animal": animal,
            "date_pesee": add_days(today(), 5), "poids_kg": 500, "type_pesee": "MENSUELLE"
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Future pesee should fail", results)
    except Exception:
        assert_test(True, "Future pesee date blocked", "", results)
    frappe.db.rollback()


# ═══════════════════════════════════════════════════════════════════
# PART 7: ETAT CORPOREL
# ═══════════════════════════════════════════════════════════════════

def test_etat_corporel(results, ctx):
    print("\n── Part 7: Etat Corporel ──")

    animal = ctx["animal"]

    ec = frappe.get_doc({
        "doctype": "Etat Corporel", "animal": animal,
        "date_evaluation": today(), "score": 3.5
    })
    ec.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["etat_corporel"] = ec.name

    assert_test(ec.name is not None, "Etat Corporel created", "Failed", results)

    score = frappe.db.get_value("Animal", animal, "etat_corporel")
    assert_test(score == 3.5, "Animal score = 3.5", f"score: {score}", results)

    # Invalid score
    try:
        frappe.get_doc({
            "doctype": "Etat Corporel", "animal": animal,
            "date_evaluation": add_days(today(), -1), "score": 6
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Score 6 should fail", results)
    except Exception:
        assert_test(True, "Invalid score blocked", "", results)
    frappe.db.rollback()


# ═══════════════════════════════════════════════════════════════════
# PART 8: TRAITEMENT
# ═══════════════════════════════════════════════════════════════════

def test_traitement_medical(results, ctx):
    print("\n── Part 8a: Traitement Medical ──")

    animal = ctx["animal"]
    # ST5-14: Bin.actual_qty post-Phase C
    _med1_item = frappe.db.get_value("Medicament", ctx["med1"], "item")
    stock_before = frappe.db.get_value("Bin",
        {"item_code": _med1_item, "warehouse": "Magasin Principal - HMD"},
        "actual_qty") or 0

    trt = frappe.get_doc({
        "doctype": "Traitement", "animal": animal,
        "date_traitement": today(), "type_traitement": "TRAITEMENT_MEDICAL",
        "praticien": "Dr. Test",
        "observations": "Test diagnostic",
        "medicaments": [{
            "medicament": ctx["med1"], "dose": 10,
            "unite_dose": "ml", "voie_administration": "INJECTABLE_IM"
        }]
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()
    ctx["traitement"] = trt.name

    assert_test(trt.name.startswith("TRT-"), f"Traitement created: {trt.name}", f"Name: {trt.name}", results)

    stock_after = frappe.db.get_value("Bin",
        {"item_code": _med1_item, "warehouse": "Magasin Principal - HMD"},
        "actual_qty") or 0
    assert_test(stock_after == stock_before - 1,
        f"Stock decremented: {stock_before}→{stock_after}", f"Stock: {stock_after}", results)

    a = frappe.db.get_value("Animal", animal, ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)
    assert_test(a.attente_lait_active == 1, "attente_lait = 1", f"flag: {a.attente_lait_active}", results)

    expected_fin = add_days(today(), 5)
    assert_test(str(a.date_fin_attente_lait) == str(expected_fin),
        f"date_fin = {expected_fin}", f"date_fin: {a.date_fin_attente_lait}", results)

    trt.reload()
    assert_test(str(trt.medicaments[0].date_fin_attente_lait) == str(expected_fin),
        "Child row date calculated", "", results)


def test_traitement_parage(results, ctx):
    print("\n── Part 8b: Traitement PARAGE ──")

    animal = ctx["animal"]

    trt = frappe.get_doc({
        "doctype": "Traitement", "animal": animal,
        "date_traitement": today(), "type_traitement": "PARAGE"
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    assert_test(len(trt.medicaments or []) == 0, "PARAGE has no medicaments", "", results)

    # PARAGE with medicaments should fail
    try:
        frappe.get_doc({
            "doctype": "Traitement", "animal": animal,
            "date_traitement": add_days(today(), -1), "type_traitement": "PARAGE",
            "medicaments": [{"medicament": ctx["med1"], "dose": 1, "unite_dose": "ml"}]
        }).insert(ignore_permissions=True)
        assert_test(False, "", "PARAGE with meds should fail", results)
    except Exception:
        assert_test(True, "PARAGE with medicaments blocked", "", results)
    frappe.db.rollback()

    # TRAITEMENT_MEDICAL without medicaments should fail
    try:
        frappe.get_doc({
            "doctype": "Traitement", "animal": animal,
            "date_traitement": add_days(today(), -1), "type_traitement": "TRAITEMENT_MEDICAL"
        }).insert(ignore_permissions=True)
        assert_test(False, "", "Medical without meds should fail", results)
    except Exception:
        assert_test(True, "Medical without medicaments blocked", "", results)
    frappe.db.rollback()


def test_traitement_attente_lait(results, ctx):
    print("\n── Part 8c: Attente Lait Lifecycle ──")

    animal = ctx["animal"]

    # Delete all traitements → flags should clear
    for t in frappe.get_all("Traitement", {"animal": animal}, pluck="name"):
        frappe.delete_doc("Traitement", t, force=True)
    frappe.db.commit()

    a = frappe.db.get_value("Animal", animal, "attente_lait_active")
    assert_test(a == 0, "Flags cleared after delete", f"flag: {a}", results)

    # Scheduler test: set expired flag, run scheduler
    frappe.db.set_value("Animal", animal, {
        "attente_lait_active": 1, "date_fin_attente_lait": add_days(today(), -1)
    })
    frappe.db.commit()

    from hmd_agro.hmd_agro.doctype.traitement.traitement import refresh_attente_lait
    refresh_attente_lait()

    a = frappe.db.get_value("Animal", animal, "attente_lait_active")
    assert_test(a == 0, "Scheduler cleared expired flag", f"flag: {a}", results)


# ═══════════════════════════════════════════════════════════════════
# PART 9: AVORTEMENT
# ═══════════════════════════════════════════════════════════════════

def test_avortement(results, ctx):
    print("\n── Part 9: Avortement ──")

    animal = ctx["animal"]

    # Make animal GESTANTE: close current lactation, set VIDE, create IA
    lac = frappe.db.get_value("Lactation", {"animal": animal, "statut": "EN_COURS"}, "name")
    if lac:
        lac_doc = frappe.get_doc("Lactation", lac)
        lac_doc.statut = "TARIE"
        lac_doc.flags.ignore_validate = True
        lac_doc.save()

    frappe.db.set_value("Animal", animal, {"etat_gestation": "VIDE"}, update_modified=False)
    frappe.db.commit()

    # New lactation for IA
    new_lac = frappe.get_doc({
        "doctype": "Lactation", "animal": animal,
        "date_debut": add_days(today(), -60), "statut": "EN_COURS"
    })
    new_lac.flags.ignore_validate = True
    new_lac.insert(ignore_permissions=True)

    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": today(),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)
    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    etat = frappe.db.get_value("Animal", animal, "etat_gestation")
    assert_test(etat == "GESTANTE", "Animal GESTANTE for avortement", f"etat: {etat}", results)

    avo = frappe.get_doc({
        "doctype": "Avortement", "animal": animal,
        "date_avortement": today(), "cause": "INCONNUE"
    })
    avo.insert(ignore_permissions=True)
    frappe.db.commit()

    assert_test(avo.name is not None, f"Avortement created", "Failed", results)

    a = frappe.db.get_value("Animal", animal,
        ["etat_gestation", "id_ia_fecondante"], as_dict=True)
    assert_test(a.etat_gestation == "VIDE", "Animal → VIDE", f"etat: {a.etat_gestation}", results)
    assert_test(a.id_ia_fecondante is None, "id_ia_fecondante cleared", "", results)


# ═══════════════════════════════════════════════════════════════════
# PART 10: ALERT SYSTEM
# ═══════════════════════════════════════════════════════════════════

def test_alert_system(results, ctx):
    print("\n── Part 10: Alert System ──")

    animal = ctx["animal"]
    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts, mark_alert

    # Clean alerts for this animal
    for a in frappe.get_all("Alerte", {"animal": animal}, pluck="name"):
        frappe.delete_doc("Alerte", a, force=True)
    frappe.db.commit()

    generate_alerts()
    assert_test(True, "Alert generation ran without errors", "", results)

    # Test mark_alert
    alert = frappe.get_doc({
        "doctype": "Alerte", "animal": animal,
        "type_alerte": "CHALEUR_POST_VELAGE", "date_alerte": today(),
        "raison": "Test alert", "statut": "NOUVELLE"
    })
    alert.insert(ignore_permissions=True)
    frappe.db.commit()

    mark_alert(alert.name, "traiter")
    alert.reload()
    assert_test(alert.statut == "TRAITEE", "Alert → TRAITEE", f"statut: {alert.statut}", results)
    assert_test(alert.date_traitement is not None, "date_traitement set", "", results)


# ═══════════════════════════════════════════════════════════════════
# PART 11: ANIMAL EXIT
# ═══════════════════════════════════════════════════════════════════

def test_animal_exit(results, ctx):
    print("\n── Part 11: Animal Exit (VENDU) ──")

    # Create a separate animal for exit test
    exit_animal = frappe.get_doc({
        "doctype": "Animal", "identification_tn": ANIMAL_EXIT_ID,
        "categorie": "VACHE", "race": "Holstein", "date_naissance": "2019-01-01",
        "date_entree": "2019-06-01",  # required when est_achat=1
        "est_achat": 1, "id_mere_externe": ctx["mere_externe"],
        "id_pere": ctx["taureau"], "id_lot": ctx["lot"],
        "statut": "ACTIF"
    })
    exit_animal.insert(ignore_permissions=True)
    ctx["exit_animal"] = exit_animal.name

    lac = frappe.get_doc({
        "doctype": "Lactation", "animal": exit_animal.name,
        "date_debut": add_days(today(), -30), "statut": "EN_COURS"
    })
    lac.insert(ignore_permissions=True)
    frappe.db.commit()

    exit_animal.reload()
    exit_animal.statut = "VENDU"
    exit_animal.date_sortie = today()
    exit_animal.flags.ignore_validate = True
    exit_animal.save()
    frappe.db.commit()

    lac.reload()
    assert_test(lac.statut == "INTERROMPUE", "Lactation → INTERROMPUE", f"statut: {lac.statut}", results)

    etat_lac = frappe.db.get_value("Animal", exit_animal.name, "etat_lactation")
    assert_test(etat_lac == "" or etat_lac is None, "etat_lactation cleared", f"etat: {etat_lac}", results)


# ═══════════════════════════════════════════════════════════════════
# PART 12: LOCK IDENTITY
# ═══════════════════════════════════════════════════════════════════

def test_lock_identity(results, ctx):
    print("\n── Part 12: Lock Identity Fields ──")

    animal = ctx["animal"]

    # Need a second animal to try switching
    other = ctx.get("exit_animal") or ctx.get("calf")
    if not other:
        log("No second animal for lock test, skipping", "WARN")
        return

    trt = frappe.get_doc({
        "doctype": "Traitement", "animal": animal,
        "date_traitement": today(), "type_traitement": "PARAGE"
    })
    trt.insert(ignore_permissions=True)
    frappe.db.commit()

    try:
        trt.reload()
        trt.animal = other
        trt.save()
        assert_test(False, "", "Changing animal should fail", results)
    except Exception:
        assert_test(True, "Animal field locked after creation", "", results)
    frappe.db.rollback()

    trt.reload()
    frappe.delete_doc("Traitement", trt.name, force=True)
    frappe.db.commit()


# ═══════════════════════════════════════════════════════════════════
# PART 13: SEMENCE STOCK
# ═══════════════════════════════════════════════════════════════════

def test_semence_stock(results, ctx):
    print("\n── Part 13: Semence Stock ──")

    # ST5-14 (Phase C): the pre-Phase-C test verified the legacy validate
    # constraint `quantite_restante <= quantite_recue` and that you could
    # not set quantite_restante > quantite_recue. Both legacy fields are
    # gone; stock now lives in Batch.batch_qty. The replacement scenarios
    # — Batch can't go negative (v15 Serial-and-Batch Bundle enforcement),
    # FIFO + all-empty refusal — are covered by tests/test_semence_dual_write.py.
    # Here we just sanity-check that the linked Batch exists and qty is sane.
    sem = frappe.get_doc("Semence", ctx["semence"])
    batch_qty = frappe.db.get_value("Batch", sem.name, "batch_qty") or 0
    assert_test(batch_qty >= 0,
        f"Batch.batch_qty non-negative ({batch_qty})",
        f"Batch.batch_qty negative: {batch_qty}", results)
    assert_test(sem.item and frappe.db.exists("Item", sem.item),
        f"Semence linked to Item {sem.item}",
        "Semence missing Item link", results)


# ═══════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════

def cleanup_all(ctx):
    log("Cleaning up...", "HEAD")

    animals = [ctx.get("animal"), ctx.get("exit_animal"), ctx.get("calf")]
    animals = [a for a in animals if a]

    # Delete in reverse dependency order
    for dt in ["Alerte", "Avortement", "Etat Corporel", "Pesee", "Traite", "Traitement"]:
        for name in frappe.get_all(dt, {"animal": ["in", animals]}, pluck="name"):
            try:
                frappe.delete_doc(dt, name, force=True)
            except Exception:
                pass

    # Velage (cascades: calves, lactation)
    for v in frappe.get_all("Velage", {"animal": ["in", animals]}, pluck="name"):
        try:
            frappe.delete_doc("Velage", v, force=True)
        except Exception:
            pass

    # Inseminations
    for ia in frappe.get_all("Insemination", {"animal": ["in", animals]}, pluck="name"):
        try:
            frappe.delete_doc("Insemination", ia, force=True)
        except Exception:
            pass

    # Lactations
    for l in frappe.get_all("Lactation", {"animal": ["in", animals]}, pluck="name"):
        try:
            frappe.delete_doc("Lactation", l, force=True)
        except Exception:
            pass

    # Animals (including calves created by velage)
    for a in animals:
        if frappe.db.exists("Animal", a):
            # Delete any pesees for calves first
            calves = frappe.get_all("Animal", {"id_mere": a}, pluck="name")
            for c in calves:
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

    # Medicaments
    for m in [ctx.get("med1"), ctx.get("med2")]:
        if m and frappe.db.exists("Medicament", m):
            try:
                frappe.delete_doc("Medicament", m, force=True)
            except Exception:
                pass

    # Semence
    if ctx.get("semence") and frappe.db.exists("Semence", ctx["semence"]):
        try:
            frappe.delete_doc("Semence", ctx["semence"], force=True)
        except Exception:
            pass

    # Taureau, Lot, Batiment
    for dt, name in [("Taureau", ctx.get("taureau")), ("Lot", ctx.get("lot")), ("Batiment", ctx.get("batiment"))]:
        if name and frappe.db.exists(dt, name):
            try:
                frappe.delete_doc(dt, name, force=True)
            except Exception:
                pass

    frappe.db.commit()
    log("Cleanup complete")
