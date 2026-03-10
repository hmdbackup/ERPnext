// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Traite", {
    refresh(frm) {
        // Lock animal field when pre-filled from Animal form or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        // Filter: only ACTIF animals with active lactation and no milk withdrawal
        frm.set_query("animal", function() {
            return {
                filters: {
                    statut: "ACTIF",
                    etat_lactation: "EN_PRODUCTION",
                    attente_lait_active: 0
                }
            };
        });
    },

    animal: function(frm) {
        if (frm.doc.animal) {
            // Auto-fetch lactation
            frappe.db.get_value("Lactation", {
                "animal": frm.doc.animal,
                "statut": "EN_COURS"
            }, "name", function(r) {
                if (r && r.name) {
                    frm.set_value("lactation", r.name);
                }
            });
        }
    }
});