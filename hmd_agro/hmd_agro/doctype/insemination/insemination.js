// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Insemination", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Insemination", {
    refresh(frm) {
        frm.trigger("set_filters");
        frm.trigger("filter_resultat_options");

        // Lock animal field when pre-filled from Animal form or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        // Ensure animal link shows nom_metier (title) after being set via frappe.new_doc
        if (frm.doc.animal && !frm.fields_dict.animal.$input.val()) {
            frm.fields_dict.animal.set_value(frm.doc.animal);
        }
    },

    set_filters(frm) {
        // Only show VACHE/GENISSE in animal dropdown
        frm.set_query("animal", function() {
            return {
                filters: {
                    categorie: ["in", ["VACHE", "GENISSE"]],
                    statut: "ACTIF"
                }
            };
        });
    },

    filter_resultat_options(frm) {
        /**
         * Restrict the "résultat" dropdown to valid transitions only.
         * EN_ATTENTE → REUSSIE, ECHOUEE
         * REUSSIE   → ECHOUEE  (abortion / re-evaluation)
         * ECHOUEE   → (final — no change allowed)
         * New doc   → EN_ATTENTE only
         */
        if (frm.is_new()) {
            frm.set_df_property("resultat", "options", "EN_ATTENTE");
            frm.set_df_property("resultat", "read_only", 1);
            return;
        }

        const current = frm.doc.resultat;
        const transitions = {
            "EN_ATTENTE": ["EN_ATTENTE", "REUSSIE", "ECHOUEE"],
            "REUSSIE":    ["REUSSIE", "ECHOUEE"],
            "ECHOUEE":    ["ECHOUEE"],
        };

        const allowed = transitions[current] || [current];
        frm.set_df_property("resultat", "options", allowed.join("\n"));
        frm.set_df_property("resultat", "read_only", allowed.length <= 1 ? 1 : 0);

        if (current === "ECHOUEE") {
            frm.set_intro(__("État final — aucune transition possible."), "grey");
        }
    }
});