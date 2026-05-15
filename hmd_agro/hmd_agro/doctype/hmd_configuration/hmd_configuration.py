# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


LACTATION_RECALC_FIELDS = ("pic_production_jours", "production_initiale_jours")
TARISSEMENT_RECALC_FIELDS = ("tarissement_window_jours",)
VELAGE_PREVUE_RECALC_FIELDS = ("periode_velage_jours",)


class HMDConfiguration(Document):
    def validate(self):
        self.validate_dim_monotonicity()
        self.validate_tarissement_advance_window()
        self.validate_periode_velage_vs_tarissement()
        self.validate_alerte_lead_cap()

    def validate_periode_velage_vs_tarissement(self):
        """Période de gestation doit être > fenêtre de tarissement.
        Sinon date_tarissement (= velage_prevue - window) précèderait la date d'IA,
        ce qui n'a aucun sens."""
        if (self.periode_velage_jours and self.tarissement_window_jours
                and self.periode_velage_jours <= self.tarissement_window_jours):
            frappe.throw(
                f"Période de gestation ({self.periode_velage_jours} jours) doit être strictement "
                f"supérieure à la fenêtre de tarissement ({self.tarissement_window_jours} jours)."
            )

    def validate_tarissement_advance_window(self):
        """Préavis tarissement doit être ≤ fenêtre de tarissement.
        Sinon l'alerte fire avant que la cow n'entre dans la fenêtre prévue."""
        if (self.tarissement_advance_jours and self.tarissement_window_jours
                and self.tarissement_advance_jours > self.tarissement_window_jours):
            frappe.throw(
                f"Préavis tarissement ({self.tarissement_advance_jours} jours) ne peut pas "
                f"dépasser la fenêtre de tarissement ({self.tarissement_window_jours} jours)."
            )

    def validate_alerte_lead_cap(self):
        """alerte_lead_jours doit rester raisonnable (≤ 7). Au-delà, les reports
        vétérinaires courts (typiquement 7-21j) collapseraient à 'aujourd'hui'."""
        if self.alerte_lead_jours and self.alerte_lead_jours > 7:
            frappe.throw(
                f"Avance d'affichage des alertes ({self.alerte_lead_jours} jours) ne peut pas "
                f"dépasser 7 jours."
            )

    def on_update(self):
        """Queue background recalcs for derived data when relevant config
        fields changed. Operator doesn't wait."""
        if any(self.has_value_changed(f) for f in LACTATION_RECALC_FIELDS):
            frappe.enqueue(
                "hmd_agro.hmd_agro.utils.lactation_recalc.recalculate_all_lactations",
                queue="long",
                timeout=900,
            )
            frappe.msgprint(
                "Recalcul de toutes les lactations programmé en arrière-plan. "
                "Une notification apparaîtra quand terminé."
            )

        if any(self.has_value_changed(f) for f in TARISSEMENT_RECALC_FIELDS):
            frappe.enqueue(
                "hmd_agro.hmd_agro.utils.tarissement_recalc.recalculate_tarissement_dates",
                queue="long",
                timeout=300,
            )
            frappe.msgprint(
                "Recalcul des dates de tarissement (animaux gestants) programmé "
                "en arrière-plan. Une notification apparaîtra quand terminé."
            )

        if any(self.has_value_changed(f) for f in VELAGE_PREVUE_RECALC_FIELDS):
            frappe.enqueue(
                "hmd_agro.hmd_agro.utils.velage_prevue_recalc.recalculate_velage_prevue_dates",
                queue="long",
                timeout=600,
            )
            frappe.msgprint(
                "Recalcul des dates de vêlage prévues et de tarissement (toutes les "
                "vaches gestantes) programmé en arrière-plan. Une notification "
                "apparaîtra quand terminé."
            )

    def validate_dim_monotonicity(self):
        """DIM stage boundaries must be strictly increasing.
        Otherwise the allotement engine misclassifies cows."""
        boundaries = [
            ("dim_fv_max_multi", self.dim_fv_max_multi),
            ("dim_thp_max", self.dim_thp_max),
            ("dim_hp_max", self.dim_hp_max),
            ("dim_mp_max", self.dim_mp_max),
        ]
        for i in range(1, len(boundaries)):
            prev_name, prev_val = boundaries[i - 1]
            cur_name, cur_val = boundaries[i]
            if cur_val is None or prev_val is None:
                continue
            if cur_val <= prev_val:
                frappe.throw(
                    f"Les bornes JL doivent être strictement croissantes : "
                    f"{cur_name} ({cur_val}) doit être > {prev_name} ({prev_val})."
                )
        if self.dim_primipare_cap and self.dim_mp_max and self.dim_primipare_cap > self.dim_mp_max:
            frappe.throw(
                f"Le cap primipare ({self.dim_primipare_cap}) ne peut pas dépasser "
                f"le JL max MP ({self.dim_mp_max})."
            )
