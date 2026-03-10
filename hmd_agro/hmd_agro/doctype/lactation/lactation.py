# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, date_diff


class Lactation(Document):
    def validate(self):
        self.lock_identity_fields()
        self.auto_set_numero_lactation()
        self.validate_animal_eligible()
        self.validate_no_active_lactation()
        self.validate_statut_transition()
        self.validate_dates()
        self.calculate_jours_lactation()

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
                "Supprimez cette lactation et créez-en une nouvelle."
            )

    def auto_set_numero_lactation(self):
        """Auto-calculate lactation number for this animal"""
        if self.animal and self.is_new():
            count = frappe.db.count("Lactation", {"animal": self.animal})
            self.numero_lactation = count + 1

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
        if self.date_tarissement and self.date_debut:
            if getdate(self.date_tarissement) < getdate(self.date_debut):
                frappe.throw("ERR-LAC-04: La date de tarissement ne peut pas être avant la date de début.")

    def calculate_jours_lactation(self):
        if self.date_debut:
            end = getdate(self.date_tarissement) if self.date_tarissement else getdate(today())
            self.jours_lactation = date_diff(end, getdate(self.date_debut))

    def after_insert(self):
        """Fix 3: Sync animal etat_lactation on manual creation"""
        if self.statut == "EN_COURS" and self.animal:
            frappe.db.set_value("Animal", self.animal, "etat_lactation", "EN_PRODUCTION")

    def on_update(self):
        self.auto_fill_date_tarissement()
        self.sync_animal_etat()

    def auto_fill_date_tarissement(self):
        """Auto-fill date_tarissement when statut changes to TARIE"""
        if not self.has_value_changed("statut"):
            return
        if self.statut == "TARIE" and not self.date_tarissement:
            frappe.db.set_value("Lactation", self.name, "date_tarissement", today())

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

    def on_trash(self):
        """Fix 6: Block deletion if linked records exist, otherwise reset animal"""
        if self.velage_debut:
            frappe.throw("Supprimez le vêlage associé avant de supprimer cette lactation.")

        if frappe.db.exists("Traite", {"lactation": self.name}):
            frappe.throw("Supprimez les traites d'abord avant de supprimer cette lactation.")

        if frappe.db.exists("Insemination", {"lactation": self.name}):
            frappe.throw("Supprimez les inséminations liées d'abord avant de supprimer cette lactation.")

        if self.animal and self.statut == "EN_COURS":
            frappe.db.set_value("Animal", self.animal, "etat_lactation", "")


@frappe.whitelist()
def get_production_chart_data(lactation):
    """Fix 8b: Return daily production data for chart rendering"""
    lac = frappe.get_doc("Lactation", lactation)

    data = frappe.db.sql("""
        SELECT date_traite, SUM(quantite_litres) as daily_total
        FROM `tabTraite`
        WHERE lactation = %s
        GROUP BY date_traite
        ORDER BY date_traite ASC
    """, lactation, as_dict=True)

    if not data:
        return None

    labels = [d.date_traite.strftime("%d/%m") for d in data]
    values = [float(d.daily_total or 0) for d in data]

    return {
        "labels": labels,
        "datasets": [{"values": values}],
        "date_debut": str(lac.date_debut) if lac.date_debut else None
    }


@frappe.whitelist()
def get_traite_grid_data(lactation):
    """Return traites grouped by date and session for the production grid."""
    traites = frappe.db.sql("""
        SELECT date_traite, session, quantite_litres, name
        FROM `tabTraite`
        WHERE lactation = %s
        ORDER BY date_traite DESC, FIELD(session, 'MATIN', 'SOIR')
    """, lactation, as_dict=True)

    if not traites:
        return None

    dates = {}
    for t in traites:
        d = str(t.date_traite)
        if d not in dates:
            dates[d] = {"date": d, "MATIN": None, "SOIR": None, "total": 0}
        dates[d][t.session] = float(t.quantite_litres or 0)
        dates[d]["total"] += float(t.quantite_litres or 0)

    rows = sorted(dates.values(), key=lambda x: x["date"], reverse=True)

    # Round totals
    for r in rows:
        r["total"] = round(r["total"], 1)

    return rows
