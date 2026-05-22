"""
Alert System test suite — tests every alert type, generation, buttons, and cascades.
Each alert type gets an ideal animal in the exact state needed.

Run with: bench execute hmd_agro.hmd_agro.tests.test_alert_system.run_all_tests
"""
import frappe
import time
from frappe.utils import today, add_days, add_months, getdate

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
    print(f"  ALERT SYSTEM — TEST SUITE (run {RUN_ID})")
    print("=" * 70)

    results = {"pass": 0, "fail": 0}
    ctx = {}

    try:
        setup_base(ctx)

        test_chaleur_genisse(results, ctx)
        test_chaleur_post_velage(results, ctx)
        test_verification_j21(results, ctx)
        test_tarissement(results, ctx)
        test_velage_imminent(results, ctx)
        test_alert_close_on_ia_creation(results, ctx)
        test_alert_close_on_velage(results, ctx)
        test_alert_close_on_ia_echouee(results, ctx)
        test_alert_close_on_animal_exit(results, ctx)
        # Phase 1 — HIGH-priority gap tests (added 2026-05-19)
        test_avortement_closes_alerts(results, ctx)
        test_j50_lifecycle(results, ctx)
        test_delvo_end_to_end(results, ctx)
        # Phase 2 — MED-priority gap tests (added 2026-05-19)
        test_alert_close_on_animal_exit_other_statuses(results, ctx)
        test_ia_reussie_animal_side_effects(results, ctx)
        test_chaleur_regen_blocked_by_reportee(results, ctx)
        # Phase 3 — LOW-priority boundary tests (added 2026-05-19)
        test_reporter_alerte_rejects_wrong_status(results, ctx)
        test_a_revoir_nb_jours_boundaries(results, ctx)
        test_tarissement_date_boundaries(results, ctx)

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

    bat = f"ABAT-{RUN_ID}"
    frappe.get_doc({"doctype": "Batiment", "nom_batiment": bat, "type_batiment": "ELEVAGE", "actif": 1}).insert(ignore_permissions=True)
    ctx["batiment"] = bat

    lot = f"ALOT-{RUN_ID}"
    frappe.get_doc({"doctype": "Lot", "nom": lot, "batiment": bat, "superficie_m2": 100, "capacite_optimale": 20, "capacite_maximale": 30, "actif": 1}).insert(ignore_permissions=True)
    ctx["lot"] = lot

    bull = f"ABULL-{RUN_ID}"
    frappe.get_doc({"doctype": "Taureau", "nom_taureau": bull, "code_taureau": f"AC{RUN_ID}", "race": "Holstein"}).insert(ignore_permissions=True)
    ctx["taureau"] = bull

    # ST5-14 (Phase C): legacy quantite_recue/quantite_restante removed in ST5-12.
    sem = frappe.get_doc({"doctype": "Semence", "taureau": bull, "type_semence": "CONVENTIONNELLE", "date_reception": today()})
    sem.insert(ignore_permissions=True)
    ctx["semence"] = sem.name

    mere = frappe.db.get_value("Mere externe", {}, "name")
    if not mere:
        doc = frappe.get_doc({"doctype": "Mere externe"})
        doc.insert(ignore_permissions=True)
        mere = doc.name
    ctx["mere_externe"] = mere

    ctx["animals"] = []
    frappe.db.commit()
    log("Base data ready")


def make_animal(ctx, suffix, categorie="VACHE", date_naissance="2020-01-01"):
    """Create a test animal and track it for cleanup"""
    animal_id = f"91{RUN_ID}{suffix:02d}"
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": animal_id,
        "categorie": categorie, "race": "Holstein",
        "date_naissance": date_naissance,
        # est_achat=1 requires date_entree (Animal.validate_mere_obligatoire)
        "date_entree": date_naissance,
        "est_achat": 1, "id_mere_externe": ctx["mere_externe"],
        "id_pere": ctx["taureau"], "id_lot": ctx["lot"],
        "statut": "ACTIF"
    })
    doc.insert(ignore_permissions=True)
    ctx["animals"].append(animal_id)
    frappe.db.commit()
    return animal_id


def clear_alerts(animal):
    """Delete all alerts for an animal"""
    for a in frappe.get_all("Alerte", {"animal": animal}, pluck="name"):
        frappe.delete_doc("Alerte", a, force=True)
    frappe.db.commit()


# ═══════════════════════════════════════════════════════════════════
# TEST 1: CHALEUR GENISSE
# ═══════════════════════════════════════════════════════════════════

