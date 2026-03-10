# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Medicament(Document):
    def validate(self):
        if self.stock_actuel is not None and self.stock_actuel < 0:
            frappe.msgprint(
                f"Attention: Le stock de {self.nom_medicament} est négatif ({self.stock_actuel}). "
                f"Veuillez vérifier l'inventaire.",
                indicator="orange",
                alert=True
            )
