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
