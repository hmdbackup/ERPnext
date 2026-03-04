# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, date_diff


class Pesee(Document):
    def validate(self):
        self.validate_animal()
        self.validate_date()
        self.calculate_age()
        self.calculate_gmq()


    def validate_animal(self):
        if not frappe.db.exists("Animal", self.animal):
            frappe.throw("L'animal {0} n'existe pas".format(self.animal))

        statut = frappe.db.get_value("Animal", self.animal, "statut")
        if statut != "ACTIF":
            frappe.throw("Impossible d'ajouter une pesée pour un animal non actif")
    
    def validate_date(self):
        if self.date_pesee and getdate(self.date_pesee) > getdate(frappe.utils.today()):
            frappe.throw("La date de pesée ne peut pas être dans le futur.")

    def calculate_age(self):
        if self.animal and self.date_pesee:
            date_naissance = frappe.db.get_value("Animal", self.animal, "date_naissance")
            if date_naissance:
                self.age_jours = date_diff(getdate(self.date_pesee), getdate(date_naissance))

    def calculate_gmq(self):
        if self.animal and self.date_pesee and self.poids_kg:
            previous = frappe.db.get_all("Pesee", filters={
                "animal": self.animal,
                "date_pesee": ["<", self.date_pesee],
                "name": ["!=", self.name or ""]
            }, fields=["poids_kg", "date_pesee"],
            order_by="date_pesee desc", limit=1)

            if previous:
                jours = date_diff(getdate(self.date_pesee), getdate(previous[0].date_pesee))
                if jours > 0:
                    diff_poids = self.poids_kg - previous[0].poids_kg
                    self.gain_quotidien_moyen = round((diff_poids / jours) * 1000, 3)
    

    def after_insert(self):
        self.update_animal_poids()

    def on_update(self):
        self.update_animal_poids()

    def on_trash(self):
        self.update_animal_poids(on_delete=True)

    def update_animal_poids(self, on_delete=False):
        """Always fetch the latest pesée to update Animal.dernier_poids"""
        exclude = self.name if on_delete else None
        filters = {"animal": self.animal}
        if exclude:
            filters["name"] = ["!=", exclude]
        latest = frappe.db.get_value(
            "Pesee",
            filters=filters,
            fieldname="poids_kg",
            order_by="date_pesee desc, creation desc"
        )
        frappe.db.set_value("Animal", self.animal, "dernier_poids", latest or None)