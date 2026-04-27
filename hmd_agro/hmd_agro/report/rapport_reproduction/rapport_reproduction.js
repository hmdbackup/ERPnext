// Reusable: add prev/next day arrows next to a Date filter (Saisie Traite pattern).
function add_date_arrows(report, fieldname) {
    setTimeout(function() {
        var f = report.get_filter(fieldname);
        if (!f || !f.$wrapper || f.$wrapper.find(".date-nav-arrows").length) return;
        var arrows = $('<div class="date-nav-arrows" style="display:inline-block; margin-left:6px; vertical-align:middle;">' +
            '<button class="btn btn-default btn-xs" title="Jour précédent" style="padding:2px 8px;">&lsaquo;</button>' +
            '<button class="btn btn-default btn-xs" title="Jour suivant" style="padding:2px 8px; margin-left:4px;">&rsaquo;</button>' +
            '</div>');
        f.$wrapper.append(arrows);
        var btns = arrows.find("button");
        $(btns[0]).on("click", function() {
            var cur = f.get_value();
            if (cur) { report.set_filter_value(fieldname, frappe.datetime.add_days(cur, -1)); }
        });
        $(btns[1]).on("click", function() {
            var cur = f.get_value();
            if (cur) { report.set_filter_value(fieldname, frappe.datetime.add_days(cur, 1)); }
        });
    }, 100);
}

frappe.query_reports["Rapport Reproduction"] = {
    onload(report) { add_date_arrows(report, "date"); },
    filters: [
        {
            fieldname: "date",
            label: __("Date du rapport"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: "section",
            label: __("Section"),
            fieldtype: "Select",
            options: "Reproduction\nPerformance IA\nBilan Annuel",
            default: "Reproduction",
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }

        // Statut Reproduction colour cues
        if (column.fieldname === "statut_repro") {
            const v = String(value);
            let color = "gray";
            if (v === "Gestante") color = "green";
            else if (v.startsWith("Gestante (proche")) color = "orange";
            else if (v === "Tarie") color = "blue";
            else if (v.startsWith("Vide >90j")) color = "red";
            else if (v.startsWith("Vide")) color = "darkorange";
            return `<span style="color:${color};font-weight:500;">${value}</span>`;
        }

        // État Gestation
        if (column.fieldname === "etat_gestation") {
            const c = value === "GESTANTE" ? "green" : "gray";
            return `<span style="color:${c};">${value}</span>`;
        }

        // État Lactation
        if (column.fieldname === "etat_lactation") {
            const c = value === "EN_PRODUCTION" ? "green" : (value === "TARIE" ? "blue" : "gray");
            return `<span style="color:${c};">${value}</span>`;
        }

        // Résultat IA
        if (column.fieldname === "resultat_derniere_ia") {
            const map = {REUSSIE: "green", ECHOUEE: "red", EN_ATTENTE: "orange"};
            const c = map[value] || "gray";
            return `<span style="color:${c};">${value}</span>`;
        }

        // IVV >= 410 days = warning
        if (column.fieldname === "ivv_moyen" || column.fieldname === "dernier_ivv") {
            const n = Number(value);
            if (n >= 450) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n >= 410) return `<span style="color:orange;">${value}</span>`;
        }

        // ─── Performance IA section formatting ───
        // Bold TOTAL row
        if (data && data.mois === "TOTAL") {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }
        // % réussite — green ≥50, orange ≥40, red >0
        const reussite_cols = ["pct_reussite_ia1", "pct_reussite_ia2", "pct_reussite_ia3",
                               "pct_reussite_ia_sup", "pct_reussite_global"];
        if (reussite_cols.includes(column.fieldname)) {
            const pct = Number(value);
            let color = "gray";
            if (pct >= 50) color = "green";
            else if (pct >= 40) color = "orange";
            else if (pct > 0) color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }
        // % perte (inverse: low=good)
        const perte_cols = ["pct_perte_velles", "pct_perte_veaux"];
        if (perte_cols.includes(column.fieldname)) {
            const pct = Number(value);
            let color = "gray";
            if (pct === 0) color = "green";
            else if (pct <= 10) color = "orange";
            else color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }

        return default_formatter(value, row, column, data);
    },
};
