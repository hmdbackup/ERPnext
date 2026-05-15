import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months, add_days, date_diff

from hmd_agro.hmd_agro.utils.config import get_config


class Alerte(Document):
    pass


@frappe.whitelist()
def generate_alerts():
    """Run daily to create heat, J+21 verification, tarissement,
    velage imminent, and DELVO alerts. J+50 alerts are NOT generated
    here — they are created only via the 'À revoir' action."""
    _generate_genisse_alerts()
    _generate_post_velage_alerts()
    _generate_j21_alerts()
    _generate_tarissement_alerts()
    _generate_velage_alerts()
    _generate_delvo_alerts()
    frappe.db.commit()


def _generate_genisse_alerts():
    """CHALEUR_GENISSE: Genisse reaches configured age (default 14 months)"""
    n_months = get_config("chaleur_genisse_age_mois", default=14)
    cutoff_date = add_months(getdate(today()), -n_months)

    genisses = frappe.db.get_all("Animal", filters={
        "categorie": "GENISSE",
        "statut": "ACTIF",
        "etat_gestation": "VIDE",
        "date_naissance": ["<=", cutoff_date]
    }, fields=["name", "nom_metier", "date_naissance"])

    for g in genisses:
        existing = frappe.db.exists("Alerte", {
            "animal": g.name,
            "type_alerte": "CHALEUR_GENISSE",
            "statut": ["in", ["NOUVELLE", "CONFIRMEE", "REPORTEE"]]
        })
        if existing:
            continue

        pending_ia = frappe.db.exists("Insemination", {
            "animal": g.name,
            "resultat": "EN_ATTENTE"
        })
        if pending_ia:
            continue

        age_months = date_diff(getdate(today()), g.date_naissance) // 30

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": g.name,
            "type_alerte": "CHALEUR_GENISSE",
            "date_alerte": today(),
            "raison": f"GENISSE - {age_months} mois d'âge",
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


def _generate_post_velage_alerts():
    """CHALEUR_POST_VELAGE: Vache N days after last velage (default 45)"""
    n_days = get_config("chaleur_post_velage_jours", default=45)
    cutoff_date = add_days(getdate(today()), -n_days)

    velages = frappe.db.sql("""
        SELECT v.animal, v.date_velage, a.nom_metier
        FROM `tabVelage` v
        JOIN `tabAnimal` a ON a.name = v.animal
        WHERE v.date_velage <= %s
        AND a.statut = 'ACTIF'
        AND a.etat_gestation = 'VIDE'
        AND a.categorie = 'VACHE'
        AND v.date_velage = (
            SELECT MAX(v2.date_velage)
            FROM `tabVelage` v2
            WHERE v2.animal = v.animal
        )
    """, (cutoff_date,), as_dict=True)

    for v in velages:
        existing = frappe.db.exists("Alerte", {
            "animal": v.animal,
            "type_alerte": "CHALEUR_POST_VELAGE",
            "statut": ["in", ["NOUVELLE", "CONFIRMEE", "REPORTEE"]]
        })
        if existing:
            continue

        pending_ia = frappe.db.exists("Insemination", {
            "animal": v.animal,
            "resultat": "EN_ATTENTE"
        })
        if pending_ia:
            continue

        days_post = date_diff(getdate(today()), v.date_velage)

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": v.animal,
            "type_alerte": "CHALEUR_POST_VELAGE",
            "date_alerte": today(),
            "raison": f"VACHE - {days_post}j post-vêlage",
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


def _generate_j21_alerts():
    """VERIFICATION_J21: IA pending for N+ days (default 18)"""
    n_days = get_config("verification_j21_jours", default=18)
    cutoff_date = add_days(getdate(today()), -n_days)

    pending_ias = frappe.db.get_all("Insemination", filters={
        "resultat": "EN_ATTENTE",
        "date_ia": ["<=", cutoff_date]
    }, fields=["name", "animal", "date_ia"])

    for ia in pending_ias:
        existing = frappe.db.exists("Alerte", {
            "insemination": ia.name,
            "type_alerte": "VERIFICATION_J21",
            "statut": "NOUVELLE"
        })
        if existing:
            continue

        # Skip if J+21 already resolved for this IA (GESTANTE_PROBABLE or RETOUR_CHALEUR)
        resolved = frappe.db.exists("Alerte", {
            "insemination": ia.name,
            "type_alerte": "VERIFICATION_J21",
            "statut": ["in", ["GESTANTE_PROBABLE", "GESTANTE_CONFIRMEE","RETOUR_CHALEUR"]]
        })
        if resolved:
            continue

        animal = frappe.db.get_value("Animal", ia.animal,
            ["name", "nom_metier"], as_dict=True)
        if not animal:
            continue

        days_since = date_diff(getdate(today()), ia.date_ia)

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": ia.animal,
            "type_alerte": "VERIFICATION_J21",
            "insemination": ia.name,
            "date_alerte": today(),
            "raison": f"IA du {ia.date_ia} - J+{days_since}",
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


