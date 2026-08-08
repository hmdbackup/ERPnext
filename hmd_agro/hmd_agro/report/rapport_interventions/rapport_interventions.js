// SCRUM-11 — Rapport Interventions : interventions mécaniques de la période.
// Mêmes filtres de période que le Rapport Performance (qui détient
// `period_bounds`), plus deux filtres facultatifs Équipement / Atelier.
// La coloration reprend le formatter maison : `indicator` est calculé côté
// Python (Red = échéance préventive en retard, Orange = écart de
// rapprochement non nul), jamais dans le JS.

frappe.query_reports["Rapport Interventions"] = {
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
        },
        {
            fieldname: "equipement",
            label: __("Équipement"),
            fieldtype: "Link",
            options: "Asset"
        },
        {
            fieldname: "atelier",
            label: __("Atelier"),
            fieldtype: "Link",
            options: "Cost Center"
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        let html = default_formatter(value, row, column, data);
        if (column.fieldname === "section") {
            html = `<b>${html}</b>`;
        }
        // Coloration du coût — même palette/graisses que le Rapport Performance.
        if (column.fieldname === "cout" && data && data.indicator) {
            const colors = {Green: "green", Orange: "orange", Red: "red"};
            const c = colors[data.indicator];
            if (c) {
                const w = data.indicator === "Red" ? "font-weight:bold;" : "font-weight:600;";
                html = `<span style="color:${c};${w}">${html}</span>`;
            }
        }
        // Une échéance préventive dépassée se voit sur sa date, pas seulement
        // sur son type : c'est la colonne que l'œil cherche.
        if (column.fieldname === "date" && data && data.indicator === "Red") {
            html = `<span style="color:red;font-weight:bold;">${html}</span>`;
        }
        return html;
    }
};
