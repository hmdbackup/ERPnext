// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Traite", {
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