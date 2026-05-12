# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, getdate, today

from hmd_agro.hmd_agro.utils.config import get_config


class Traite(Document):
    def validate(self):
        self.lock_identity_fields()
        self.auto_link_lactation()
        self.auto_fill_id_lot()
        self.validate_lactation_en_cours()
        self.validate_date()
        self.validate_quantite()
        self.validate_unique_session()
        self.validate_taux()
        self.fallback_quantite_brut()
        self.warn_attente_lait()

    def fallback_quantite_brut(self):
        """If brut wasn't set explicitly (form creation, bulk import, legacy),
        seed it with the current quantite_litres so the reconciliation math
        always has a brut to read."""
        if not self.quantite_litres_brut and self.quantite_litres is not None:
            self.quantite_litres_brut = self.quantite_litres

    def auto_fill_id_lot(self):
        """Stamp the cow's current lot at save time so historical reports keep the right attribution."""
        if not self.id_lot and self.animal:
            self.id_lot = frappe.db.get_value("Animal", self.animal, "id_lot")

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
        max_litres = get_config("traite_max_litres", default=60)
        if self.quantite_litres is not None and self.quantite_litres > max_litres:
            frappe.throw(f"La quantité ne peut pas dépasser {max_litres} litres par traite.")

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
        max_tb = get_config("taux_tb_max_pct", default=10)
        max_tp = get_config("taux_tp_max_pct", default=10)
        if self.taux_tb is not None and self.taux_tb > 0:
            if self.taux_tb > max_tb:
                frappe.throw(f"Le taux butyreux ne peut pas dépasser {max_tb}%.")
        if self.taux_tp is not None and self.taux_tp > 0:
            if self.taux_tp > max_tp:
                frappe.throw(f"Le taux protéique ne peut pas dépasser {max_tp}%.")

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

    def before_insert(self):
        self._inherit_taux_from_bilan()

    def _inherit_taux_from_bilan(self):
        """Pull daily herd TB/TP from Bilan Lait Journalier if not already set.
        Handles the case where the Bilan was saved before this Traite was inserted
        (e.g. backfill of a date that already has a Bilan)."""
        if not self.date_traite:
            return
        if self.taux_tb and self.taux_tp:
            return
        bilan = frappe.db.get_value(
            "Bilan Lait Journalier",
            {"date": self.date_traite},
            ["taux_tb_moyen", "taux_tp_moyen"],
            as_dict=True,
        )
        if not bilan:
            return
        if not self.taux_tb and bilan.taux_tb_moyen:
            self.taux_tb = bilan.taux_tb_moyen
        if not self.taux_tp and bilan.taux_tp_moyen:
            self.taux_tp = bilan.taux_tp_moyen

    def after_insert(self):
        self.update_lactation_production()

    def on_update(self):
        self.update_lactation_production()

    def on_trash(self):
        self.update_lactation_production()

    def update_lactation_production(self):
        """Update lactation totals from all traites.
        Bulk imports set flags.skip_lactation_update to defer recalc to a single
        end-of-import pass per affected lactation."""
        if not self.lactation:
            return
        if self.flags.get("skip_lactation_update"):
            return

        date_debut = frappe.db.get_value("Lactation", self.lactation, "date_debut")

        # Production Totale: sum of ALL traites
        total = frappe.db.sql("""
            SELECT SUM(quantite_litres)
            FROM `tabTraite`
            WHERE lactation = %s
        """, self.lactation)[0][0] or 0

        # Pic Production: best daily total within first N DIM (default 150)
        pic_window = cint(get_config("pic_production_jours", default=150))
        pic = frappe.db.sql(f"""
            SELECT MAX(daily_total) FROM (
                SELECT SUM(quantite_litres) as daily_total
                FROM `tabTraite`
                WHERE lactation = %s
                  AND DATEDIFF(date_traite, %s) <= {pic_window}
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

            # Production Initiale: sum of traites within first N days (default 60)
            init_window = cint(get_config("production_initiale_jours", default=60))
            prod_init = frappe.db.sql(f"""
                SELECT SUM(quantite_litres)
                FROM `tabTraite`
                WHERE lactation = %s
                  AND DATEDIFF(date_traite, %s) <= {init_window}
            """, (self.lactation, date_debut))[0][0] or 0
            updates["production_initiale"] = round(prod_init, 2)

            # Moyenne Production: average daily production
            from frappe.utils import date_diff, today as today_fn
            jours = date_diff(today_fn(), date_debut)
            if jours > 0:
                updates["moyenne_production"] = round(total / jours, 2)

        frappe.db.set_value("Lactation", self.lactation, updates)


@frappe.whitelist()
def backfill_id_lot():
    """One-time: stamp id_lot on existing Traite records using each animal's current lot."""
    rows = frappe.db.sql("""
        SELECT t.name, a.id_lot
        FROM `tabTraite` t JOIN `tabAnimal` a ON t.animal = a.name
        WHERE (t.id_lot IS NULL OR t.id_lot = '') AND a.id_lot IS NOT NULL AND a.id_lot != ''
    """, as_dict=True)
    for r in rows:
        frappe.db.set_value("Traite", r.name, "id_lot", r.id_lot, update_modified=False)
    frappe.db.commit()
    return {"backfilled": len(rows)}


@frappe.whitelist()
def get_production_journaliere():
    """Return yesterday's total milk production for the dashboard card"""
    from frappe.utils import add_days
    yesterday = add_days(today(), -1)
    result = frappe.db.sql("""
        SELECT SUM(quantite_litres) as total
        FROM `tabTraite`
        WHERE date_traite = %s
    """, yesterday)[0][0] or 0
    return {
        "value": round(result, 1),
        "fieldtype": "Float"
    }