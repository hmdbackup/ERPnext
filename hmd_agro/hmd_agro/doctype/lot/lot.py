# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Lot(Document):
	def update_nb_animaux(self, exclude_animal=None):
		"""Count active animals in this lot and update nb_animaux"""
		filters = {"id_lot": self.name, "statut": "ACTIF"}
		if exclude_animal:
			filters["name"] = ["!=", exclude_animal]
		count = frappe.db.count("Animal", filters)
		self.db_set("nb_animaux", count, update_modified=False)


def update_lot_animal_count(lot_name, exclude_animal=None):
	"""Utility to update nb_animaux for a given lot"""
	if lot_name:
		lot = frappe.get_doc("Lot", lot_name)
		lot.update_nb_animaux(exclude_animal=exclude_animal)
