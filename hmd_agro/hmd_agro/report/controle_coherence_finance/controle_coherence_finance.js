// FIN-S70 — Contrôle de cohérence finance (rapport « Controle Coherence Finance »).
// Colore la colonne `statut` (OK / ALERTE / ERREUR) et met en évidence la
// ligne de synthèse, pour qu'un coup d'œil suffise sur une base restaurée.

frappe.query_reports["Controle Coherence Finance"] = {
    filters: [
        {
            fieldname: "date_debut",
            label: __("Du"),
            fieldtype: "Date",
            default: frappe.datetime.month_start(),
            reqd: 1,
        },
        {
            fieldname: "date_fin",
            label: __("Au"),
            fieldtype: "Date",
            default: frappe.datetime.month_end(),
            reqd: 1,
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        let html = default_formatter(value, row, column, data);

        if (data && data.domaine === "SYNTHÈSE") {
            html = `<b>${html}</b>`;
        }

        if (column.fieldname === "statut" && data && data.indicator) {
            const colors = { Green: "green", Orange: "orange", Red: "red" };
            const c = colors[data.indicator];
            if (c) {
                const w = data.indicator === "Green" ? "font-weight:600;" : "font-weight:bold;";
                html = `<span style="color:${c};${w}">${html}</span>`;
            }
        }

        return html;
    },

    onload(report) {
        if (report.__hmd_buttons) return;
        report.__hmd_buttons = true;

        // Raccourci de cadrage : l'exercice entier, pour valider une
        // restauration de production d'un seul coup.
        report.page.add_inner_button(__("Exercice complet"), () => {
            const annee = (report.get_filter_value("date_fin") || frappe.datetime.get_today())
                .slice(0, 4);
            report.set_filter_value("date_debut", `${annee}-01-01`);
            report.set_filter_value("date_fin", `${annee}-12-31`);
        });
    },
};
