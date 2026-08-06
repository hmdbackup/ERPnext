// TASK B3 — Tableau d'amortissement consolidé (rapport « Tableau Amortissement »).
// Filtres : catégorie d'actif (optionnel) et inclusion des actifs sortis
// (coché par défaut — la date de sortie doit rester visible). Les lignes
// d'actifs sortis sont grisées pour se distinguer du parc en service.

frappe.query_reports["Tableau Amortissement"] = {
    filters: [
        {
            fieldname: "asset_category",
            label: __("Catégorie"),
            fieldtype: "Link",
            options: "Asset Category",
        },
        {
            fieldname: "inclure_sortis",
            label: __("Inclure les actifs sortis"),
            fieldtype: "Check",
            default: 1,
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        let html = default_formatter(value, row, column, data);

        if (data && data.date_sortie) {
            html = `<span style="color:#8d99a6">${html}</span>`;
        } else if (column.fieldname === "statut" && data && data.statut === "AMORTI") {
            html = `<span style="color:orange;font-weight:600">${html}</span>`;
        }

        return html;
    },
};