def _generate_tarissement_alerts():
    """TARISSEMENT: Gestating cow with EN_COURS lactation approaching dry-off date (default 7 days before)"""
    n_days = get_config("tarissement_advance_jours", default=7)
    cutoff_date = add_days(getdate(today()), n_days)

    animals = frappe.db.get_all("Animal", filters=[
        ["statut", "=", "ACTIF"],
        ["etat_gestation", "=", "GESTANTE"],
        ["date_tarissement", "is", "set"],
        ["date_tarissement", "<=", cutoff_date]
    ], fields=["name", "nom_metier", "date_tarissement"])

    for a in animals:
        # Must have an active lactation to need tarissement
        has_lactation = frappe.db.exists("Lactation", {
            "animal": a.name,
            "statut": "EN_COURS"
        })
        if not has_lactation:
            continue

        existing = frappe.db.exists("Alerte", {
            "animal": a.name,
            "type_alerte": "TARISSEMENT",
            "statut": ["in", ["NOUVELLE", "TRAITEE"]]
        })
        if existing:
            continue

        days_until = date_diff(a.date_tarissement, getdate(today()))
        if days_until > 0:
            raison = f"Tarissement prevu dans {days_until} jour(s) ({a.date_tarissement})"
        elif days_until == 0:
            raison = f"Tarissement prevu aujourd'hui ({a.date_tarissement})"
        else:
            raison = f"Tarissement en retard de {abs(days_until)} jour(s) ({a.date_tarissement})"

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": a.name,
            "type_alerte": "TARISSEMENT",
            "date_alerte": today(),
            "raison": raison,
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


def _generate_velage_alerts():
    """VELAGE_IMMINENT: Gestating animal approaching expected calving date (default 15 days before)"""
    n_days = get_config("velage_advance_jours", default=15)
    cutoff_date = add_days(getdate(today()), n_days)

    animals = frappe.db.get_all("Animal", filters=[
        ["statut", "=", "ACTIF"],
        ["etat_gestation", "=", "GESTANTE"],
        ["date_velage_prevue", "is", "set"],
        ["date_velage_prevue", "<=", cutoff_date]
    ], fields=["name", "nom_metier", "date_velage_prevue"])

    for a in animals:
        existing = frappe.db.exists("Alerte", {
            "animal": a.name,
            "type_alerte": "VELAGE_IMMINENT",
            "statut": ["in", ["NOUVELLE", "TRAITEE"]]
        })
        if existing:
            continue

        days_until = date_diff(a.date_velage_prevue, getdate(today()))
        if days_until > 0:
            raison = f"Velage prevu dans {days_until} jour(s) ({a.date_velage_prevue})"
        elif days_until == 0:
            raison = f"Velage prevu aujourd'hui ({a.date_velage_prevue})"
        else:
            raison = f"Velage en retard de {abs(days_until)} jour(s) ({a.date_velage_prevue})"

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": a.name,
            "type_alerte": "VELAGE_IMMINENT",
            "date_alerte": today(),
            "raison": raison,
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


def _generate_delvo_alerts():
    """DELVO: Alert N day(s) before milk withdrawal ends — remind farmer to test milk (default 1)"""
    n_days = get_config("delvo_advance_jours", default=1)
    tomorrow = add_days(getdate(today()), n_days)

    animals = frappe.db.get_all("Animal", filters=[
        ["statut", "=", "ACTIF"],
        ["attente_lait_active", "=", 1],
        ["date_fin_attente_lait", "is", "set"],
        ["date_fin_attente_lait", "<=", tomorrow]
    ], fields=["name", "nom_metier", "date_fin_attente_lait"])

    for a in animals:
        # Block only on a NOUVELLE alert. REPORTEE (deferred via "encore
        # contaminée") and TRAITEE (handled via "lait propre" — flag also
        # cleared) must NOT block: the deferred case needs a fresh reminder
        # at the new date; lait propre case can't reach here (animal flag
        # cleared, removed from the filter above).
        existing = frappe.db.exists("Alerte", {
            "animal": a.name,
            "type_alerte": "DELVO",
            "statut": "NOUVELLE"
        })
        if existing:
            continue

        days_until = date_diff(a.date_fin_attente_lait, getdate(today()))
        if days_until == 1:
            raison = f"Test Delvo demain ({a.date_fin_attente_lait}) — verifier traces antibiotiques"
        elif days_until == 0:
            raison = f"Test Delvo aujourd'hui ({a.date_fin_attente_lait}) — verifier traces antibiotiques"
        else:
            raison = f"Test Delvo en retard de {abs(days_until)} jour(s) ({a.date_fin_attente_lait})"

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": a.name,
            "type_alerte": "DELVO",
            "date_alerte": today(),
            "raison": raison,
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


