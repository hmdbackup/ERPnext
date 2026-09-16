import frappe
from frappe import _
from frappe.model.document import Document


class Vaccination(Document):
    def validate(self):
        self.lock_identity_fields()
        self.validate_animal()
        self.validate_vaccin()
        self.validate_dates()

    def lock_identity_fields(self):
        """Prevent editing animal/vaccin after creation (CF-VAC-01)."""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return
        if str(self.animal or "") != str(db_doc.animal or ""):
            frappe.throw(
                _("Le champ 'Animal' ne peut pas être modifié après création. "
                "Supprimez cette vaccination et créez-en une nouvelle.")
            )
        if str(self.vaccin or "") != str(db_doc.vaccin or ""):
            frappe.throw(
                _("Le champ 'Vaccin' ne peut pas être modifié après création. "
                "Supprimez cette vaccination et créez-en une nouvelle.")
            )

    def validate_animal(self):
        if not frappe.db.exists("Animal", self.animal):
            frappe.throw(_("L'animal {0} n'existe pas").format(self.animal))

        statut = frappe.db.get_value("Animal", self.animal, "statut")
        if statut != "ACTIF":
            frappe.throw(_("Impossible d'enregistrer une vaccination pour un animal non actif"))

    def validate_vaccin(self):
        """ERR-VAC-01: the linked Medicament must be of type VACCIN."""
        if not frappe.db.exists("Medicament", self.vaccin):
            frappe.throw(_("Le vaccin {0} n'existe pas").format(self.vaccin))

        type_medicament = frappe.db.get_value("Medicament", self.vaccin, "type_medicament")
        if type_medicament != "VACCIN":
            frappe.throw(
                _("ERR-VAC-01: Le produit {0} n'est pas un vaccin (type_medicament doit être VACCIN).").format(
                    self.vaccin
                )
            )

    def validate_dates(self):
        if self.date_vaccination and self.date_vaccination > frappe.utils.today():
            frappe.throw(_("La date de vaccination ne peut pas être dans le futur"))

        if self.date_rappel and self.date_vaccination and self.date_rappel <= self.date_vaccination:
            frappe.throw(_("La date de rappel doit être postérieure à la date de vaccination"))