def test_chaleur_genisse(results, ctx):
    print("\n── CHALEUR_GENISSE ──")

    # Ideal: GENISSE, ACTIF, VIDE, born 15 months ago
    birth = add_months(getdate(today()), -15)
    animal = make_animal(ctx, 1, categorie="GENISSE", date_naissance=str(birth))

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts

    clear_alerts(animal)
    generate_alerts()

    alerts = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "CHALEUR_GENISSE", "statut": "NOUVELLE"})
    assert_test(len(alerts) == 1, "CHALEUR_GENISSE generated for 15mo genisse", f"alerts: {len(alerts)}", results)

    # Running again should NOT create duplicate
    generate_alerts()
    alerts = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "CHALEUR_GENISSE", "statut": "NOUVELLE"})
    assert_test(len(alerts) == 1, "No duplicate on re-run", f"alerts: {len(alerts)}", results)

    # Test: genisse too young (10 months) — should NOT generate
    birth_young = add_months(getdate(today()), -10)
    young = make_animal(ctx, 2, categorie="GENISSE", date_naissance=str(birth_young))
    clear_alerts(young)
    generate_alerts()
    alerts_young = frappe.get_all("Alerte", {"animal": young, "type_alerte": "CHALEUR_GENISSE", "statut": "NOUVELLE"})
    assert_test(len(alerts_young) == 0, "No alert for 10mo genisse (too young)", f"alerts: {len(alerts_young)}", results)

    # Test: VACHE should NOT get CHALEUR_GENISSE
    vache = make_animal(ctx, 3, categorie="VACHE")
    clear_alerts(vache)
    generate_alerts()
    alerts_vache = frappe.get_all("Alerte", {"animal": vache, "type_alerte": "CHALEUR_GENISSE"})
    assert_test(len(alerts_vache) == 0, "No CHALEUR_GENISSE for VACHE", f"alerts: {len(alerts_vache)}", results)

    # Test buttons: Confirmer → CONFIRMEE
    from hmd_agro.hmd_agro.doctype.alerte.alerte import mark_alert
    alert_name = alerts[0].name
    mark_alert(alert_name, "confirmer")
    statut = frappe.db.get_value("Alerte", alert_name, "statut")
    assert_test(statut == "CONFIRMEE", "Confirmer → CONFIRMEE", f"statut: {statut}", results)

    # Test: Non confirmer → NON_CONFIRMEE
    new_alert = frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "CHALEUR_GENISSE",
        "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
    })
    new_alert.insert(ignore_permissions=True)
    frappe.db.commit()
    mark_alert(new_alert.name, "non_confirmer")
    statut = frappe.db.get_value("Alerte", new_alert.name, "statut")
    assert_test(statut == "NON_CONFIRMEE", "Non confirmer → NON_CONFIRMEE", f"statut: {statut}", results)

    # Test: Reporter (only works on CONFIRMEE)
    from hmd_agro.hmd_agro.doctype.alerte.alerte import reporter_alerte
    confirmed = frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "CHALEUR_GENISSE",
        "date_alerte": today(), "raison": "test", "statut": "CONFIRMEE"
    })
    confirmed.insert(ignore_permissions=True)
    frappe.db.commit()

    result = reporter_alerte(confirmed.name, "MALADE")
    confirmed.reload()
    assert_test(confirmed.statut == "REPORTEE", "Reporter → REPORTEE", f"statut: {confirmed.statut}", results)
    assert_test(result.get("new_alert") is not None, "Follow-up alert created (21 days)", f"result: {result}", results)

    if result.get("new_alert"):
        followup = frappe.get_doc("Alerte", result["new_alert"])
        expected_date = add_days(getdate(today()), 21)
        assert_test(str(followup.date_alerte) == str(expected_date),
            f"Follow-up date = today+21 ({expected_date})", f"date: {followup.date_alerte}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 2: CHALEUR POST VELAGE
# ═══════════════════════════════════════════════════════════════════

def test_chaleur_post_velage(results, ctx):
    print("\n── CHALEUR_POST_VELAGE ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts

    # Create a VACHE that had a velage 50 days ago
    animal = make_animal(ctx, 10, categorie="VACHE")

    # Create a fake velage record (50 days ago)
    velage_date = add_days(today(), -50)
    vel = frappe.get_doc({
        "doctype": "Velage", "animal": animal, "date_velage": velage_date,
        "type_velage": "FACILE", "nombre_veaux": "1", "sexe_veau1": "M", "vivant_veau1": 0
    })
    vel.flags.ignore_validate = True
    vel.insert(ignore_permissions=True)

    # Animal must be VIDE for this alert
    frappe.db.set_value("Animal", animal, {"etat_gestation": "VIDE", "categorie": "VACHE"}, update_modified=False)
    frappe.db.commit()

    clear_alerts(animal)
    generate_alerts()

    alerts = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "CHALEUR_POST_VELAGE", "statut": "NOUVELLE"})
    assert_test(len(alerts) == 1, "CHALEUR_POST_VELAGE generated (50d post-velage)", f"alerts: {len(alerts)}", results)

    # Test: velage only 30 days ago — too early
    animal2 = make_animal(ctx, 11, categorie="VACHE")
    vel2 = frappe.get_doc({
        "doctype": "Velage", "animal": animal2, "date_velage": add_days(today(), -30),
        "type_velage": "FACILE", "nombre_veaux": "1", "sexe_veau1": "M", "vivant_veau1": 0
    })
    vel2.flags.ignore_validate = True
    vel2.insert(ignore_permissions=True)
    frappe.db.set_value("Animal", animal2, {"etat_gestation": "VIDE", "categorie": "VACHE"}, update_modified=False)
    frappe.db.commit()

    clear_alerts(animal2)
    generate_alerts()
    alerts2 = frappe.get_all("Alerte", {"animal": animal2, "type_alerte": "CHALEUR_POST_VELAGE", "statut": "NOUVELLE"})
    assert_test(len(alerts2) == 0, "No alert for 30d post-velage (too early)", f"alerts: {len(alerts2)}", results)

    # Test: GESTANTE animal should NOT get post-velage alert
    frappe.db.set_value("Animal", animal, "etat_gestation", "GESTANTE", update_modified=False)
    frappe.db.commit()
    clear_alerts(animal)
    generate_alerts()
    alerts3 = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "CHALEUR_POST_VELAGE", "statut": "NOUVELLE"})
    assert_test(len(alerts3) == 0, "No alert for GESTANTE animal", f"alerts: {len(alerts3)}", results)

    # Restore
    frappe.db.set_value("Animal", animal, "etat_gestation", "VIDE", update_modified=False)
    frappe.db.commit()


# ═══════════════════════════════════════════════════════════════════
# TEST 3: VERIFICATION J21
# ═══════════════════════════════════════════════════════════════════

