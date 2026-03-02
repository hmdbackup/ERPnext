# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff


class Lactation(Document):
    def validate(self):
        self.validate_animal_eligible()
        self.validate_no_active_lactation()
        self.validate_statut_transition()
        self.validate_dates()
        self.calculate_jours_lactation()

    def validate_statut_transition(self):
        """Enforce one-way state transitions for statut"""
        if self.is_new() or self.flags.ignore_validate:
            return
        if not self.has_value_changed("statut"):
            return

        old = self.get_doc_before_save()
        if not old:
            return

        old_val = old.statut
        new_val = self.statut

        allowed = {
            "EN_COURS": ["TARIE", "INTERROMPUE"],
            "TARIE": [],
            "INTERROMPUE": [],
        }

        if new_val not in allowed.get(old_val, []):
            frappe.throw(
                f"Transition non autorisée: {old_val} → {new_val}. "
                f"Transitions possibles depuis {old_val}: {', '.join(allowed.get(old_val, [])) or 'aucune (état final)'}."
            )

    def validate_animal_eligible(self):
        if self.animal:
            categorie, sexe = frappe.db.get_value(
                "Animal", self.animal, ["categorie", "sexe"]
            )
            if sexe != "F":
                frappe.throw("ERR-LAC-01: Seuls les animaux femelles peuvent avoir une lactation.")
            if categorie not in ["VACHE", "GENISSE"]:
                frappe.throw("ERR-LAC-02: Seules les vaches et génisses peuvent avoir une lactation.")

    def validate_no_active_lactation(self):
        if self.animal and self.statut == "EN_COURS":
            existing = frappe.db.exists("Lactation", {
                "animal": self.animal,
                "statut": "EN_COURS",
                "name": ["!=", self.name or ""]
            })
            if existing:
                frappe.throw(
                    f"ERR-LAC-03: L'animal {self.animal} a déjà une lactation en cours ({existing})."
                )

    def validate_dates(self):
        if self.date_fin and self.date_debut:
            if getdate(self.date_fin) < getdate(self.date_debut):
                frappe.throw("ERR-LAC-04: La date de fin ne peut pas être avant la date de début.")
        if self.date_tarissement and self.date_debut:
            if getdate(self.date_tarissement) < getdate(self.date_debut):
                frappe.throw("ERR-LAC-05: La date de tarissement ne peut pas être avant la date de début.")

    def calculate_jours_lactation(self):
        if self.date_debut:
            end = getdate(self.date_fin) if self.date_fin else getdate(today())
            self.jours_lactation = date_diff(end, getdate(self.date_debut))

    
    def on_update(self):
        self.sync_animal_etat()

    def sync_animal_etat(self):
        """When lactation status changes, update animal"""
        if not self.has_value_changed("statut"):
            return

        if self.animal:
            if self.statut == "TARIE":
                frappe.db.set_value("Animal", self.animal, "etat_lactation", "TARIE")
            elif self.statut == "INTERROMPUE":
                frappe.db.set_value("Animal", self.animal, "etat_lactation", "")
            elif self.statut == "EN_COURS":
                frappe.db.set_value("Animal", self.animal, "etat_lactation", "EN_PRODUCTION")
