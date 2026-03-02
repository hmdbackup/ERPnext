# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff


class Avortement(Document):
    def validate(self):
        self.validate_animal_gestante()
        self.validate_date_avortement()
        self.auto_link_insemination()
        self.calculate_stade_gestation()
        self.lock_identity_fields()

    def validate_animal_gestante(self):
        """Only GESTANTE animals can have an abortion"""
        if not self.animal:
            return
        etat = frappe.db.get_value("Animal", self.animal, "etat_gestation")
        if self.is_new() and etat != "GESTANTE":
            frappe.throw("ERR-AVO-01: Seul un animal gestant peut avoir un avortement.")

    def validate_date_avortement(self):
        """Date cannot be in the future and must be after IA date"""
        if self.date_avortement and getdate(self.date_avortement) > getdate(today()):
            frappe.throw("ERR-AVO-02: La date d'avortement ne peut pas être dans le futur.")

        if self.insemination and self.date_avortement:
            date_ia = frappe.db.get_value("Insemination", self.insemination, "date_ia")
            if date_ia and getdate(self.date_avortement) <= getdate(date_ia):
                frappe.throw(
                    f"ERR-AVO-03: La date d'avortement doit être après la date d'insémination ({date_ia})."
                )

    def auto_link_insemination(self):
        """Auto-fill insemination from animal's id_ia_fecondante"""
        if self.animal and not self.insemination:
            ia = frappe.db.get_value("Animal", self.animal, "id_ia_fecondante")
            if ia:
                self.insemination = ia

    def calculate_stade_gestation(self):
        """Calculate days of gestation at abortion time"""
        if self.insemination and self.date_avortement:
            date_ia = frappe.db.get_value("Insemination", self.insemination, "date_ia")
            if date_ia:
                self.stade_gestation = date_diff(getdate(self.date_avortement), getdate(date_ia))

    def lock_identity_fields(self):
        """Prevent editing animal and date after creation"""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return

        locked = {"animal": "Animal", "date_avortement": "Date Avortement"}
        for field, label in locked.items():
            if str(self.get(field) or "") != str(db_doc.get(field) or ""):
                frappe.throw(
                    f"Le champ '{label}' ne peut pas être modifié après création. "
                    f"Supprimez cet avortement et créez-en un nouveau."
                )

    def after_insert(self):
        """Clear reproduction fields on animal, set to VIDE"""
        self.update_animal_on_abortion()

    def update_animal_on_abortion(self):
        """Reset animal gestation state"""
        if not self.animal:
            return
        animal = frappe.get_doc("Animal", self.animal)
        animal.etat_gestation = "VIDE"
        animal.id_ia_fecondante = None
        animal.date_velage_prevue = None
        animal.date_tarissement = None
        animal.flags.ignore_validate = True
        animal.save()

        display_name = animal.nom_metier or self.animal
        frappe.msgprint(
            f"Animal {display_name}: avortement enregistré, gestation annulée."
        )

        # Close any open gestation alerts for this animal
        open_alerts = frappe.get_all("Alerte", filters={
            "animal": self.animal,
            "statut": ["in", ["NOUVELLE", "CONFIRMEE", "GESTANTE_PROBABLE"]]
        }, pluck="name")
        for alert in open_alerts:
            frappe.db.set_value("Alerte", alert, {
                "statut": "NON_CONFIRMEE",
                "date_traitement": today()
            })

    def on_trash(self):
        """Safe delete: restore animal to GESTANTE with IA fields"""
        if not self.animal:
            return

        # Restore animal to GESTANTE
        animal = frappe.get_doc("Animal", self.animal)
        animal.etat_gestation = "GESTANTE"

        if self.insemination:
            date_ia = frappe.db.get_value("Insemination", self.insemination, "date_ia")
            if date_ia:
                animal.id_ia_fecondante = self.insemination
                animal.date_velage_prevue = frappe.utils.add_days(date_ia, 280)
                animal.date_tarissement = frappe.utils.add_days(animal.date_velage_prevue, -60)

        animal.flags.ignore_validate = True
        animal.save()

        display_name = animal.nom_metier or self.animal
        frappe.msgprint(
            f"Avortement supprimé: {display_name} restauré à GESTANTE."
        )
