// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Semence", {
    quantite_recue: function(frm) {
        if (frm.is_new()) {
            frm.set_value("quantite_restante", frm.doc.quantite_recue);
        }
    }
});