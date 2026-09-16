# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate


class Equipement(Document):
    def validate(self):
        self.compute_prochaine_maintenance()

    def compute_prochaine_maintenance(self):
        """Derive the next preventive-maintenance due date from the last
        intervention date + the configured periodicity. Cleared when either
        input is missing so the field never shows a stale value."""
        if self.date_derniere_maintenance and self.periodicite_maintenance_jours:
            self.date_prochaine_maintenance = add_days(
                getdate(self.date_derniere_maintenance),
                int(self.periodicite_maintenance_jours),
            )
        else:
            self.date_prochaine_maintenance = None
