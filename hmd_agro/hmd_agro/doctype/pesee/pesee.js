// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pesee", {
    refresh(frm) {
        // Lock animal field when pre-filled from Animal form or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }
    }
});