@frappe.whitelist()
def delvo_lait_propre(alert_name):
    """Clear milk withdrawal — milk is clean"""
    doc = frappe.get_doc("Alerte", alert_name)
    if doc.type_alerte != "DELVO":
        frappe.throw("Cette action est reservee aux alertes Delvo")

    # Clear the animal's withdrawal flag
    frappe.db.sql("UPDATE `tabAnimal` SET attente_lait_active=0, date_fin_attente_lait=NULL WHERE name=%s", doc.animal)

    # Mark alert as treated
    doc.statut = "TRAITEE"
    doc.date_traitement = today()
    doc.save(ignore_permissions=True)

    animal_name = frappe.db.get_value("Animal", doc.animal, "nom_metier") or doc.animal
    return {"status": "ok", "animal": animal_name}


@frappe.whitelist()
def delvo_encore_contamine(alert_name, nb_jours):
    """Extend milk withdrawal period — milk still contaminated"""
    nb_jours = int(nb_jours)
    if nb_jours < 1 or nb_jours > 30:
        frappe.throw("Le nombre de jours doit etre entre 1 et 30")

    doc = frappe.get_doc("Alerte", alert_name)
    if doc.type_alerte != "DELVO":
        frappe.throw("Cette action est reservee aux alertes Delvo")

    # Extend the animal's withdrawal date AND re-enable the active flag.
    # If refresh_attente_lait already cleared the flag (date_fin was past),
    # the flag would stay 0 here without explicit re-enable, and the
    # generator's filter (attente_lait_active=1) would skip this animal —
    # no follow-up alert ever fires.
    new_date = add_days(getdate(today()), nb_jours)
    frappe.db.set_value("Animal", doc.animal, {
        "attente_lait_active": 1,
        "date_fin_attente_lait": new_date,
    })

    # Mark alert as REPORTEE — disappears from the active dashboard but
    # doesn't block the next generate_alerts run. A fresh NOUVELLE alert
    # will be created once date_fin_attente_lait is within `delvo_advance_jours`
    # of today.
    doc.statut = "REPORTEE"
    doc.date_traitement = today()
    doc.save(ignore_permissions=True)

    animal_name = frappe.db.get_value("Animal", doc.animal, "nom_metier") or doc.animal
    return {"status": "ok", "animal": animal_name, "new_date": str(new_date)}


@frappe.whitelist()
def tarir_animal(alert_name):
    """Close EN_COURS lactation as TARIE and mark alert as TRAITEE"""
    doc = frappe.get_doc("Alerte", alert_name)
    if doc.type_alerte != "TARISSEMENT":
        frappe.throw("Cette action est reservee aux alertes de tarissement")

    # Find EN_COURS lactation
    lactation_name = frappe.db.get_value("Lactation", {
        "animal": doc.animal,
        "statut": "EN_COURS"
    })
    if not lactation_name:
        frappe.throw("Aucune lactation EN_COURS trouvee pour cet animal")

    # Close lactation as TARIE
    lactation = frappe.get_doc("Lactation", lactation_name)
    lactation.statut = "TARIE"
    lactation.date_tarissement = today()
    lactation.save(ignore_permissions=True)

    # Mark alert as treated
    doc.statut = "TRAITEE"
    doc.date_traitement = today()
    doc.save(ignore_permissions=True)

    animal_name = frappe.db.get_value("Animal", doc.animal, "nom_metier") or doc.animal
    return {"status": "ok", "animal": animal_name, "lactation": lactation_name}


@frappe.whitelist()
def mark_alert(alert_name, action):
    """Mark alert based on farmer/vet decision"""
    doc = frappe.get_doc("Alerte", alert_name)

    if action == "confirmer":
        doc.statut = "CONFIRMEE"
    elif action == "non_confirmer":
        doc.statut = "NON_CONFIRMEE"
    elif action == "retour_chaleur":
        doc.statut = "RETOUR_CHALEUR"
    elif action == "gestante_confirmee":
        doc.statut = "GESTANTE_CONFIRMEE"
    elif action == "traiter":
        doc.statut = "TRAITEE"

    doc.date_traitement = today()
    doc.save(ignore_permissions=True)

    # Handle IA changes AFTER alert is saved
    # This prevents conflict: update_animal_on_resultat won't find
    # this alert as NOUVELLE anymore when closing orphaned alerts
    if action == "retour_chaleur" and doc.insemination:
        ia = frappe.get_doc("Insemination", doc.insemination)
        ia.resultat = "ECHOUEE"
        ia.save()

    elif action == "gestante_confirmee" and doc.insemination:
        ia = frappe.get_doc("Insemination", doc.insemination)
        ia.resultat = "REUSSIE"
        ia.save()

    return doc.statut


