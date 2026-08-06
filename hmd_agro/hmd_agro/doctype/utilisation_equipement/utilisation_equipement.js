// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Utilisation Equipement", {
    setup(frm) {
        // Only submitted assets can carry working hours (ERR-UTIL-03), and a
        // group cost center can't be imputed (ERR-UTIL-05): filter both away
        // instead of letting the user hit the error on save.
        frm.set_query("equipement", () => ({ filters: { docstatus: 1 } }));
        frm.set_query("atelier", () => ({ filters: { is_group: 0 } }));
    },

    equipement(frm) {
        // Default the workshop to the one the equipment is already booked on.
        if (!frm.doc.equipement || frm.doc.atelier) {
            return;
        }
        frappe.db.get_value("Asset", frm.doc.equipement, "cost_center")
            .then((r) => {
                if (r && r.message && r.message.cost_center) {
                    frm.set_value("atelier", r.message.cost_center);
                }
            });
    }
});
