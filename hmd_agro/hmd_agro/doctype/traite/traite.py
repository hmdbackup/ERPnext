# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class Traite(Document):
    def validate(self):
        self.lock_identity_fields()
        self.auto_link_lactation()
        self.validate_lactation_en_cours()
        self.validate_date()
        self.validate_quantite()
        self.validate_unique_session()
        self.validate_taux()
        self.warn_attente_lait()

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
                "Supprimez cette traite et créez-en une nouvelle."
            )

    def auto_link_lactation(self):
        """Auto-link to animal's active lactation"""
        if self.animal and not self.lactation:
            lactation = frappe.db.get_value("Lactation", {
                "animal": self.animal,
                "statut": "EN_COURS"
            }, "name")
            if lactation:
                self.lactation = lactation

    def validate_lactation_en_cours(self):
        """CF-TRA-01: Lactation must be EN_COURS"""
        if not self.lactation:
            frappe.throw("Cet animal n'a pas de lactation en cours.")

        statut = frappe.db.get_value("Lactation", self.lactation, "statut")
        if statut != "EN_COURS":
            frappe.throw("La lactation liée n'est pas en cours.")

    def validate_date(self):
        """CF-TRA-02: Date must be within lactation period"""
        if self.date_traite and getdate(self.date_traite) > getdate(today()):
            frappe.throw("La date de traite ne peut pas être dans le futur.")

        if self.lactation and self.date_traite:
            date_debut = frappe.db.get_value("Lactation", self.lactation, "date_debut")
            if date_debut and getdate(self.date_traite) < getdate(date_debut):
                frappe.throw("La date de traite ne peut pas être avant le début de la lactation.")

    def validate_quantite(self):
        """Quantity must be >= 0 and reasonable"""
        if self.quantite_litres is not None and self.quantite_litres < 0:
            frappe.throw("La quantité ne peut pas être négative.")
        if self.quantite_litres is not None and self.quantite_litres > 60:
            frappe.throw("La quantité ne peut pas dépasser 60 litres par traite.")

    def validate_unique_session(self):
        """CF-TRA-03: Unique combination of animal + date + session"""
        if self.animal and self.date_traite and self.session:
            existing = frappe.db.exists("Traite", {
                "animal": self.animal,
                "date_traite": self.date_traite,
                "session": self.session,
                "name": ["!=", self.name or ""]
            })
            if existing:
                frappe.throw(
                    f"Une traite {self.session} existe déjà pour cet animal à cette date ({existing})."
                )

    def validate_taux(self):
        """Validate quality rates if provided"""
        if self.taux_tb is not None and self.taux_tb > 0:
            if self.taux_tb > 10:
                frappe.throw("Le taux butyreux ne peut pas dépasser 10%.")
        if self.taux_tp is not None and self.taux_tp > 0:
            if self.taux_tp > 10:
                frappe.throw("Le taux protéique ne peut pas dépasser 10%.")

    def warn_attente_lait(self):
        """CF-TMD-03: Warn if animal is under milk withdrawal period"""
        if self.animal:
            attente = frappe.db.get_value("Animal", self.animal,
                ["attente_lait_active", "date_fin_attente_lait"], as_dict=True)
            if attente and attente.attente_lait_active:
                frappe.msgprint(
                    f"Attention: Cet animal est sous délai d'attente lait jusqu'au {attente.date_fin_attente_lait}. "
                    f"Le lait ne doit pas être collecté.",
                    indicator="red",
                    alert=True
                )

    def after_insert(self):
        self.update_lactation_production()

    def on_update(self):
        self.update_lactation_production()

    def on_trash(self):
        self.update_lactation_production()

    def update_lactation_production(self):
        """Update lactation totals from all traites"""
        if not self.lactation:
            return

        date_debut = frappe.db.get_value("Lactation", self.lactation, "date_debut")

        # Production Totale: sum of ALL traites
        total = frappe.db.sql("""
            SELECT SUM(quantite_litres)
            FROM `tabTraite`
            WHERE lactation = %s
        """, self.lactation)[0][0] or 0

        # Pic Production: best daily total within first 150 DIM
        pic = frappe.db.sql("""
            SELECT MAX(daily_total) FROM (
                SELECT SUM(quantite_litres) as daily_total
                FROM `tabTraite`
                WHERE lactation = %s
                  AND DATEDIFF(date_traite, %s) <= 150
                GROUP BY date_traite
            ) as daily
        """, (self.lactation, date_debut))[0][0] or 0

        updates = {
            "production_totale": total,
            "pic_production": pic
        }

        if date_debut:
            # Lactation 305j: actual sum of traites within first 305 days only
            total_305 = frappe.db.sql("""
                SELECT SUM(quantite_litres)
                FROM `tabTraite`
                WHERE lactation = %s
                  AND DATEDIFF(date_traite, %s) <= 305
            """, (self.lactation, date_debut))[0][0] or 0
            updates["lactation_305j"] = round(total_305, 2)

            # Production Initiale: sum of traites within first 60 days
            prod_init = frappe.db.sql("""
                SELECT SUM(quantite_litres)
                FROM `tabTraite`
                WHERE lactation = %s
                  AND DATEDIFF(date_traite, %s) <= 60
            """, (self.lactation, date_debut))[0][0] or 0
            updates["production_initiale"] = round(prod_init, 2)

            # Moyenne Production: average daily production
            from frappe.utils import date_diff, today as today_fn
            jours = date_diff(today_fn(), date_debut)
            if jours > 0:
                updates["moyenne_production"] = round(total / jours, 2)

        frappe.db.set_value("Lactation", self.lactation, updates)