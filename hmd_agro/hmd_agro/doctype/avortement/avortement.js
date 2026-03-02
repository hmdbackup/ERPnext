// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Avortement", {
    refresh(frm) {
        // Lock identity fields after creation
        if (!frm.is_new()) {
            frm.set_df_property("animal", "read_only", 1);
            frm.set_df_property("date_avortement", "read_only", 1);
        }

        // Lock animal when pre-filled from Animal form
        if (frm.is_new() && frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        // Filter: only GESTANTE animals
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
