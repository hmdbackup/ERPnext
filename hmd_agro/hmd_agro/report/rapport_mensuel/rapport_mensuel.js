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
        if (report.__import_btn_added) return;
        report.__import_btn_added = true;

        report.page.add_inner_button(__("Importer Excel"), () => open_import_dialog(report));
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
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        if (data && (data.is_total || data.is_header)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }
        return default_formatter(value, row, column, data);
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
