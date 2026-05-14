// HMD Configuration form: tab-level "Reset" buttons + post-save reminder.
// Each entry below maps to one tab in the form. Reset buttons appear in the
// form header — visible regardless of which tab is currently active.
const SECTION_DEFAULTS = {
    alertes: {
        chaleur_genisse_age_mois: 14,
        chaleur_post_velage_jours: 45,
        verification_j21_jours: 18,
        verification_j50_jours: 50,
        tarissement_advance_jours: 7,
        velage_advance_jours: 15,
        delvo_advance_jours: 1,
        chaleur_cycle_jours: 21,
        alerte_lead_jours: 2,
    },
    lactation: {
        periode_velage_jours: 280,
        tarissement_window_jours: 60,
        traite_max_litres: 60,
        production_initiale_jours: 60,
        pic_production_jours: 150,
        taux_tb_max_pct: 10,
        taux_tp_max_pct: 10,
    },
    allotement: {
        dim_fv_max_multi: 30,
        dim_thp_max: 120,
        dim_hp_max: 240,
        dim_mp_max: 305,
        dim_primipare_cap: 300,
        last_third_pct: 66.7,
        production_drop_alert_pct: -15,
    },
    bilan_lait: {
        ecart_lait_seuil_negatif_l: 1,
        ecart_lait_seuil_perte_pct: 5,
    },
    seuils_pfe: {
        pfe_lc_optimal_min: 2.0,
        pfe_lc_optimal_max: 2.4,
        pfe_lc_alarm_min: 1.5,
        pfe_lc_alarm_max: 3.0,
        pfe_efficacite_min: 1.4,
        pfe_efficacite_orange_min: 1.0,
        pfe_persistance_min: 0.85,
        pfe_persistance_max: 0.95,
        pfe_persistance_alarm_min: 0.7,
        pfe_persistance_alarm_max: 1.10,
        pfe_3ia_plus_max: 15,
        pfe_3ia_plus_orange_max: 25,
    },
};

const SECTION_LABELS = {
    alertes: __("Alertes"),
    lactation: __("Lactation"),
    allotement: __("Allotement JL"),
    bilan_lait: __("Bilan Lait"),
    seuils_pfe: __("Seuils PFE"),
};

frappe.ui.form.on("HMD Configuration", {
    refresh(frm) {
        // Add a marker class on the form's outermost wrapper. The matching
        // CSS rule lives in public/css/hmd_agro.css — bolds .control-label
        // descendants. frm.$wrapper is the form's outer page wrapper and is
        // a guaranteed ancestor of all field labels.
        if (frm.$wrapper && !frm.$wrapper.hasClass("hmd-config-bold-labels")) {
            frm.$wrapper.addClass("hmd-config-bold-labels");
        }

        Object.keys(SECTION_DEFAULTS).forEach((section) => {
            frm.add_custom_button(
                __("Réinitialiser {0}", [SECTION_LABELS[section]]),
                () => reset_section(frm, section),
                __("Réinitialiser")
            );
        });

        // Listen once per session for the recalc completion events
        if (!frm.__recalc_listeners) {
            frappe.realtime.on("lactation_recalc_done", (data) => {
                _recalc_alert(data, "lactations");
            });
            frappe.realtime.on("tarissement_recalc_done", (data) => {
                _recalc_alert(data, "dates de tarissement");
            });
            frappe.realtime.on("velage_prevue_recalc_done", (data) => {
                _recalc_alert(data, "dates de vêlage prévues");
            });
            frm.__recalc_listeners = true;
        }
    },

    after_save(frm) {
        frappe.show_alert({
            message: __("Configuration enregistrée. Rafraîchir les pages ouvertes (Ctrl+Shift+R) pour appliquer."),
            indicator: "blue"
        }, 7);
    },
});

function _recalc_alert(data, label) {
    const failed_count = (data.failed || []).length;
    if (failed_count) {
        frappe.show_alert({
            message: __("Recalcul {0} terminé : {1} OK, {2} en erreur (voir Error Log).",
                [label, data.success, failed_count]),
            indicator: "orange"
        }, 10);
    } else {
        frappe.show_alert({
            message: __("Recalcul {0} terminé ({1} mis à jour).", [label, data.success]),
            indicator: "green"
        }, 7);
    }
}


function reset_section(frm, section) {
    const defaults = SECTION_DEFAULTS[section];
    const label = SECTION_LABELS[section];
    frappe.confirm(
        __("Réinitialiser les valeurs par défaut de la section <b>{0}</b> ?", [label]),
        () => {
            Object.entries(defaults).forEach(([field, value]) => {
                frm.set_value(field, value);
            });
            frappe.show_alert({
                message: __("Section {0} réinitialisée. Cliquez sur Sauvegarder pour appliquer.", [label]),
                indicator: "orange"
            });
        }
    );
}
