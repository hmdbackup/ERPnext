import frappe
from frappe.utils import today


@frappe.whitelist()
def get_alerts():
    """Get all actionable alerts grouped by type"""
    alerts = frappe.get_all("Alerte",
        filters={
            "statut": ["in", ["NOUVELLE", "CONFIRMEE"]],
            "date_alerte": ["<=", today()]
        },
        fields=["name", "animal", "type_alerte", "date_alerte", "raison", "insemination", "statut"],
        order_by="date_alerte asc"
    )

    for a in alerts:
        animal = frappe.db.get_value("Animal", a.animal,
            ["nom_metier", "categorie", "etat_gestation"], as_dict=True)
        if animal:
            a.nom_metier = animal.nom_metier or a.animal
            a.categorie = animal.categorie
            a.etat_gestation = animal.etat_gestation

    groups = {
        "CHALEUR_GENISSE": {"label": "Chaleurs Genisses", "alerts": []},
        "CHALEUR_POST_VELAGE": {"label": "Chaleurs Post-Velage", "alerts": []},
        "CONFIRMEE": {"label": "Chaleurs Confirmees - En attente IA", "alerts": []},
        "VERIFICATION_J21": {"label": "Vérification IA J+21", "alerts": []},
        "VERIFICATION_J50": {"label": "Vérifications Programmées", "alerts": []}
    }

    for a in alerts:
        if a.statut == "CONFIRMEE":
            groups["CONFIRMEE"]["alerts"].append(a)
        elif a.type_alerte in groups:
            groups[a.type_alerte]["alerts"].append(a)

    return groups