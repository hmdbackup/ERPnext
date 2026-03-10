frappe.ui.form.on("Traitement", {
    refresh(frm) {
        frm.trigger("toggle_medicaments_visibility");

        // Lock animal field when pre-filled from Animal form or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        // Ensure animal link shows nom_metier (title) after being set via frappe.new_doc
        if (frm.doc.animal && frm.fields_dict.animal.$input && !frm.fields_dict.animal.$input.val()) {
            frm.fields_dict.animal.set_value(frm.doc.animal);
        }
    },

    type_traitement(frm) {
        frm.trigger("toggle_medicaments_visibility");
        if (frm.doc.type_traitement === "PARAGE") {
            frm.clear_table("medicaments");
            frm.refresh_field("medicaments");
        }
    },

    toggle_medicaments_visibility(frm) {
        frm.toggle_display("section_medicaments",
            frm.doc.type_traitement === "TRAITEMENT_MEDICAL");
    }
});

frappe.ui.form.on("Traitement Medicale", {
    medicament(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.medicament) {
            frappe.db.get_value("Medicament", row.medicament, "delai_attente_lait",
                function(r) {
                    if (r) {
                        frappe.model.set_value(cdt, cdn, "delai_attente_lait", r.delai_attente_lait);
                        if (frm.doc.date_traitement && r.delai_attente_lait) {
                            let fin = frappe.datetime.add_days(frm.doc.date_traitement, r.delai_attente_lait);
                            frappe.model.set_value(cdt, cdn, "date_fin_attente_lait", fin);
                        }
                    }
                }
            );
        }
    }
});
