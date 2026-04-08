from frappe import _


def get_data():
    return {
        "fieldname": "animal",
        "non_standard_fieldnames": {},
        "transactions": [
            {
                "label": _("Reproduction"),
                "items": ["Insemination", "Velage", "Avortement", "Alerte"]
            },
            {
                "label": _("Production"),
                "items": ["Lactation", "Traite"]
            },
            {
                "label": _("Suivi"),
                "items": ["Pesee", "Etat Corporel", "Note Mobilite"]
            },
            {
                "label": _("Santé"),
                "items": ["Traitement"]
            },
        ]
    }