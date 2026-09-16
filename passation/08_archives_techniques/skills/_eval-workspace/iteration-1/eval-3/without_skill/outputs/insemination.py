# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days

from hmd_agro.hmd_agro.utils.config import get_config


class Insemination(Document):
    def validate(self):
        # (1) A pregnant cow must not be inseminated.
        self.validate_animal_not_pregnant()

    def on_update(self):
        # (2) When the result becomes REUSSIE, compute & store the cow's
        #     expected calving date and her dry-off (tarissement) date.
        self.sync_gestation_dates_on_result()

    # ------------------------------------------------------------------ #
    # (1) Guard: a pregnant cow cannot be inseminated
    # ------------------------------------------------------------------ #
    def validate_animal_not_pregnant(self):
        """Block insemination of an already-pregnant animal.

        The animal's gestation status is held on Animal.etat_gestation
        ("GESTANTE" / "VIDE"). We only block on *new* inseminations: an
        existing IA record is allowed to be re-saved/edited even though its
        own success has, by design, flipped the animal to GESTANTE.
        """
        if not self.animal:
            return
        if not self.is_new():
            return

        etat_gestation = frappe.db.get_value("Animal", self.animal, "etat_gestation")
        if etat_gestation == "GESTANTE":
            frappe.throw(
                "ERR-IA-06: Cet animal est déjà gestant. Insémination impossible."
            )

    # ------------------------------------------------------------------ #
    # (2) On successful result: compute calving + dry-off dates
    # ------------------------------------------------------------------ #
    def sync_gestation_dates_on_result(self):
        """Maintain the cow's gestation projection when the IA result moves.

        On REUSSIE (success):
            date_velage_prevue = date_ia + periode_velage_jours   (default 280)
            date_tarissement   = date_velage_prevue - tarissement_window_jours
                                                                  (default 60)
            etat_gestation     = "GESTANTE"
            id_ia_fecondante   = this IA

        On ECHOUEE (failure): the projection is rolled back so a wrong/
        aborted result does not leave the cow stuck as GESTANTE — but only
        if THIS IA is the one that fecundated her.

        Runs only when `resultat` actually changed, so re-saving an
        unrelated field never re-triggers the side effects.
        """
        if not self.animal or not self.has_value_changed("resultat"):
            return

        if self.resultat == "REUSSIE":
            self._mark_pregnant()
        elif self.resultat == "ECHOUEE":
            self._rollback_pregnancy()

    def _mark_pregnant(self):
        periode_velage = get_config("periode_velage_jours", default=280)
        tarissement_window = get_config("tarissement_window_jours", default=60)

        date_velage_prevue = add_days(self.date_ia, periode_velage)
        date_tarissement = add_days(date_velage_prevue, -tarissement_window)

        animal = frappe.get_doc("Animal", self.animal)
        animal.id_ia_fecondante = self.name
        animal.date_velage_prevue = date_velage_prevue
        animal.date_tarissement = date_tarissement
        animal.etat_gestation = "GESTANTE"
        # The Animal controller's own validation is not relevant to this
        # system-driven update; skip it to avoid spurious cross-checks.
        animal.flags.ignore_validate = True
        animal.save()

        display_name = animal.nom_metier or self.animal
        frappe.msgprint(
            f"Animal {display_name} mis à jour: gestation confirmée, "
            f"vêlage prévu le {date_velage_prevue}, "
            f"tarissement le {date_tarissement}."
        )

    def _rollback_pregnancy(self):
        animal = frappe.get_doc("Animal", self.animal)
        # Only undo if this very IA is the fecundating one — otherwise we'd
        # wipe a valid gestation triggered by a different insemination.
        if animal.id_ia_fecondante != self.name:
            return

        animal.id_ia_fecondante = None
        animal.date_velage_prevue = None
        animal.date_tarissement = None
        animal.etat_gestation = "VIDE"
        animal.flags.ignore_validate = True
        animal.save()

        display_name = animal.nom_metier or self.animal
        frappe.msgprint(f"Animal {display_name}: IA échouée, gestation annulée.")
