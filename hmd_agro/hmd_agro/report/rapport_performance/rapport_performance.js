// Rapport Performance (Phase 4) — synthèse hebdo / mensuelle consolidée.
// La coloration de la colonne `valeur` reprend le formatter des Indicateurs
// du Rapport Mensuel (indicator Green/Orange/Red calculé côté Python contre
// les seuils PFE de HMD Configuration) ; `valeur` reste un Float natif pour
// que l'export CSV/Excel alimente le template Excel sans nettoyage.

frappe.query_reports["Rapport Performance"] = {
    filters: [
        {
            fieldname: "periode",
            label: __("Période"),
            fieldtype: "Select",
            options: "Jour\nSemaine\nQuinzaine\nMois",
            default: "Mois",
            reqd: 1
        },
        {
            fieldname: "date",
            label: __("Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        let html = default_formatter(value, row, column, data);
        // KPI coloring — same palette/weights as Rapport Mensuel Indicateurs.
        if (column.fieldname === "valeur" && data && data.indicator) {
            const colors = {Green: "green", Orange: "orange", Red: "red"};
            const c = colors[data.indicator];
            if (c) {
                const w = data.indicator === "Red" ? "font-weight:bold;" : "font-weight:600;";
                html = `<span style="color:${c};${w}">${html}</span>`;
            }
        }
        if (column.fieldname === "section") {
            html = `<b>${html}</b>`;
        }
        return html;
    }
};
