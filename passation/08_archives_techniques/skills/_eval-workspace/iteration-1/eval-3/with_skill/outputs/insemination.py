# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt
#
# PROPOSED CONTROLLER (evaluation deliverable — NOT applied to the real app).
# Two Insemination changes are implemented here:
#   (1) a GESTANTE cow cannot be inseminated  (RG / CF-ANI-04, ERR-IA-06)
#   (2) on resultat = REUSSIE, auto-compute + store the cow's expected calving
#       date (date_velage_prevue) and her dry-off / tarissement date
#       (date_tarissement)  (RG12)
#
# Only the methods relevant to these two changes are shown in full. The rest of
# the real controller (stock decrement, alerts, on_trash reversal, numero_ia,
# lactation linking, etc.) is unchanged and elided here for clarity; in the
# repo these two changes already live inside the full Insemination class at
# hmd_agro/hmd_agro/doctype/insemination/insemination.py.

import frappe
from frappe.model.document import Document

from hmd_agro.hmd_agro.utils.config import get_config


class Insemination(Document):
    def validate(self):
        # CHANGE 1 runs here, at validate time, before the row is committed.
        self.validate_animal_eligible()
        # ... other validators preserved: validate_no_pending_ia, validate_date_ia,
        #     validate_resultat_transition, lock_identity_fields, set_lactation,
        #     set_numero_ia ...

    def on_update(self):
        # CHANGE 2 runs here: the gestation cascade fires when resultat changes.
        self.update_animal_on_resultat()
        # ... update_lactation_count preserved ...

    # ------------------------------------------------------------------ #
    # CHANGE 1 — a cow that is already pregnant must not be inseminated.
    # ------------------------------------------------------------------ #
    def validate_animal_eligible(self):
        """Only a VACHE or GENISSE that is currently VIDE may be inseminated.

        Rules applied:
          - CF-ANI-04 / CF-LAC-02: only female VACHE/GENISSE are repro-eligible.
          - RG (repro spine, SKILL.md): an IA may only target an animal whose
            `etat_gestation` is VIDE — a GESTANTE animal is already carrying.

        `etat_gestation` is a PROTECTED, hook-managed field (domain invariant 2);
        we only READ it here, never write it.

        The GESTANTE check is gated on `is_new()` ON PURPOSE, and this gate is
        load-bearing — it must not be dropped:
          - On creation, a new IA on a GESTANTE cow is rejected. ✓
          - The `animal` link is immutable after creation (locked by
            `lock_identity_fields`), so an IA can never be re-pointed onto a
            pregnant cow — the only way to target a GESTANTE animal is a NEW IA.
          - Critically, a REUSSIE IA makes ITS OWN animal GESTANTE. The allowed
            REUSSIE → ECHOUEE transition (state-machines.md §3) re-saves this IA
            while the animal is still GESTANTE (the rollback to VIDE happens
            later, in on_update). An UN-gated check would see that GESTANTE state
            and throw ERR-IA-06, self-blocking the transition and making the
            ECHOUEE rollback branch unreachable. Gating on is_new() avoids this.
        """
        if not self.animal:
            return

        categorie, etat_gestation = frappe.db.get_value(
            "Animal", self.animal, ["categorie", "etat_gestation"]
        )

        # Only cows and heifers can be inseminated (males / calves cannot).
        if categorie not in ("VACHE", "GENISSE"):
            frappe.throw(
                "ERR-IA-01: Seules les vaches et génisses peuvent être inséminées."
            )

        # A cow that is already pregnant must not be inseminated.
        # Gated on is_new(): see docstring — a REUSSIE IA sets its own animal
        # GESTANTE, so an ungated check would self-block REUSSIE → ECHOUEE.
        if self.is_new() and etat_gestation == "GESTANTE":
            frappe.throw(
                "ERR-IA-06: Cet animal est déjà gestant. Insémination impossible."
            )

    # ------------------------------------------------------------------ #
    # CHANGE 2 — on a successful result, compute + store calving & dry-off dates.
    # ------------------------------------------------------------------ #
    def update_animal_on_resultat(self):
        """When the IA result changes, sync the mother's gestation state.

        On REUSSIE (RG12 — "une insémination déclarée RÉUSSIE met automatiquement
        l'animal à l'état GESTANTE"):
          - date_velage_prevue = date_ia + periode_velage_jours   (default 280)
          - date_tarissement   = date_velage_prevue - tarissement_window_jours
                                                                   (default 60)
          - etat_gestation     = "GESTANTE"
          - id_ia_fecondante   = this IA

        Both day-windows come from `get_config(...)` (domain invariant 4 — never
        hardcode thresholds). Because date_velage_prevue, date_tarissement,
        id_ia_fecondante and etat_gestation are PROTECTED fields (domain
        invariant 2), we write them only after setting
        `animal.flags.ignore_validate = True`, which is the single sanctioned
        bypass of Animal's protect_* guards (state-machines.md §3). The same
        280/60 math must stay in lockstep with the Velage / Avortement restore
        paths (state-machines.md §4, §6).

        On ECHOUEE, the gestation is rolled back to VIDE and the dates cleared,
        but only if this IA is still the fecundating one — preserved below.
        """
        if not self.has_value_changed("resultat"):
            return

        if self.resultat == "REUSSIE" and self.animal:
            animal = frappe.get_doc("Animal", self.animal)

            # Expected calving date: IA date + gestation length (config-driven).
            periode_velage = get_config("periode_velage_jours", default=280)
            animal.date_velage_prevue = frappe.utils.add_days(
                self.date_ia, periode_velage
            )

            # Dry-off (tarissement) date: calving date minus the dry-off window.
            tarissement_window = get_config("tarissement_window_jours", default=60)
            animal.date_tarissement = frappe.utils.add_days(
                animal.date_velage_prevue, -tarissement_window
            )

            animal.id_ia_fecondante = self.name
            animal.etat_gestation = "GESTANTE"

            # Sanctioned bypass of Animal's protected-field guards.
            animal.flags.ignore_validate = True
            animal.save()

            display_name = animal.nom_metier or self.animal
            frappe.msgprint(
                f"Animal {display_name} mis à jour: Gestation confirmée, "
                f"vêlage prévu le {animal.date_velage_prevue}, "
                f"tarissement prévu le {animal.date_tarissement}."
            )

        elif self.resultat == "ECHOUEE" and self.animal:
            animal = frappe.get_doc("Animal", self.animal)
            # Only roll back if THIS IA is the one that made her gestante.
            if animal.id_ia_fecondante == self.name:
                animal.id_ia_fecondante = None
                animal.date_velage_prevue = None
                animal.date_tarissement = None
                animal.etat_gestation = "VIDE"
                animal.flags.ignore_validate = True
                animal.save()
            # ... alert closure (_close_gestation_alerts, NOUVELLE → NON_CONFIRMEE)
            #     preserved from the real controller ...