def test_verification_j21(results, ctx):
    print("\n── VERIFICATION_J21 ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts, mark_alert, a_revoir_alerte

    animal = make_animal(ctx, 20, categorie="VACHE")

    # Create lactation
    lac = frappe.get_doc({
        "doctype": "Lactation", "animal": animal,
        "date_debut": add_days(today(), -100), "statut": "EN_COURS"
    })
    lac.insert(ignore_permissions=True)

    # Create IA 20 days ago (>18 days = triggers J21)
    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -20),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)
    frappe.db.commit()

    clear_alerts(animal)
    generate_alerts()

    alerts = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "VERIFICATION_J21", "statut": "NOUVELLE"})
    assert_test(len(alerts) == 1, "J21 alert generated (IA 20 days old)", f"alerts: {len(alerts)}", results)

    # Test: IA only 10 days old — too early
    animal2 = make_animal(ctx, 21, categorie="VACHE")
    lac2 = frappe.get_doc({"doctype": "Lactation", "animal": animal2, "date_debut": add_days(today(), -100), "statut": "EN_COURS"})
    lac2.insert(ignore_permissions=True)
    ia2 = frappe.get_doc({
        "doctype": "Insemination", "animal": animal2,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -10),
        "type_semence": "CONVENTIONNELLE"
    })
    ia2.insert(ignore_permissions=True)
    frappe.db.commit()
    clear_alerts(animal2)
    generate_alerts()
    alerts2 = frappe.get_all("Alerte", {"animal": animal2, "type_alerte": "VERIFICATION_J21", "statut": "NOUVELLE"})
    assert_test(len(alerts2) == 0, "No J21 for 10-day IA (too early)", f"alerts: {len(alerts2)}", results)

    # Test button: Pleine → GESTANTE_CONFIRMEE + IA → REUSSIE
    alert_name = alerts[0].name
    mark_alert(alert_name, "gestante_confirmee")
    statut = frappe.db.get_value("Alerte", alert_name, "statut")
    assert_test(statut == "GESTANTE_CONFIRMEE", "Pleine → GESTANTE_CONFIRMEE", f"statut: {statut}", results)

    ia.reload()
    assert_test(ia.resultat == "REUSSIE", "IA → REUSSIE after Pleine", f"resultat: {ia.resultat}", results)

    etat = frappe.db.get_value("Animal", animal, "etat_gestation")
    assert_test(etat == "GESTANTE", "Animal → GESTANTE after Pleine", f"etat: {etat}", results)

    # Test button: Vide → RETOUR_CHALEUR + IA → ECHOUEE (need new IA)
    # Reset animal
    frappe.db.set_value("Animal", animal, {"etat_gestation": "VIDE", "id_ia_fecondante": None, "date_velage_prevue": None, "date_tarissement": None}, update_modified=False)
    ia3 = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -25),
        "type_semence": "CONVENTIONNELLE"
    })
    ia3.insert(ignore_permissions=True)
    frappe.db.commit()

    vide_alert = frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "VERIFICATION_J21",
        "insemination": ia3.name, "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
    })
    vide_alert.insert(ignore_permissions=True)
    frappe.db.commit()

    mark_alert(vide_alert.name, "retour_chaleur")
    vide_alert.reload()
    assert_test(vide_alert.statut == "RETOUR_CHALEUR", "Vide → RETOUR_CHALEUR", f"statut: {vide_alert.statut}", results)

    ia3.reload()
    assert_test(ia3.resultat == "ECHOUEE", "IA → ECHOUEE after Vide", f"resultat: {ia3.resultat}", results)

    # Test button: A revoir → GESTANTE_PROBABLE + follow-up alert
    frappe.db.set_value("Animal", animal, {"etat_gestation": "VIDE", "id_ia_fecondante": None}, update_modified=False)
    ia4 = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -22),
        "type_semence": "CONVENTIONNELLE"
    })
    ia4.insert(ignore_permissions=True)
    frappe.db.commit()

    revoir_alert = frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "VERIFICATION_J21",
        "insemination": ia4.name, "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
    })
    revoir_alert.insert(ignore_permissions=True)
    frappe.db.commit()

    result = a_revoir_alerte(revoir_alert.name, 29)
    revoir_alert.reload()
    assert_test(revoir_alert.statut == "GESTANTE_PROBABLE", "A revoir → GESTANTE_PROBABLE", f"statut: {revoir_alert.statut}", results)
    assert_test(result.get("new_alert") is not None, "Follow-up J50 alert created", f"result: {result}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 5: TARISSEMENT
# ═══════════════════════════════════════════════════════════════════

def test_tarissement(results, ctx):
    print("\n── TARISSEMENT ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts, tarir_animal

    animal = make_animal(ctx, 40, categorie="VACHE")

    # Create lactation
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    # Set animal as GESTANTE with tarissement date in 5 days
    frappe.db.set_value("Animal", animal, {
        "etat_gestation": "GESTANTE",
        "date_tarissement": add_days(today(), 5),
        "date_velage_prevue": add_days(today(), 65)
    }, update_modified=False)
    frappe.db.commit()

    clear_alerts(animal)
    generate_alerts()

    alerts = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "TARISSEMENT", "statut": "NOUVELLE"})
    assert_test(len(alerts) == 1, "TARISSEMENT alert generated (5 days before)", f"alerts: {len(alerts)}", results)

    # Test: tarissement date 10 days away — too far
    animal2 = make_animal(ctx, 41, categorie="VACHE")
    lac2 = frappe.get_doc({"doctype": "Lactation", "animal": animal2, "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
    lac2.insert(ignore_permissions=True)
    frappe.db.set_value("Animal", animal2, {
        "etat_gestation": "GESTANTE",
        "date_tarissement": add_days(today(), 10)
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal2)
    generate_alerts()
    alerts2 = frappe.get_all("Alerte", {"animal": animal2, "type_alerte": "TARISSEMENT", "statut": "NOUVELLE"})
    assert_test(len(alerts2) == 0, "No alert for 10d away (too far)", f"alerts: {len(alerts2)}", results)

    # Test: no lactation — should NOT generate even if date is close
    animal3 = make_animal(ctx, 42, categorie="VACHE")
    frappe.db.set_value("Animal", animal3, {
        "etat_gestation": "GESTANTE",
        "date_tarissement": add_days(today(), 3)
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal3)
    generate_alerts()
    alerts3 = frappe.get_all("Alerte", {"animal": animal3, "type_alerte": "TARISSEMENT", "statut": "NOUVELLE"})
    assert_test(len(alerts3) == 0, "No alert without EN_COURS lactation", f"alerts: {len(alerts3)}", results)

    # Test Tarir button: closes lactation as TARIE
    alert_name = alerts[0].name
    result = tarir_animal(alert_name)
    assert_test(result.get("status") == "ok", "Tarir action succeeded", f"result: {result}", results)

    lac.reload()
    assert_test(lac.statut == "TARIE", "Lactation → TARIE after tarir", f"statut: {lac.statut}", results)

    alert_statut = frappe.db.get_value("Alerte", alert_name, "statut")
    assert_test(alert_statut == "TRAITEE", "Alert → TRAITEE after tarir", f"statut: {alert_statut}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 6: VELAGE IMMINENT
# ═══════════════════════════════════════════════════════════════════

def test_velage_imminent(results, ctx):
    print("\n── VELAGE_IMMINENT ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts

    animal = make_animal(ctx, 50, categorie="VACHE")

    # Set GESTANTE with velage in 10 days
    frappe.db.set_value("Animal", animal, {
        "etat_gestation": "GESTANTE",
        "date_velage_prevue": add_days(today(), 10)
    }, update_modified=False)
    frappe.db.commit()

    clear_alerts(animal)
    generate_alerts()

    alerts = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "VELAGE_IMMINENT", "statut": "NOUVELLE"})
    assert_test(len(alerts) == 1, "VELAGE_IMMINENT generated (10 days before)", f"alerts: {len(alerts)}", results)

    # Test: velage in 20 days — too far
    animal2 = make_animal(ctx, 51, categorie="VACHE")
    frappe.db.set_value("Animal", animal2, {
        "etat_gestation": "GESTANTE",
        "date_velage_prevue": add_days(today(), 20)
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal2)
    generate_alerts()
    alerts2 = frappe.get_all("Alerte", {"animal": animal2, "type_alerte": "VELAGE_IMMINENT", "statut": "NOUVELLE"})
    assert_test(len(alerts2) == 0, "No alert for 20d away (too far)", f"alerts: {len(alerts2)}", results)

    # Test: VIDE animal — should NOT generate
    animal3 = make_animal(ctx, 52, categorie="VACHE")
    frappe.db.set_value("Animal", animal3, {
        "etat_gestation": "VIDE",
        "date_velage_prevue": add_days(today(), 5)
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal3)
    generate_alerts()
    alerts3 = frappe.get_all("Alerte", {"animal": animal3, "type_alerte": "VELAGE_IMMINENT", "statut": "NOUVELLE"})
    assert_test(len(alerts3) == 0, "No alert for VIDE animal", f"alerts: {len(alerts3)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 7: ALERT CLOSE ON IA CREATION
# ═══════════════════════════════════════════════════════════════════

def test_alert_close_on_ia_creation(results, ctx):
    print("\n── Alert Close: IA Creation ──")

    animal = make_animal(ctx, 60, categorie="VACHE")

    # Create lactation
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": add_days(today(), -100), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    # Create open chaleur alert
    alert = frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "CHALEUR_POST_VELAGE",
        "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
    })
    alert.insert(ignore_permissions=True)
    frappe.db.commit()

    # Create IA → should close the chaleur alert
    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": today(),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)
    frappe.db.commit()

    alert.reload()
    assert_test(alert.statut == "TRAITEE", "Chaleur alert → TRAITEE on IA creation", f"statut: {alert.statut}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 8: ALERT CLOSE ON VELAGE
# ═══════════════════════════════════════════════════════════════════

def test_alert_close_on_velage(results, ctx):
    print("\n── Alert Close: Velage ──")

    animal = make_animal(ctx, 70, categorie="VACHE")

    # Make GESTANTE
    frappe.db.set_value("Animal", animal, {
        "etat_gestation": "GESTANTE",
        "date_velage_prevue": today()
    }, update_modified=False)
    frappe.db.commit()

    # Create alerts
    for t in ["VELAGE_IMMINENT", "TARISSEMENT"]:
        frappe.get_doc({
            "doctype": "Alerte", "animal": animal, "type_alerte": t,
            "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
        }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Create velage
    vel = frappe.get_doc({
        "doctype": "Velage", "animal": animal, "date_velage": today(),
        "type_velage": "FACILE", "nombre_veaux": "1", "sexe_veau1": "M", "vivant_veau1": 0
    })
    vel.flags.ignore_validate = True
    vel.insert(ignore_permissions=True)
    frappe.db.commit()

    # All NOUVELLE alerts should be closed
    open_alerts = frappe.get_all("Alerte", {"animal": animal, "statut": "NOUVELLE"})
    assert_test(len(open_alerts) == 0, "All alerts closed after velage", f"open: {len(open_alerts)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 9: ALERT CLOSE ON IA ECHOUEE
# ═══════════════════════════════════════════════════════════════════

def test_alert_close_on_ia_echouee(results, ctx):
    print("\n── Alert Close: IA → ECHOUEE ──")

    animal = make_animal(ctx, 80, categorie="VACHE")

    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal, "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)

    ia = frappe.get_doc({
        "doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -30),
        "type_semence": "CONVENTIONNELLE"
    })
    ia.insert(ignore_permissions=True)

    # Mark REUSSIE first
    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    # Create TARISSEMENT and VELAGE_IMMINENT alerts
    for t in ["TARISSEMENT", "VELAGE_IMMINENT"]:
        frappe.get_doc({
            "doctype": "Alerte", "animal": animal, "type_alerte": t,
            "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
        }).insert(ignore_permissions=True)

    # Create verification alert
    frappe.get_doc({
        "doctype": "Alerte", "animal": animal, "type_alerte": "VERIFICATION_J21",
        "insemination": ia.name, "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Mark IA as ECHOUEE
    ia.resultat = "ECHOUEE"
    ia.save()
    frappe.db.commit()

    # Verification alert should be NON_CONFIRMEE
    verif = frappe.get_all("Alerte", {"animal": animal, "type_alerte": "VERIFICATION_J21", "insemination": ia.name})
    if verif:
        statut = frappe.db.get_value("Alerte", verif[0].name, "statut")
        assert_test(statut == "NON_CONFIRMEE", "Verification alert → NON_CONFIRMEE", f"statut: {statut}", results)

    # TARISSEMENT/VELAGE_IMMINENT should be closed
    gestation_alerts = frappe.get_all("Alerte", {
        "animal": animal,
        "type_alerte": ["in", ["TARISSEMENT", "VELAGE_IMMINENT"]],
        "statut": "NOUVELLE"
    })
    assert_test(len(gestation_alerts) == 0, "Gestation alerts closed on IA ECHOUEE", f"open: {len(gestation_alerts)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 10: ALERT CLOSE ON ANIMAL EXIT
# ═══════════════════════════════════════════════════════════════════

def test_alert_close_on_animal_exit(results, ctx):
    print("\n── Alert Close: Animal Exit ──")

    animal = make_animal(ctx, 90, categorie="VACHE")

    # Create various alerts
    for t in ["CHALEUR_POST_VELAGE", "TARISSEMENT", "VELAGE_IMMINENT"]:
        frappe.get_doc({
            "doctype": "Alerte", "animal": animal, "type_alerte": t,
            "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"
        }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Sell animal
    a = frappe.get_doc("Animal", animal)
    a.statut = "VENDU"
    a.date_sortie = today()
    a.flags.ignore_validate = True
    a.save()
    frappe.db.commit()

    open_alerts = frappe.get_all("Alerte", {"animal": animal, "statut": ["in", ["NOUVELLE", "CONFIRMEE"]]})
    assert_test(len(open_alerts) == 0, "All alerts closed on animal exit", f"open: {len(open_alerts)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 11: AVORTEMENT CASCADE — closes open gestation alerts
# ═══════════════════════════════════════════════════════════════════

def test_avortement_closes_alerts(results, ctx):
    """Avortement.after_insert: resets Animal to VIDE + closes NOUVELLE/CONFIRMEE/GESTANTE_PROBABLE alerts."""
    print("\n── Avortement closes open alerts ──")

    animal = make_animal(ctx, 91, categorie="VACHE")
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal,
        "date_debut": add_days(today(), -100), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)
    ia = frappe.get_doc({"doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -60),
        "type_semence": "CONVENTIONNELLE"})
    ia.insert(ignore_permissions=True)
    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    # Seed one alert per (type, status) combo Avortement closes
    seeded = {}
    for type_alerte, statut in [
        ("VERIFICATION_J21", "NOUVELLE"),
        ("TARISSEMENT", "NOUVELLE"),
        ("VELAGE_IMMINENT", "NOUVELLE"),
        ("CHALEUR_POST_VELAGE", "CONFIRMEE"),
        ("VERIFICATION_J50", "GESTANTE_PROBABLE"),
    ]:
        a = frappe.get_doc({"doctype": "Alerte", "animal": animal,
            "type_alerte": type_alerte, "insemination": ia.name,
            "date_alerte": today(), "raison": "test", "statut": statut})
        a.insert(ignore_permissions=True)
        seeded[type_alerte] = a.name
    frappe.db.commit()

    avo = frappe.get_doc({"doctype": "Avortement", "animal": animal,
        "date_avortement": today(), "insemination": ia.name,
        "type_avortement": "SPONTANE"})
    avo.insert(ignore_permissions=True)
    frappe.db.commit()

    for type_alerte, name in seeded.items():
        st = frappe.db.get_value("Alerte", name, "statut")
        assert_test(st == "NON_CONFIRMEE",
                    f"{type_alerte} → NON_CONFIRMEE",
                    f"got: {st}", results)

    a = frappe.db.get_value("Animal", animal,
        ["etat_gestation", "id_ia_fecondante"], as_dict=True)
    assert_test(a.etat_gestation == "VIDE" and a.id_ia_fecondante is None,
                "Animal reset to VIDE + id_ia_fecondante cleared",
                f"etat={a.etat_gestation}, id_ia={a.id_ia_fecondante}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 12: VERIFICATION_J50 LIFECYCLE
# ═══════════════════════════════════════════════════════════════════

def test_j50_lifecycle(results, ctx):
    """J50 creation via a_revoir + both transitions (GESTANTE_CONFIRMEE / RETOUR_CHALEUR)."""
    print("\n── VERIFICATION_J50 lifecycle ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import a_revoir_alerte, mark_alert

    # ─── Sub-test A: J21 + a_revoir → J50 with correct type and display_date
    animal_a = make_animal(ctx, 92, categorie="VACHE")
    lac_a = frappe.get_doc({"doctype": "Lactation", "animal": animal_a,
        "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
    lac_a.insert(ignore_permissions=True)
    ia_a = frappe.get_doc({"doctype": "Insemination", "animal": animal_a,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -25),
        "type_semence": "CONVENTIONNELLE"})
    ia_a.insert(ignore_permissions=True)
    frappe.db.commit()

    j21 = frappe.get_doc({"doctype": "Alerte", "animal": animal_a,
        "type_alerte": "VERIFICATION_J21", "insemination": ia_a.name,
        "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"})
    j21.insert(ignore_permissions=True)
    frappe.db.commit()

    result_a = a_revoir_alerte(j21.name, 30)
    j50_name_a = result_a.get("new_alert")
    j50_a = frappe.db.get_value("Alerte", j50_name_a,
        ["type_alerte", "date_alerte", "insemination", "statut"], as_dict=True)
    assert_test(j50_a.type_alerte == "VERIFICATION_J50",
                f"a_revoir creates VERIFICATION_J50 (not J21)",
                f"got type: {j50_a.type_alerte}", results)
    # display_date = today + max(nb_jours - alerte_lead_jours, 0); default lead=2
    expected_display = add_days(getdate(today()), 28)  # 30 - 2
    assert_test(str(j50_a.date_alerte) == str(expected_display),
                f"J50 display_date = today + 28 (30 - lead 2)",
                f"got: {j50_a.date_alerte}, expected: {expected_display}",
                results)
    assert_test(j50_a.insemination == ia_a.name,
                f"J50 inherits insemination link",
                f"got: {j50_a.insemination}", results)

    # ─── Sub-test B: J50 → GESTANTE_CONFIRMEE cascades to IA + Animal
    mark_alert(j50_name_a, "gestante_confirmee")
    j50_after = frappe.db.get_value("Alerte", j50_name_a, "statut")
    assert_test(j50_after == "GESTANTE_CONFIRMEE",
                "J50 → GESTANTE_CONFIRMEE",
                f"got: {j50_after}", results)
    ia_a.reload()
    assert_test(ia_a.resultat == "REUSSIE",
                "IA → REUSSIE after J50 GESTANTE_CONFIRMEE",
                f"got: {ia_a.resultat}", results)
    etat_a = frappe.db.get_value("Animal", animal_a, "etat_gestation")
    assert_test(etat_a == "GESTANTE",
                "Animal → GESTANTE after J50 Pleine",
                f"got: {etat_a}", results)

    # ─── Sub-test C: Different J50 → RETOUR_CHALEUR cascades to IA + Animal
    animal_c = make_animal(ctx, 93, categorie="VACHE")
    lac_c = frappe.get_doc({"doctype": "Lactation", "animal": animal_c,
        "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
    lac_c.insert(ignore_permissions=True)
    ia_c = frappe.get_doc({"doctype": "Insemination", "animal": animal_c,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -55),
        "type_semence": "CONVENTIONNELLE"})
    ia_c.insert(ignore_permissions=True)
    frappe.db.commit()

    j50_c = frappe.get_doc({"doctype": "Alerte", "animal": animal_c,
        "type_alerte": "VERIFICATION_J50", "insemination": ia_c.name,
        "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"})
    j50_c.insert(ignore_permissions=True)
    frappe.db.commit()

    mark_alert(j50_c.name, "retour_chaleur")
    j50_c.reload()
    assert_test(j50_c.statut == "RETOUR_CHALEUR",
                "J50 → RETOUR_CHALEUR",
                f"got: {j50_c.statut}", results)
    ia_c.reload()
    assert_test(ia_c.resultat == "ECHOUEE",
                "IA → ECHOUEE after J50 Vide",
                f"got: {ia_c.resultat}", results)
    etat_c = frappe.db.get_value("Animal", animal_c, "etat_gestation")
    assert_test(etat_c == "VIDE",
                "Animal → VIDE after J50 Vide",
                f"got: {etat_c}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 13: DELVO END-TO-END
# ═══════════════════════════════════════════════════════════════════

def test_delvo_end_to_end(results, ctx):
    """DELVO loop: generation, date window, lait_propre, encore_contamine, REPORTEE regen."""
    print("\n── DELVO end-to-end ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import (
        generate_alerts, delvo_lait_propre, delvo_encore_contamine,
    )

    # Generation IN window (default advance=1, so date_fin=today+1 hits)
    animal_a = make_animal(ctx, 94, categorie="VACHE")
    frappe.db.set_value("Animal", animal_a, {
        "attente_lait_active": 1,
        "date_fin_attente_lait": add_days(today(), 1),
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal_a)
    generate_alerts()
    alerts_a = frappe.get_all("Alerte", {"animal": animal_a,
        "type_alerte": "DELVO", "statut": "NOUVELLE"})
    assert_test(len(alerts_a) == 1,
                "DELVO generated when date_fin = today+1",
                f"alerts: {len(alerts_a)}", results)

    # Generation OUT of window (today+5 > advance=1)
    animal_b = make_animal(ctx, 95, categorie="VACHE")
    frappe.db.set_value("Animal", animal_b, {
        "attente_lait_active": 1,
        "date_fin_attente_lait": add_days(today(), 5),
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal_b)
    generate_alerts()
    alerts_b = frappe.get_all("Alerte", {"animal": animal_b,
        "type_alerte": "DELVO", "statut": "NOUVELLE"})
    assert_test(len(alerts_b) == 0,
                "No DELVO for date_fin = today+5 (out of window)",
                f"alerts: {len(alerts_b)}", results)

    # lait_propre clears flag + dates, marks alert TRAITEE
    delvo_lait_propre(alerts_a[0].name)
    a_after = frappe.db.get_value("Animal", animal_a,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)
    statut_c = frappe.db.get_value("Alerte", alerts_a[0].name, "statut")
    assert_test(
        int(a_after.attente_lait_active or 0) == 0
        and a_after.date_fin_attente_lait is None
        and statut_c == "TRAITEE",
        "lait_propre: flag cleared + date cleared + alert TRAITEE",
        f"flag={a_after.attente_lait_active}, "
        f"date={a_after.date_fin_attente_lait}, statut={statut_c}", results)

    # encore_contamine: critical that flag is RE-ENABLED (not just date extended)
    animal_d = make_animal(ctx, 96, categorie="VACHE")
    frappe.db.set_value("Animal", animal_d, {
        "attente_lait_active": 1,
        "date_fin_attente_lait": today(),
    }, update_modified=False)
    frappe.db.commit()
    clear_alerts(animal_d)
    generate_alerts()
    alerts_d = frappe.get_all("Alerte", {"animal": animal_d,
        "type_alerte": "DELVO", "statut": "NOUVELLE"})

    delvo_encore_contamine(alerts_d[0].name, 5)
    a_d = frappe.db.get_value("Animal", animal_d,
        ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)
    statut_d = frappe.db.get_value("Alerte", alerts_d[0].name, "statut")
    expected_new_date = add_days(getdate(today()), 5)
    assert_test(
        int(a_d.attente_lait_active or 0) == 1
        and str(a_d.date_fin_attente_lait) == str(expected_new_date)
        and statut_d == "REPORTEE",
        "encore_contamine: flag RE-ENABLED + date extended to today+5 + alert REPORTEE",
        f"flag={a_d.attente_lait_active}, date={a_d.date_fin_attente_lait}, "
        f"statut={statut_d}", results)

    # REPORTEE doesn't block regen — date filter does. Re-run same-day (still
    # out of window), then bring date back in window and expect fresh NOUVELLE.
    generate_alerts()
    alerts_e = frappe.get_all("Alerte", {"animal": animal_d,
        "type_alerte": "DELVO", "statut": "NOUVELLE"})
    assert_test(len(alerts_e) == 0,
                "REPORTEE alone doesn't regen (date out of window)",
                f"alerts: {len(alerts_e)}", results)

    frappe.db.set_value("Animal", animal_d, "date_fin_attente_lait",
                        add_days(today(), 1), update_modified=False)
    frappe.db.commit()
    generate_alerts()
    alerts_f = frappe.get_all("Alerte", {"animal": animal_d,
        "type_alerte": "DELVO", "statut": "NOUVELLE"})
    assert_test(len(alerts_f) == 1,
                "Fresh NOUVELLE created when date re-enters window after REPORTEE",
                f"alerts: {len(alerts_f)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 14: ANIMAL EXIT — MORT and REFORME parallel to VENDU
# ═══════════════════════════════════════════════════════════════════

def test_alert_close_on_animal_exit_other_statuses(results, ctx):
    """MORT and REFORME cascade identically to VENDU (test 10)."""
    print("\n── Alert Close: MORT and REFORME ──")

    for suffix, exit_statut in [(71, "MORT"), (72, "REFORME")]:
        animal = make_animal(ctx, suffix, categorie="VACHE")
        for t in ["CHALEUR_POST_VELAGE", "TARISSEMENT", "VELAGE_IMMINENT"]:
            frappe.get_doc({"doctype": "Alerte", "animal": animal,
                "type_alerte": t, "date_alerte": today(),
                "raison": "test", "statut": "NOUVELLE"}).insert(
                    ignore_permissions=True)
        frappe.db.commit()

        a = frappe.get_doc("Animal", animal)
        a.statut = exit_statut
        a.date_sortie = today()
        a.flags.ignore_validate = True
        a.save()
        frappe.db.commit()

        open_alerts = frappe.get_all("Alerte", {"animal": animal,
            "statut": ["in", ["NOUVELLE", "CONFIRMEE"]]})
        assert_test(len(open_alerts) == 0,
                    f"All alerts closed on animal exit (statut={exit_statut})",
                    f"open: {len(open_alerts)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 15: IA → REUSSIE — explicit side effects on Animal fields
# ═══════════════════════════════════════════════════════════════════

def test_ia_reussie_animal_side_effects(results, ctx):
    """IA → REUSSIE updates Animal: GESTANTE + id_ia_fecondante + computed velage/tarissement dates."""
    print("\n── IA → REUSSIE side effects ──")

    from hmd_agro.hmd_agro.utils.config import get_config
    periode_velage = get_config("periode_velage_jours", default=280)
    tarissement_window = get_config("tarissement_window_jours", default=60)

    animal = make_animal(ctx, 73, categorie="VACHE")
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal,
        "date_debut": add_days(today(), -100), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)
    date_ia = add_days(today(), -30)
    ia = frappe.get_doc({"doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": date_ia,
        "type_semence": "CONVENTIONNELLE"})
    ia.insert(ignore_permissions=True)
    frappe.db.commit()

    ia.resultat = "REUSSIE"
    ia.save()
    frappe.db.commit()

    a = frappe.db.get_value("Animal", animal, [
        "etat_gestation", "id_ia_fecondante",
        "date_velage_prevue", "date_tarissement",
    ], as_dict=True)
    assert_test(a.etat_gestation == "GESTANTE",
                "Animal.etat_gestation = GESTANTE",
                f"got: {a.etat_gestation}", results)
    assert_test(a.id_ia_fecondante == ia.name,
                f"Animal.id_ia_fecondante = {ia.name}",
                f"got: {a.id_ia_fecondante}", results)
    expected_velage = add_days(getdate(date_ia), periode_velage)
    assert_test(str(a.date_velage_prevue) == str(expected_velage),
                f"date_velage_prevue = date_ia + {periode_velage}j "
                f"= {expected_velage}",
                f"got: {a.date_velage_prevue}", results)
    expected_tarissement = add_days(expected_velage, -tarissement_window)
    assert_test(str(a.date_tarissement) == str(expected_tarissement),
                f"date_tarissement = date_velage_prevue - {tarissement_window}j "
                f"= {expected_tarissement}",
                f"got: {a.date_tarissement}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 16: CHALEUR REGEN — REPORTEE blocks, TRAITEE doesn't
# ═══════════════════════════════════════════════════════════════════

def test_chaleur_regen_blocked_by_reportee(results, ctx):
    """REPORTEE blocks CHALEUR_GENISSE regen (alerte.py:42); TRAITEE doesn't."""
    print("\n── CHALEUR regen: REPORTEE blocks, TRAITEE doesn't ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts

    # 15mo génisse — meets generator criteria
    birth = add_months(getdate(today()), -15)
    animal = make_animal(ctx, 74, categorie="GENISSE",
                          date_naissance=str(birth))

    # Pre-seed a REPORTEE alert. Use yesterday so the generator can't say
    # "duplicate today" — the assertion is "REPORTEE blocks regardless of
    # whether dates overlap".
    reportee = frappe.get_doc({"doctype": "Alerte", "animal": animal,
        "type_alerte": "CHALEUR_GENISSE",
        "date_alerte": add_days(today(), -1),
        "raison": "test seed", "statut": "REPORTEE"})
    reportee.insert(ignore_permissions=True)
    frappe.db.commit()

    generate_alerts()
    new_alerts = frappe.get_all("Alerte", {"animal": animal,
        "type_alerte": "CHALEUR_GENISSE", "statut": "NOUVELLE"})
    assert_test(len(new_alerts) == 0,
                "REPORTEE alert blocks new CHALEUR_GENISSE generation",
                f"unexpected NOUVELLE created: {len(new_alerts)}", results)

    # Flip the REPORTEE to TRAITEE — generator should now create a fresh one
    frappe.db.set_value("Alerte", reportee.name, "statut", "TRAITEE",
                         update_modified=False)
    frappe.db.commit()
    generate_alerts()
    new_alerts2 = frappe.get_all("Alerte", {"animal": animal,
        "type_alerte": "CHALEUR_GENISSE", "statut": "NOUVELLE"})
    assert_test(len(new_alerts2) == 1,
                "TRAITEE alert does NOT block new CHALEUR_GENISSE generation",
                f"expected 1 NOUVELLE, got {len(new_alerts2)}", results)


# ═══════════════════════════════════════════════════════════════════
# TEST 17: REPORTER_ALERTE — rejects non-CONFIRMEE statuses
# ═══════════════════════════════════════════════════════════════════

def test_reporter_alerte_rejects_wrong_status(results, ctx):
    """reporter_alerte throws on any non-CONFIRMEE status (alerte.py:424)."""
    print("\n── Reporter rejects non-CONFIRMEE statuses ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import reporter_alerte

    animal = make_animal(ctx, 75, categorie="GENISSE",
                          date_naissance=str(add_months(getdate(today()), -15)))

    for bad_statut in ("NOUVELLE", "NON_CONFIRMEE", "TRAITEE", "REPORTEE"):
        a = frappe.get_doc({"doctype": "Alerte", "animal": animal,
            "type_alerte": "CHALEUR_GENISSE", "date_alerte": today(),
            "raison": "test", "statut": bad_statut})
        a.insert(ignore_permissions=True)
        frappe.db.commit()

        threw = False
        try:
            reporter_alerte(a.name, "MALADE")
        except Exception:
            threw = True
        assert_test(threw,
                    f"Reporter on statut={bad_statut} throws",
                    f"silently succeeded", results)
        frappe.delete_doc("Alerte", a.name, force=True,
                          ignore_permissions=True)
        frappe.db.commit()


# ═══════════════════════════════════════════════════════════════════
# TEST 18: A_REVOIR_ALERTE — nb_jours boundaries
# ═══════════════════════════════════════════════════════════════════

def test_a_revoir_nb_jours_boundaries(results, ctx):
    """a_revoir_alerte validates nb_jours ∈ [1, 120] (alerte.py:473)."""
    print("\n── a_revoir nb_jours boundaries ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import a_revoir_alerte

    animal = make_animal(ctx, 76, categorie="VACHE")
    lac = frappe.get_doc({"doctype": "Lactation", "animal": animal,
        "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
    lac.insert(ignore_permissions=True)
    ia = frappe.get_doc({"doctype": "Insemination", "animal": animal,
        "taureau": ctx["taureau"], "date_ia": add_days(today(), -25),
        "type_semence": "CONVENTIONNELLE"})
    ia.insert(ignore_permissions=True)
    frappe.db.commit()

    def _seed_j21():
        a = frappe.get_doc({"doctype": "Alerte", "animal": animal,
            "type_alerte": "VERIFICATION_J21", "insemination": ia.name,
            "date_alerte": today(), "raison": "test", "statut": "NOUVELLE"})
        a.insert(ignore_permissions=True)
        frappe.db.commit()
        return a.name

    # Invalid: nb_jours=0
    a0 = _seed_j21()
    threw_0 = False
    try:
        a_revoir_alerte(a0, 0)
    except Exception:
        threw_0 = True
    assert_test(threw_0, "nb_jours=0 throws",
                "nb_jours=0 silently succeeded", results)

    # Valid: nb_jours=1
    a1 = _seed_j21()
    try:
        result_1 = a_revoir_alerte(a1, 1)
        assert_test(result_1.get("new_alert") is not None,
                    "nb_jours=1 accepted, creates follow-up",
                    f"got: {result_1}", results)
        # Cleanup the new alert
        if result_1.get("new_alert"):
            frappe.delete_doc("Alerte", result_1["new_alert"], force=True,
                              ignore_permissions=True)
    except Exception as e:
        assert_test(False, "nb_jours=1 accepted",
                    f"unexpectedly threw: {e}", results)

    # Valid: nb_jours=120
    a120 = _seed_j21()
    try:
        result_120 = a_revoir_alerte(a120, 120)
        assert_test(result_120.get("new_alert") is not None,
                    "nb_jours=120 accepted, creates follow-up",
                    f"got: {result_120}", results)
        if result_120.get("new_alert"):
            frappe.delete_doc("Alerte", result_120["new_alert"], force=True,
                              ignore_permissions=True)
    except Exception as e:
        assert_test(False, "nb_jours=120 accepted",
                    f"unexpectedly threw: {e}", results)

    # Invalid: nb_jours=121
    a121 = _seed_j21()
    threw_121 = False
    try:
        a_revoir_alerte(a121, 121)
    except Exception:
        threw_121 = True
    assert_test(threw_121, "nb_jours=121 throws",
                "nb_jours=121 silently succeeded", results)

    frappe.db.commit()


# ═══════════════════════════════════════════════════════════════════
# TEST 19: TARISSEMENT — date boundaries
# ═══════════════════════════════════════════════════════════════════

def test_tarissement_date_boundaries(results, ctx):
    """TARISSEMENT filters date_tarissement <= today + advance_jours (default 7)."""
    print("\n── TARISSEMENT date boundaries ──")

    from hmd_agro.hmd_agro.doctype.alerte.alerte import generate_alerts

    def _setup_animal(suffix, days_to_tarissement):
        animal = make_animal(ctx, suffix, categorie="VACHE")
        lac = frappe.get_doc({"doctype": "Lactation", "animal": animal,
            "date_debut": add_days(today(), -200), "statut": "EN_COURS"})
        lac.insert(ignore_permissions=True)
        frappe.db.set_value("Animal", animal, {
            "etat_gestation": "GESTANTE",
            "date_tarissement": add_days(today(), days_to_tarissement),
            "date_velage_prevue": add_days(today(), days_to_tarissement + 60),
        }, update_modified=False)
        frappe.db.commit()
        clear_alerts(animal)
        return animal

    cases = [
        (77, 0, True,  "today (days_until=0)"),
        (78, 7, True,  "today+7 (boundary inclusive)"),
        (79, 8, False, "today+8 (just outside default window)"),
    ]
    for suffix, days, should_gen, label in cases:
        animal = _setup_animal(suffix, days)
        generate_alerts()
        alerts = frappe.get_all("Alerte", {"animal": animal,
            "type_alerte": "TARISSEMENT", "statut": "NOUVELLE"})
        got = len(alerts)
        expected = 1 if should_gen else 0
        assert_test(got == expected,
                    f"date_tarissement = {label}: "
                    f"{'generates' if should_gen else 'no'} alert",
                    f"expected {expected}, got {got}", results)


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

    # Delete animals and their calves
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

    # Base data
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
