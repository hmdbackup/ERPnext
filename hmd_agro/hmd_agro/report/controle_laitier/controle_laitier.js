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

frappe.query_reports["Controle Laitier"] = {
    onload(report) { add_date_arrows(report, "reference_date"); },
    filters: [
        {
            fieldname: "view_mode",
            label: __("Vue"),
            fieldtype: "Select",
            options: "Conversion\nCL",
            default: "Conversion",
            reqd: 1,
        },
        {
            fieldname: "reference_date",
            label: __("Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -1),
            depends_on: "eval:doc.view_mode == 'Conversion'",
        },
        {
            fieldname: "from_date",
            label: __("Du"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            depends_on: "eval:doc.view_mode == 'CL'",
        },
        {
            fieldname: "to_date",
            label: __("Au"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -1),
            depends_on: "eval:doc.view_mode == 'CL'",
        },
        {
            fieldname: "lot",
            label: __("Lot"),
            fieldtype: "Link",
            options: "Lot",
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        if (["total", "moyenne", "moyenne_3j"].includes(column.fieldname)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }
        if (column.fieldname === "delta") {
            const pct = Number(value);
            const drop_threshold = (frappe.boot.hmd_config || {}).production_drop_alert_pct || -15;
            let color = "gray";
            let bold = false;
            if (pct > 0) {
                color = "green";
            } else if (pct < 0) {
                if (pct <= drop_threshold) { color = "red"; bold = true; }
                else color = "orange";
            }
            const sign = pct > 0 ? "+" : "";
            const style = `color:${color};${bold ? "font-weight:bold;" : ""}`;
            return `<span style="${style}">${sign}${pct}%</span>`;
        }
        return default_formatter(value, row, column, data);
    },

    after_datatable_render(datatable) {
        // Sticky first 2 columns (row number + nom_metier) — useful in CL wide grid.
        if (datatable.wrapper.querySelector(".sticky-col-style")) return;
        const style = document.createElement("style");
        style.className = "sticky-col-style";
        const col0Width = datatable.getColumn(0).width || 40;
        style.textContent = `
            .dt-cell--col-0, .dt-cell--header-0 {
                position: sticky !important; left: 0; z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-0 { z-index: 11; }
            .dt-cell--col-1, .dt-cell--header-1 {
                position: sticky !important; left: ${col0Width}px; z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-1 { z-index: 11; }
        `;
        datatable.wrapper.appendChild(style);
    },
};
