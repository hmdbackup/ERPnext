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

frappe.query_reports["Rapport Mensuel"] = {
    onload(report) {
        add_date_arrows(report, "date");
        if (report.__buttons_added) return;
        report.__buttons_added = true;

        report.page.add_inner_button(__("Importer Excel"), () => open_import_dialog(report));

        // "État du Mois" toggles a hidden effectif_mode filter. Visible only
        // when section == Effectif or Tout (the sections that render the
        // Effectif sub-table). Label flips to reflect current state.
        const update_effectif_btn = () => {
            const section = report.get_filter_value("section") || "Tout";
            const mode = report.get_filter_value("effectif_mode") || "Jour";
            const $btn = report.page.inner_toolbar.find('.btn').filter(function() {
                return /^État/.test($(this).text().trim());
            });
            if (!$btn.length) return;
            if (section === "Effectif" || section === "Tout") {
                $btn.show();
                $btn.text(mode === "Mois" ? __("État du Jour") : __("État du Mois"));
            } else {
                $btn.hide();
            }
        };

        report.page.add_inner_button(__("État du Mois"), () => {
            const current = report.get_filter_value("effectif_mode") || "Jour";
            report.set_filter_value("effectif_mode", current === "Mois" ? "Jour" : "Mois");
            // refresh fires automatically on filter change → wrapper below updates label
        });

        // Hook into refresh so the button label/visibility track filter changes
        // (section toggle, effectif_mode toggle, date navigation).
        const origRefresh = report.refresh.bind(report);
        report.refresh = function () {
            const r = origRefresh();
            setTimeout(update_effectif_btn, 100);
            return r;
        };
        setTimeout(update_effectif_btn, 200);  // initial load
    },

    filters: [
        {
            fieldname: "date",
            label: __("Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "section",
            label: __("Section"),
            fieldtype: "Select",
            options: "Tout\nEffectif\nProduction\nProduction par Lot\nAlimentation\nIndicateurs",
            default: "Tout"
        },
        {
            fieldname: "granularite",
            label: __("Granularité"),
            fieldtype: "Select",
            options: "Quinzaine\nQuotidien\nHebdomadaire",
            default: "Quinzaine",
            depends_on: "eval:['Alimentation','Production','Tout'].includes(doc.section)"
        },
        {
            fieldname: "periode",
            label: __("Période"),
            fieldtype: "Select",
            options: "Jour\nHebdomadaire",
            default: "Jour",
            depends_on: "eval:['Production par Lot','Tout'].includes(doc.section)"
        },
        {
            fieldname: "effectif_mode",
            label: __("Effectif Mode"),
            fieldtype: "Select",
            options: "Jour\nMois",
            default: "Jour",
            hidden: 1
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        let html = default_formatter(value, row, column, data);
        if (data && (data.is_total || data.is_header)) {
            html = `<b>${html}</b>`;
        }
        // Indicateurs (KPI) table — color the `valeur` cell when the row carries
        // an `indicator` (Green/Orange/Red) computed by _indicateurs against a
        // PFE-recommended threshold.
        if (column.fieldname === "valeur" && data && data.indicator) {
            const colors = {Green: "green", Orange: "orange", Red: "red"};
            const c = colors[data.indicator];
            if (c) {
                const w = data.indicator === "Red" ? "font-weight:bold;" : "font-weight:600;";
                html = `<span style="color:${c};${w}">${html}</span>`;
            }
        }
        // Indicateurs Δ % — color by `direction`: "up" means higher-better,
        // "down" means lower-better. Improving trend → green, deteriorating → red.
        // No color when direction is None (absolutes / range KPIs where sign
        // alone isn't meaningful) or delta is null/zero.
        if (column.fieldname === "delta_pct" && data && data.direction && data.delta_pct) {
            const improving = (data.direction === "up" && data.delta_pct > 0) ||
                              (data.direction === "down" && data.delta_pct < 0);
            const c = improving ? "green" : "red";
            html = `<span style="color:${c};font-weight:600;">${html}</span>`;
        }
        // Period-row tinting (Production Q1/Q2/Sn, Lot weekly Sem. préc./act.)
        // — applied to every cell when the row carries a `tint` flag set by
        // the Python builder. Same color palette as the Alimentation column
        // tints below. Skip the leading label cell so the row label stays
        // unstyled (avoids a colored "Q1" vs colored values mismatch).
        if (data && data.tint && column.fieldname !== "jour") {
            const tints = {
                orange: "rgba(220, 150, 50, 0.22)",
                green: "rgba(60, 160, 90, 0.20)",
            };
            const bg = tints[data.tint];
            if (bg) {
                html = `<span style="display:block; margin:-6px -10px; padding:6px 10px; background:${bg};">${html}</span>`;
            }
        }
        // Alimentation column tinting — applied only to rows from _alimentation
        // (rows with an "aliment" key). The block-level span with negative
        // margins extends the color to the cell edges. Implemented in the
        // formatter (not via injected CSS) because the global zebra has higher
        // specificity than any per-cell selector we can write here.
        if (data && data.aliment !== undefined) {
            const fn = column.fieldname || "";
            let tint = null;
            if (fn === "moy_jour_mois")                            tint = "rgba(60, 160, 90, 0.20)";
            else if (fn.startsWith("moy_") || fn === "delta_q2_q1") tint = "rgba(220, 150, 50, 0.22)";
            else if (fn !== "aliment" && fn !== "ms_pct")          tint = "rgba(70, 130, 180, 0.18)";
            if (tint) {
                html = `<span style="display:block; margin:-6px -10px; padding:6px 10px; background:${tint};">${html}</span>`;
            }
        }
        return html;
    }
};


function open_import_dialog(report) {
    const d = new frappe.ui.Dialog({
        title: __("Importer un Rapport Mensuel"),
        fields: [
            {
                fieldname: "info",
                fieldtype: "HTML",
                options: `<div style="color:var(--text-muted);font-size:13px;margin-bottom:10px;">
                    Importer un fichier Excel au format Rapport Mensuel (1 onglet par jour, nommés "01".."31").
                    L'année et le mois sont détectés automatiquement après chargement du fichier.
                </div>`
            },
            { fieldname: "file_url", fieldtype: "Attach", label: __("Fichier Excel"), reqd: 1,
              options: { restrictions: { allowed_file_types: [".xlsx", ".xls"] } },
              change() { detect_and_fill(d); } },
            { fieldname: "annee", fieldtype: "Int", label: __("Année"), reqd: 1 },
            { fieldname: "mois", fieldtype: "Int", label: __("Mois"), reqd: 1,
              description: __("1 = Janvier, 12 = Décembre") }
        ],
        primary_action_label: __("Importer"),
        primary_action(values) {
            if (values.mois < 1 || values.mois > 12) {
                frappe.msgprint(__("Le mois doit être entre 1 et 12."));
                return;
            }
            d.disable_primary_action();
            frappe.call({
                method: "hmd_agro.hmd_agro.utils.import_rapport.import_workbook",
                args: { file_url: values.file_url, annee: values.annee, mois: values.mois },
                freeze: true,
                freeze_message: __("Import en cours..."),
                callback(r) {
                    d.hide();
                    const res = r.message || {};
                    const imported = (res.imported || []).length;
                    const skipped = (res.skipped || []).length;
                    frappe.show_alert({
                        message: __("{0} jour(s) importé(s), {1} ignoré(s).", [imported, skipped]),
                        indicator: imported ? "green" : "orange"
                    });
                    report.refresh();
                },
                error() { d.enable_primary_action(); }
            });
        }
    });
    d.show();
}


function detect_and_fill(d) {
    const file_url = d.get_value("file_url");
    if (!file_url) return;
    frappe.call({
        method: "hmd_agro.hmd_agro.utils.import_rapport.detect_period",
        args: { file_url: file_url },
        callback(r) {
            const m = r.message;
            if (!m) {
                frappe.show_alert({ message: __("Aucune date détectée dans le fichier."), indicator: "orange" });
                return;
            }
            d.set_value("annee", m.annee);
            d.set_value("mois", m.mois);
            frappe.show_alert({
                message: __("Période détectée : {0}/{1} ({2}/{3} feuilles)", [m.mois, m.annee, m.confidence, m.total_sheets]),
                indicator: "green"
            });
        }
    });
}
