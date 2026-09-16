// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.listview_settings["Intervention Maintenance"] = {
    hide_name_column: true,
    get_indicator(doc) {
        const map = {
            PLANIFIEE: "orange",
            EN_COURS: "blue",
            REALISEE: "green",
            ANNULEE: "red",
        };
        return [__(doc.statut), map[doc.statut] || "gray", "statut,=," + doc.statut];
    },
};