@frappe.whitelist()
def reporter_alerte(alert_name, raison_report, observations=None):
    """Reporter (postpone) a confirmed heat alert.
    Creates a new chaleur alert in 21 days for the same animal."""
    doc = frappe.get_doc("Alerte", alert_name)

    if doc.statut != "CONFIRMEE":
        frappe.throw("Seule une alerte CONFIRMEE peut être reportée")

    # Mark current alert as REPORTEE
    doc.statut = "REPORTEE"
    doc.raison_report = raison_report
    doc.observations = observations or ""
    doc.date_traitement = today()
    doc.save(ignore_permissions=True)

    # Determine original chaleur type for the follow-up
    # CONFIRMEE alerts were originally CHALEUR_GENISSE or CHALEUR_POST_VELAGE
    original_type = doc.type_alerte
    if original_type not in ("CHALEUR_GENISSE", "CHALEUR_POST_VELAGE"):
        # Guess from animal categorie
        categorie = frappe.db.get_value("Animal", doc.animal, "categorie")
        original_type = "CHALEUR_GENISSE" if categorie == "GENISSE" else "CHALEUR_POST_VELAGE"

    # Create follow-up chaleur alert in 21 days
    raison_labels = {
        "MALADE": "Animal malade",
        "BOITERIE": "Boiterie",
        "CONDITION_CORPORELLE_INSUFFISANTE": "Condition corporelle insuffisante",
        "AUTRE": "Autre raison"
    }
    raison_text = raison_labels.get(raison_report, raison_report)

    cycle_days = get_config("chaleur_cycle_jours", default=21)
    new_alert = frappe.get_doc({
        "doctype": "Alerte",
        "animal": doc.animal,
        "type_alerte": original_type,
        "date_alerte": add_days(getdate(today()), cycle_days),
        "raison": f"Suivi report - {raison_text}",
        "statut": "NOUVELLE"
    })
    new_alert.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "ok", "new_alert": new_alert.name}


@frappe.whitelist()
def a_revoir_alerte(alert_name, nb_jours, observations=None):
    """Handle 'À revoir' on a verification alert with configurable days.
    Works for both VERIFICATION_J21 and VERIFICATION_J50.
    Marks current alert as GESTANTE_PROBABLE and creates a new
    verification alert in nb_jours days (shown 2 days early)."""
    nb_jours = int(nb_jours)
    if nb_jours < 1 or nb_jours > 120:
        frappe.throw("Le nombre de jours doit être entre 1 et 120")

    doc = frappe.get_doc("Alerte", alert_name)
    if doc.type_alerte not in ("VERIFICATION_J21", "VERIFICATION_J50"):
        frappe.throw("Cette action est réservée aux alertes de vérification")

    # Mark current alert as GESTANTE_PROBABLE (handled, follow-up created)
    doc.statut = "GESTANTE_PROBABLE"
    doc.observations = observations or ""
    doc.date_traitement = today()
    doc.save(ignore_permissions=True)

    # Create new verification alert scheduled in nb_jours days
    # Show `alerte_lead_jours` days early so the farmer can prepare (default 2)
    lead_days = get_config("alerte_lead_jours", default=2)
    target_date = add_days(getdate(today()), nb_jours)
    display_date = add_days(getdate(today()), max(nb_jours - lead_days, 0))

    # Calculate days since IA for the raison label
    ia_date_str = ""
    if doc.insemination:
        ia_date = frappe.db.get_value("Insemination", doc.insemination, "date_ia")
        if ia_date:
            days_since_ia = date_diff(target_date, ia_date)
            ia_date_str = f"IA du {ia_date} - J+{days_since_ia}"

    new_alert = frappe.get_doc({
        "doctype": "Alerte",
        "animal": doc.animal,
        "type_alerte": "VERIFICATION_J50",
        "insemination": doc.insemination,
        "date_alerte": display_date,
        "raison": f"{ia_date_str} - Contrôle programmé (+{nb_jours}j)",
        "statut": "NOUVELLE"
    })
    new_alert.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "ok", "new_alert": new_alert.name, "date_controle": str(target_date)}


@frappe.whitelist()
def get_alertes_count():
    """Return count of pending alerts for the dashboard card"""
    count = frappe.db.count("Alerte", {"statut": "NOUVELLE"})
    return {
        "value": count,
        "fieldtype": "Int",
        "route": "/app/centre-alertes"
    }
