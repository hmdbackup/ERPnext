# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_days


class Traitement(Document):
    def validate(self):
        self.validate_animal_active()
        self.validate_date_traitement()
        self.lock_identity_fields()
        self.validate_type_has_medicaments()
        self.calculate_attente_dates()

    def after_insert(self):
        self.decrement_medicament_stock()
        self.update_animal_attente_lait()

    def on_trash(self):
        self.restore_medicament_stock()
        self.update_animal_attente_lait(clear=True)

    def validate_animal_active(self):
        """RG19: Animal must be ACTIF for treatment"""
        if self.animal:
            statut = frappe.db.get_value("Animal", self.animal, "statut")
            if statut != "ACTIF":
                frappe.throw("RG19: L'animal doit être ACTIF pour recevoir un traitement.")

    def validate_date_traitement(self):
        """Date traitement cannot be in the future"""
        if self.date_traitement and getdate(self.date_traitement) > getdate(today()):
            frappe.throw("La date de traitement ne peut pas être dans le futur.")

    def lock_identity_fields(self):
        """Prevent editing animal after creation"""
        if self.is_new() or self.flags.ignore_validate:
            return
        db_doc = self.get_doc_before_save()
        if not db_doc:
            return

        if str(self.animal or "") != str(db_doc.animal or ""):
            frappe.throw(
                "Le champ 'Animal' ne peut pas être modifié après création. "
                "Supprimez ce traitement et créez-en un nouveau."
            )

    def validate_type_has_medicaments(self):
        """CF-TRT-02: TRAITEMENT_MEDICAL must have medicaments, PARAGE must not"""
        if self.type_traitement == "TRAITEMENT_MEDICAL":
            if not self.medicaments or len(self.medicaments) == 0:
                frappe.throw(
                    "Un traitement médical doit contenir au moins un médicament."
                )
        elif self.type_traitement == "PARAGE":
            if self.medicaments and len(self.medicaments) > 0:
                frappe.throw(
                    "Un parage ne doit pas contenir de médicaments."
                )

    def calculate_attente_dates(self):
        """RC-TMD-01: Calculate date_fin_attente_lait for each medicament row"""
        if self.type_traitement != "TRAITEMENT_MEDICAL" or not self.medicaments:
            return
        for row in self.medicaments:
            if row.delai_attente_lait and self.date_traitement:
                row.date_fin_attente_lait = add_days(
                    self.date_traitement, row.delai_attente_lait
                )

    def decrement_medicament_stock(self):
        """RG20: Decrement stock_actuel by 1 for each medicament used"""
        if self.type_traitement != "TRAITEMENT_MEDICAL" or not self.medicaments:
            return
        for row in self.medicaments:
            if row.medicament:
                stock = frappe.db.get_value("Medicament", row.medicament, "stock_actuel")
                if stock and stock > 0:
                    frappe.db.set_value("Medicament", row.medicament,
                        "stock_actuel", stock - 1)
                else:
                    frappe.msgprint(
                        f"Attention: Stock épuisé pour le médicament {row.medicament}.",
                        indicator="orange",
                        alert=True
                    )

    def restore_medicament_stock(self):
        """Restore +1 to stock_actuel for each medicament on delete"""
        if self.type_traitement != "TRAITEMENT_MEDICAL" or not self.medicaments:
            return
        for row in self.medicaments:
            if row.medicament:
                stock = frappe.db.get_value("Medicament", row.medicament, "stock_actuel")
                if stock is not None:
                    frappe.db.set_value("Medicament", row.medicament,
                        "stock_actuel", stock + 1)

    def update_animal_attente_lait(self, clear=False):
        """Update Animal milk withdrawal flag based on all treatments"""
        if not self.animal:
            return

        if clear:
            # Recalculate from all OTHER traitements for this animal
            max_date = frappe.db.sql("""
                SELECT MAX(tm.date_fin_attente_lait)
                FROM `tabTraitement Medicale` tm
                JOIN `tabTraitement` t ON t.name = tm.parent
                WHERE t.animal = %s
                  AND t.name != %s
                  AND tm.date_fin_attente_lait >= %s
            """, (self.animal, self.name, today()))
        else:
            # Recalculate from ALL traitements for this animal
            max_date = frappe.db.sql("""
                SELECT MAX(tm.date_fin_attente_lait)
                FROM `tabTraitement Medicale` tm
                JOIN `tabTraitement` t ON t.name = tm.parent
                WHERE t.animal = %s
                  AND tm.date_fin_attente_lait >= %s
            """, (self.animal, today()))

        max_date = max_date[0][0] if max_date and max_date[0][0] else None

        if max_date:
            frappe.db.set_value("Animal", self.animal, {
                "attente_lait_active": 1,
                "date_fin_attente_lait": max_date
            })
        else:
            frappe.db.set_value("Animal", self.animal, {
                "attente_lait_active": 0,
                "date_fin_attente_lait": None
            })


@frappe.whitelist()
def refresh_attente_lait():
    """Clear expired milk withdrawal flags daily"""
    expired = frappe.get_all("Animal", filters={
        "attente_lait_active": 1,
        "date_fin_attente_lait": ["<", today()]
    }, pluck="name")
    for animal in expired:
        frappe.db.set_value("Animal", animal, {
            "attente_lait_active": 0,
            "date_fin_attente_lait": None
        })
    if expired:
        frappe.db.commit()
