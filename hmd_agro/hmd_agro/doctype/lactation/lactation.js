// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lactation", {
    refresh(frm) {
        frm.trigger("set_filters");
        frm.trigger("filter_statut_options");

        if (["TARIE", "INTERROMPUE"].includes(frm.doc.statut)) {
            frm.set_intro(__("Lactation clôturée — modification limitée."), "yellow");
        }
    },

    set_filters(frm) {
        frm.set_query("animal", function() {
            return {
                filters: {
                    categorie: ["in", ["VACHE", "GENISSE"]],
                    sexe: "F",
                    statut: "ACTIF"
                }
            };
        });

        frm.set_query("velage_debut", function() {
            return {
                filters: {
                    animal: frm.doc.animal
                }
            };
        });
    },

    filter_statut_options(frm) {
        /**
         * Restrict the "statut" dropdown to valid transitions only.
         * EN_COURS    → TARIE, INTERROMPUE
         * TARIE       → (final)
         * INTERROMPUE → (final)
         * New doc     → EN_COURS only
         */
        if (frm.is_new()) {
            frm.set_df_property("statut", "options", "EN_COURS");
            frm.set_df_property("statut", "read_only", 1);
            return;
        }

        const current = frm.doc.statut;
        const transitions = {
            "EN_COURS":    ["EN_COURS", "TARIE", "INTERROMPUE"],
            "TARIE":       ["TARIE"],
            "INTERROMPUE": ["INTERROMPUE"],
        };

        const allowed = transitions[current] || [current];
        frm.set_df_property("statut", "options", allowed.join("\n"));
        frm.set_df_property("statut", "read_only", allowed.length <= 1 ? 1 : 0);

        if (["TARIE", "INTERROMPUE"].includes(current)) {
            frm.set_df_property("statut", "description", __("État final — aucune transition possible."));
        }
    }
});
