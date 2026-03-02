# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class Traite(Document):
    def validate(self):
        self.auto_link_lactation()
        self.validate_lactation_en_cours()
        self.validate_date()
        self.validate_quantite()
        self.validate_unique_session()
        self.validate_taux()

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

        # Total production
        total = frappe.db.sql("""
            SELECT SUM(quantite_litres)
            FROM `tabTraite`
            WHERE lactation = %s
        """, self.lactation)[0][0] or 0

        # Peak daily production
        pic = frappe.db.sql("""
            SELECT MAX(daily_total) FROM (
                SELECT SUM(quantite_litres) as daily_total
                FROM `tabTraite`
                WHERE lactation = %s
                GROUP BY date_traite
            ) as daily
        """, self.lactation)[0][0] or 0

        frappe.db.set_value("Lactation", self.lactation, {
            "production_totale": total,
            "pic_production": pic
        })