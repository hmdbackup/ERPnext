# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class InterventionMaintenance(Document):
    def validate(self):
        self.validate_equipement()
        self.validate_date()

    def validate_equipement(self):
        if not frappe.db.exists("Equipement", self.equipement):
            frappe.throw("L'équipement {0} n'existe pas".format(self.equipement))

    def validate_date(self):
        if self.date_intervention and getdate(self.date_intervention) > getdate(today()):
            frappe.throw("La date d'intervention ne peut pas être dans le futur.")

    # --- RG23: an intervention updates the equipment's last-maintenance date ---
    # Mirrors the Pesee -> Animal.dernier_poids pattern: on every write/delete we
    # recompute from the *latest* completed intervention rather than blindly
    # stamping self, so edits and deletions stay consistent.

    def after_insert(self):
        self.update_equipement_maintenance()

    def on_update(self):
        self.update_equipement_maintenance()

    def on_trash(self):
        self.update_equipement_maintenance(on_delete=True)

    def update_equipement_maintenance(self, on_delete=False):
        """Set Equipement.date_derniere_maintenance to the most recent REALISEE
        intervention date for this equipment. Only completed interventions count
        toward "last maintenance"; planned/cancelled ones are ignored."""
        exclude = self.name if on_delete else None
        filters = {"equipement": self.equipement, "statut": "REALISEE"}
        if exclude:
            filters["name"] = ["!=", exclude]

        latest = frappe.db.get_value(
            "Intervention Maintenance",
            filters=filters,
            fieldname="date_intervention",
            order_by="date_intervention desc, creation desc",
        )

        equipement = frappe.get_doc("Equipement", self.equipement)
        equipement.date_derniere_maintenance = latest or None
        # Recompute date_prochaine_maintenance via Equipement.validate().
        equipement.save(ignore_permissions=True)
