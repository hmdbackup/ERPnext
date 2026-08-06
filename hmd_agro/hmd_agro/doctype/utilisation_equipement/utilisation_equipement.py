# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

"""FIN-S96 — heures d'utilisation d'un équipement et coût mécanique.

Décision de la réunion du 05/08/2026 (« option 2, la plus simple ») : chaque
équipement porte un **coût horaire forfaitaire** qui regroupe amortissement +
maintenance + mazout (25 DT/h par défaut, surchargeable équipement par
équipement). On saisit les heures réellement travaillées — « le tracteur a
travaillé 1 h ou 5 h dans la journée » — et le coût mécanique de l'atelier en
découle.

    coût mécanique = heures × coût horaire de l'équipement

ATTENTION — CE DOCUMENT NE POSTE AUCUNE ÉCRITURE (le piège de la story).
L'amortissement (comptes 68x) et l'entretien (compte 615) sont DÉJÀ au Grand
Livre, donc déjà dans le coût complet du litre. Valoriser les heures produirait
un DOUBLE COMPTAGE si on les postait. Le coût horaire est une vue purement
ANALYTIQUE : il sert à RÉPARTIR une charge déjà comptabilisée entre les
ateliers (Lait, Cultures - Fourrage, Traction…), pas à en créer une seconde.
Les lectures agrégées vivent dans
`utils.maintenance_utils.cout_utilisation(date_debut, date_fin)`.

Codes d'erreur : ERR-UTIL-01 → 05.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

# A day physically holds 24 hours: this is a bound on data entry (catching the
# "50 h in one day" typo), not a business threshold — nothing to configure.
HEURES_MAX_PAR_JOUR = 24.0


class UtilisationEquipement(Document):
    def validate(self):
        self.validate_heures()
        self.validate_equipement()
        self.validate_date()
        self.validate_atelier()
        self.calculer_cout()

    def validate_heures(self):
        heures = flt(self.heures)
        if heures <= 0:
            frappe.throw(
                _("ERR-UTIL-01 : les heures d'utilisation doivent être "
                  "strictement positives (saisi : {0}).").format(self.heures)
            )
        if heures > HEURES_MAX_PAR_JOUR:
            frappe.throw(
                _("ERR-UTIL-02 : {0} h sur une seule journée — le maximum est "
                  "{1} h. Répartir la saisie sur plusieurs jours.")
                .format(heures, HEURES_MAX_PAR_JOUR)
            )

    def validate_equipement(self):
        """Only a submitted Asset is a real, depreciating piece of equipment:
        a draft or cancelled one has no cost basis to spread."""
        docstatus = frappe.db.get_value("Asset", self.equipement, "docstatus")
        if docstatus != 1:
            frappe.throw(
                _("ERR-UTIL-03 : l'équipement « {0} » n'est pas soumis dans le "
                  "registre des immobilisations — aucune heure ne peut y être "
                  "rattachée.").format(self.equipement)
            )

    def validate_date(self):
        if getdate(self.date) > getdate(today()):
            frappe.throw(
                _("ERR-UTIL-04 : la date d'utilisation ({0}) est dans le futur "
                  "— on ne saisit que des heures déjà travaillées.")
                .format(self.date)
            )

    def validate_atelier(self):
        """A group cost center carries no postings of its own — imputing on it
        would put the mechanical cost outside every workshop total."""
        if frappe.db.get_value("Cost Center", self.atelier, "is_group"):
            frappe.throw(
                _("ERR-UTIL-05 : « {0} » est un centre de coûts groupe — "
                  "choisir un atelier terminal (Lait, Cultures - Fourrage, "
                  "Traction…).").format(self.atelier)
            )

    def calculer_cout(self):
        """Snapshot the hourly rate at entry time: changing an Asset's rate
        later must not silently rewrite the cost of past working days."""
        from hmd_agro.hmd_agro.utils.maintenance_utils import cout_horaire

        self.cout_horaire_applique = flt(cout_horaire(self.equipement), 3)
        self.cout_total = flt(flt(self.heures) * flt(self.cout_horaire_applique), 3)
