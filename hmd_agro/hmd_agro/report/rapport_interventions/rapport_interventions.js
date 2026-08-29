// SCRUM-11 — Rapport Interventions : le parc et ses interventions.
// Mêmes filtres de période que le Rapport Performance (qui détient
// `period_bounds`, « Année » = du 1er janvier à la date choisie), plus deux
// filtres facultatifs Équipement / Atelier.
// La coloration reprend le formatter maison : `indicator` est calculé côté
// Python, jamais dans le JS —
//   Parc      : PRÊT (Green), EN ATTENTE DE MAINTENANCE (Orange), EN PANNE (Red)
//   Préventif : À VENIR (Blue), EN RETARD (Red)
//   Rapprochement : écart nul (Green) ou non (Orange)

const HMD_COULEURS_INDICATEUR = {Green: "green", Orange: "orange", Red: "red", Blue: "blue"};

// Colonnes qui portent la couleur de leur ligne : le coût (rapprochement), le
// type (état du parc, échéance) et, pour une échéance dépassée, la date —
// c'est la colonne que l'œil cherche.
function hmd_colonne_coloree(fieldname, indicator) {
    if (fieldname === "cout" || fieldname === "type") return true;
    return fieldname === "date" && indicator === "Red";
}

frappe.query_reports["Rapport Interventions"] = {
    filters: [
        {
            fieldname: "periode",
            label: __("Période"),
            fieldtype: "Select",
            options: "Jour\nSemaine\nQuinzaine\nMois\nAnnée",
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
        // Même palette/graisses que le Rapport Performance : le rouge est gras,
        // le reste semi-gras.
        const couleur = data && HMD_COULEURS_INDICATEUR[data.indicator];
        if (couleur && hmd_colonne_coloree(column.fieldname, data.indicator)) {
            const graisse = data.indicator === "Red" ? "font-weight:bold;" : "font-weight:600;";
            html = `<span style="color:${couleur};${graisse}">${html}</span>`;
        }
        return html;
    }
};
