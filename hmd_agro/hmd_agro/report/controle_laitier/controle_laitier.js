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
            label: __("Lots"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Lot", txt);
            },
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        const isTotal = data && data.is_total;

        // Delta color rules apply to BOTH normal and TOTAL rows so the
        // herd-level delta is visually classified (green/orange/red) just
        // like the per-cow deltas.
        if (column.fieldname === "delta" && value != null && value !== "") {
            const pct = Number(value);
            const drop_threshold = (frappe.boot.hmd_config || {}).production_drop_alert_pct || -15;
            let color = "gray";
            let dropBold = false;
            if (pct > 0) color = "green";
            else if (pct < 0) {
                if (pct <= drop_threshold) { color = "red"; dropBold = true; }
                else color = "orange";
            }
            const sign = pct > 0 ? "+" : "";
            const fontWeight = (isTotal || dropBold) ? "font-weight:bold;" : "";
            const bg = isTotal ? "background:#fff3cd;" : "";
            return `<span style="color:${color};${fontWeight}${bg}">${sign}${pct}%</span>`;
        }

        if (isTotal) {
            const formatted = default_formatter(value, row, column, data);
            return `<span style="font-weight:bold; background:#fff3cd;">${formatted}</span>`;
        }
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        if (["total", "moyenne", "moyenne_3j"].includes(column.fieldname)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }
        return default_formatter(value, row, column, data);
    },

    after_datatable_render(datatable) {
        // Freeze the row-number "+" column and nom_metier so they stay visible
        // when the user scrolls right through many date columns.
        hmd_make_sticky_columns(datatable, 2);
    },
};
