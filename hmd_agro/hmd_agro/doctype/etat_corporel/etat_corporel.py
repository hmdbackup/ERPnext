import frappe
from frappe import _
from frappe.model.document import Document


VALID_SCORES = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]


class EtatCorporel(Document):
    def validate(self):
        self.validate_score()
        self.validate_animal()
        self.validate_date()

    def validate_score(self):
        try:
            score = float(self.score)
        except (ValueError, TypeError):
            frappe.throw(_("Le score doit être un nombre valide (entre 1 et 5)"))

        if score not in VALID_SCORES:
            frappe.throw(
                _("Le score doit être entre 1 et 5 par pas de 0.5 (1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5)")
            )

    def validate_animal(self):
        if not frappe.db.exists("Animal", self.animal):
            frappe.throw(_("L'animal {0} n'existe pas").format(self.animal))

        statut = frappe.db.get_value("Animal", self.animal, "statut")
        if statut != "ACTIF":
            frappe.throw(_("Impossible d'ajouter un état corporel pour un animal non actif"))

    def validate_date(self):
        if self.date and self.date > frappe.utils.today():
            frappe.throw(_("La date ne peut pas être dans le futur"))

    def after_insert(self):
        self.update_animal_score()

    def on_update(self):
        self.update_animal_score()

    def on_trash(self):
        self.update_animal_score(on_delete=True)

    def update_animal_score(self, on_delete=False):
        """Always fetch the latest score to update Animal.etat_corporel"""
        exclude = self.name if on_delete else None
        filters = {"animal": self.animal}
        if exclude:
            filters["name"] = ["!=", exclude]
        latest = frappe.db.get_value(
            "Etat Corporel",
            filters=filters,
            fieldname="score",
            order_by="date desc, creation desc"
        )
        frappe.db.set_value("Animal", self.animal, "etat_corporel", latest or None)