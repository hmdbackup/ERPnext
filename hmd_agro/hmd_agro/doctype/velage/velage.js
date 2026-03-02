// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Velage", {
    refresh(frm) {
        frm.trigger("set_filters");
        frm.trigger("toggle_veau2");

        // Lock identity fields after creation
        if (!frm.is_new()) {
            frm.set_df_property("animal", "read_only", 1);
            frm.set_df_property("date_velage", "read_only", 1);
        }
    },

    nombre_veaux(frm) {
        frm.trigger("toggle_veau2");
    },

    toggle_veau2(frm) {
        let is_jumeaux = frm.doc.nombre_veaux === "2";
        frm.set_df_property("section_veau2", "hidden", !is_jumeaux);

        if (!is_jumeaux) {
            frm.set_value("sexe_veau2", "");
            frm.set_value("vivant_veau2", 0);
            frm.set_value("poids_veau2", null);
        }
    },

    set_filters(frm) {
        frm.set_query("animal", function() {
            return {
                filters: {
                    categorie: ["in", ["VACHE", "GENISSE"]],
                    etat_gestation: "GESTANTE",
                    statut: "ACTIF"
                }
            };
        });
    }
});
