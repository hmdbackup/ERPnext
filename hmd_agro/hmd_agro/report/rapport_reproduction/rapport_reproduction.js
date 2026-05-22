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

        // IVV (Reproduction per-cow + Bilan Annuel year-aggregate). Target: 365j.
        if (column.fieldname === "ivv_moyen" || column.fieldname === "dernier_ivv") {
            const n = Number(value);
            if (n >= 450) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n >= 410) return `<span style="color:orange;">${value}</span>`;
        }

        // IVIA1 — Reproduction per-cow (v_ia1) + Bilan Annuel year-aggregate
        // (ivia1_moy). PFE target 70j, > 80j flagged.
        if (column.fieldname === "v_ia1" || column.fieldname === "ivia1_moy") {
            const n = Number(value);
            if (n > 110) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n > 80) return `<span style="color:orange;">${value}</span>`;
        }

        // IVIF — Reproduction per-cow (v_iad) + Bilan Annuel year-aggregate
        // (ivif_moy). PFE target 90j, > 110j flagged.
        if (column.fieldname === "v_iad" || column.fieldname === "ivif_moy") {
            const n = Number(value);
            if (n > 140) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n > 110) return `<span style="color:orange;">${value}</span>`;
        }

        // Taux de Réforme (Bilan Annuel) — PFE 3.2.2.4. Ideal 20-30%.
        // Below 15% = renouvellement insuffisant. Above 35% = excessif.
        if (column.fieldname === "taux_reforme") {
            const n = Number(value);
            if (n < 15 || n > 35) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n < 20 || n > 30) return `<span style="color:orange;">${value}</span>`;
            return `<span style="color:green;font-weight:600">${value}</span>`;
        }

        // % Survie Naissance (Bilan Annuel) — higher is better.
        if (column.fieldname === "taux_survie_naissance") {
            const n = Number(value);
            if (n < 85) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n < 95) return `<span style="color:orange;">${value}</span>`;
            return `<span style="color:green;font-weight:600">${value}</span>`;
        }

        // Persistance de lactation — PFE Chap 3.1.1.3. Optimal 0.85-0.95.
        // Lower = drop-off after pic (nutrition / health issue). Higher = OK.
        // > 1.10 is unusual (production growing post-pic) — flag as suspicious.
        if (column.fieldname === "persistance") {
            const n = Number(value);
            if (n < 0.7 || n > 1.10) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n < 0.85) return `<span style="color:orange;">${value}</span>`;
            return `<span style="color:green;">${value}</span>`;
        }

        // L/C ratio — PFE optimal 2.0 to 2.4. Below 1.5 or above 3.0 = poor.
        if (column.fieldname === "lc") {
            const n = Number(value);
            if (n < 1.5 || n > 3.0) return `<span style="color:red;font-weight:bold;">${value}</span>`;
            if (n < 2.0 || n > 2.4) return `<span style="color:orange;">${value}</span>`;
            return `<span style="color:green;">${value}</span>`;
        }

        // pct_ia_global (Bilan Annuel TRGlobal) — same scale as Performance IA pct_reussite_global
        if (column.fieldname === "pct_ia_global") {
            const pct = Number(value);
            let color = "gray";
            if (pct >= 50) color = "green";
            else if (pct >= 30) color = "orange";
            else if (pct > 0) color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }

        // %3IA+ (Bilan Annuel) — inverse: low is good. < 15 green, < 25 orange, else red.
        if (column.fieldname === "pct_3ia_plus") {
            const pct = Number(value);
            let color = "gray";
            if (value === null || value === undefined || value === "") color = "gray";
            else if (pct < 15) color = "green";
            else if (pct < 25) color = "orange";
            else color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }

        // ─── Performance IA section formatting ───
        // Bold TOTAL row
        if (data && data.mois === "TOTAL") {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }
        // TR1IA — PFE standard > 60% (more stringent than the others).
        if (column.fieldname === "pct_reussite_ia1") {
            const pct = Number(value);
            let color = "gray";
            if (pct >= 60) color = "green";
            else if (pct >= 40) color = "orange";
            else if (pct > 0) color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }
        // % réussite global — target ≥ 50%, < 30 = poor.
        if (column.fieldname === "pct_reussite_global") {
            const pct = Number(value);
            let color = "gray";
            if (pct >= 50) color = "green";
            else if (pct >= 30) color = "orange";
            else if (pct > 0) color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }
        // Other rank reussite (IA2, IA3, IA sup) — secondary, more lenient.
        const reussite_cols = ["pct_reussite_ia2", "pct_reussite_ia3", "pct_reussite_ia_sup"];
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

    after_datatable_render(datatable) {
        // Freeze row-number + first data column. Works across all 3 sections:
        // Reproduction (col 1 = nom_metier), Performance IA (col 1 = mois),
        // Bilan Annuel (col 1 = annee). All have many columns, all benefit.
        hmd_make_sticky_columns(datatable, 2);
    },
};
