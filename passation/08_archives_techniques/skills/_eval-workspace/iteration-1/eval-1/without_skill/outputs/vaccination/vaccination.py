# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class Vaccination(Document):
    def validate(self):
        self.validate_vaccin_type()
        self.validate_dates()

    def validate_vaccin_type(self):
        """The linked Medicament must be of type VACCIN — vaccinations only
        record vaccine products, not other médicaments."""
        if not self.vaccin:
            return
        type_medicament = frappe.db.get_value("Medicament", self.vaccin, "type_medicament")
        if type_medicament != "VACCIN":
            frappe.throw(
                f"Le médicament '{self.vaccin}' n'est pas un vaccin "
                f"(type: {type_medicament or 'inconnu'}). "
                f"Seuls les médicaments de type VACCIN sont autorisés."
            )

    def validate_dates(self):
        """The next-due date, when set, must be after the date given."""
        if self.date_prochaine and self.date_vaccination:
            if getdate(self.date_prochaine) <= getdate(self.date_vaccination):
                frappe.throw(
                    "La prochaine échéance doit être postérieure à la date de vaccination."
                )
