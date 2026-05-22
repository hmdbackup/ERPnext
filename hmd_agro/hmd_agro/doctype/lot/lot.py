# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today

from hmd_agro.hmd_agro.doctype.lot_ration_history.lot_ration_history import (
	record_ration_assignment,
)


class Lot(Document):
	def validate(self):
		self.validate_ration_active()

	def validate_ration_active(self):
		"""CF-RAT-01: Cannot assign an inactive ration to a lot"""
		if self.id_ration_actuelle:
			active = frappe.db.get_value("Ration", self.id_ration_actuelle, "active")
			if not active:
				frappe.throw("La ration selectionnee n'est pas active.")

	def on_update(self):
		self._track_ration_change()

	def _track_ration_change(self):
		"""When id_ration_actuelle changes, close the open Lot Ration History
		episode and open a new one. Delegates to record_ration_assignment() so
		the Ration list-view bulk action and on-form edits use identical logic.

		Callers (e.g. the bulk-assign button) can pass `flags.ration_effective_date`
		to backdate the new episode; defaults to today when unset.
		"""
		if not self.has_value_changed("id_ration_actuelle"):
			return
		prev = self.get_doc_before_save()
		prev_ration = prev.id_ration_actuelle if prev else None
		if (prev_ration or "") == (self.id_ration_actuelle or ""):
			return
		date_debut = getattr(self.flags, "ration_effective_date", None) or today()
		source = getattr(self.flags, "ration_change_source", "MANUAL")
		record_ration_assignment(
			lot=self.name,
			new_ration=self.id_ration_actuelle or None,
			date_debut=date_debut,
			source=source,
		)

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
