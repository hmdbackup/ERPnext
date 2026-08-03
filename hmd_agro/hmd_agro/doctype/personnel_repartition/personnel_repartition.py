# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PersonnelRepartition(Document):
    """Ligne de ventilation analytique d'un salarié : quelle part de son coût
    est imputée à quel atelier (Cost Center). Validée par le parent Personnel
    (la somme des parts doit faire 100 %)."""
    pass
