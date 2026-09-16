// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vaccination", {
    refresh(frm) {
        frm.trigger("set_filters");

        // Lock animal field when pre-filled from Animal form or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        // Ensure animal link shows its title after being set via frappe.new_doc
        if (frm.doc.animal && !frm.fields_dict.animal.$input.val()) {
            frm.fields_dict.animal.set_value(frm.doc.animal);
        }
    },

    set_filters(frm) {
        // Only allow active animals
        frm.set_query("animal", function() {
            return {
                filters: {
                    statut: "ACTIF"
                }
            };
        });

        // Only allow Medicaments of type VACCIN in the vaccin dropdown
        frm.set_query("vaccin", function() {
            return {
                filters: {
                    type_medicament: "VACCIN"
                }
            };
        });
    }
});
