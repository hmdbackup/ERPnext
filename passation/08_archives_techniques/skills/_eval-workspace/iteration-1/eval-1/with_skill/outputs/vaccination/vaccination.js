// Copyright (c) 2026, HMD AGRO and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vaccination", {
    setup(frm) {
        // Only active animals can be vaccinated.
        frm.set_query("animal", function () {
            return {
                filters: {
                    statut: "ACTIF",
                },
            };
        });

        // "vaccine product" = a Medicament of type VACCIN — reuse the existing
        // product master rather than a free-text field. Mirrors validate_vaccin().
        frm.set_query("vaccin", function () {
            return {
                filters: {
                    type_medicament: "VACCIN",
                },
            };
        });
    },
});
