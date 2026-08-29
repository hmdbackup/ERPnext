// Rapport Performance (Phase 4) — synthèse jour / semaine / quinzaine / mois /
// année consolidée, avec colonnes comparatives (maquettes 24/08 et 26/08/2026).
// La coloration de la colonne `valeur` reprend le formatter des Indicateurs
// du Rapport Periodique (indicator Green/Orange/Red calculé côté Python contre
// les seuils PFE de HMD Configuration) ; `valeur` et `precedent` restent des
// Float natifs pour que l'export CSV/Excel alimente le template Excel sans
// nettoyage. Une case sans valeur s'affiche « – », jamais 0 (réunion 26/08).

const HMD_PERF_TIRET = "–";
const HMD_PERF_COLONNES_VALEUR = ["valeur", "precedent"];

frappe.query_reports["Rapport Performance"] = {
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
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        const vide = value == null || value === "";
        if (HMD_PERF_COLONNES_VALEUR.includes(column.fieldname) && vide) {
            return HMD_PERF_TIRET;
        }
        if (column.fieldname === "ecart_pct") {
            return vide ? HMD_PERF_TIRET : hmd_perf_ecart_signe(value);
        }
        if (vide) {
            return default_formatter(value, row, column, data);
        }
        let html = default_formatter(value, row, column, data);
        // KPI coloring — same palette/weights as Rapport Periodique Indicateurs.
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

// « +12,5 % » : l'écart est toujours signé, le lecteur ne doit pas deviner le sens.
function hmd_perf_ecart_signe(value) {
    const signe = value > 0 ? "+" : "";
    const nombre = frappe.format(value, {fieldtype: "Float", precision: 1});
    return `<span class="text-right">${signe}${nombre} %</span>`;
}
