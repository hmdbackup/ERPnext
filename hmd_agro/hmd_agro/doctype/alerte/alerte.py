import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months, add_days, date_diff


class Alerte(Document):
    pass


@frappe.whitelist()
def generate_alerts():
    """Run daily to create heat alerts, J+21 and J+50 verification alerts"""
    _generate_genisse_alerts()
    _generate_post_velage_alerts()
    _generate_j21_alerts()
    _generate_j50_alerts()
    frappe.db.commit()


def _generate_genisse_alerts():
    """CHALEUR_GENISSE: Genisse reaches 14 months of age"""
    cutoff_date = add_months(getdate(today()), -14)

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
            "statut": ["in", ["NOUVELLE", "CONFIRMEE"]]
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
    """CHALEUR_POST_VELAGE: Vache 45 days after last velage"""
    cutoff_date = add_days(getdate(today()), -45)

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
            "statut": ["in", ["NOUVELLE", "CONFIRMEE"]]
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
    """VERIFICATION_J21: IA pending for 18+ days"""
    cutoff_date = add_days(getdate(today()), -18)

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


def _generate_j50_alerts():
    """VERIFICATION_J50: IA marked GESTANTE_PROBABLE at J+21, now 50+ days old"""
    cutoff_date = add_days(getdate(today()), -50)

    # Find IAs that have a GESTANTE_PROBABLE J+21 alert and are 50+ days old
    j21_probable = frappe.db.get_all("Alerte", filters={
        "type_alerte": "VERIFICATION_J21",
        "statut": "GESTANTE_PROBABLE"
    }, fields=["insemination", "animal"])

    for alert in j21_probable:
        if not alert.insemination:
            continue

        # Check IA is 50+ days old and still EN_ATTENTE
        ia = frappe.db.get_value("Insemination", alert.insemination,
            ["name", "date_ia", "resultat"], as_dict=True)
        if not ia or ia.resultat != "EN_ATTENTE":
            continue
        if getdate(ia.date_ia) > cutoff_date:
            continue

        # Skip if J+50 alert already exists for this IA
        existing = frappe.db.exists("Alerte", {
            "insemination": ia.name,
            "type_alerte": "VERIFICATION_J50",
            "statut": "NOUVELLE"
        })
        if existing:
            continue

        # Skip if J+50 already resolved
        resolved = frappe.db.exists("Alerte", {
            "insemination": ia.name,
            "type_alerte": "VERIFICATION_J50",
            "statut": ["in", ["GESTANTE_CONFIRMEE", "RETOUR_CHALEUR"]]
        })
        if resolved:
            continue

        days_since = date_diff(getdate(today()), ia.date_ia)

        doc = frappe.get_doc({
            "doctype": "Alerte",
            "animal": alert.animal,
            "type_alerte": "VERIFICATION_J50",
            "insemination": ia.name,
            "date_alerte": today(),
            "raison": f"IA du {ia.date_ia} - J+{days_since} - Confirmation gestation",
            "statut": "NOUVELLE"
        })
        doc.insert(ignore_permissions=True)


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
    elif action == "gestante_probable":
        doc.statut = "GESTANTE_PROBABLE"
    elif action == "gestante_confirmee":
        doc.statut = "GESTANTE_CONFIRMEE"

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