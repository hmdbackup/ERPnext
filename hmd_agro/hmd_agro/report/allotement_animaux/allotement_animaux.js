frappe.query_reports["Allotement Animaux Base"] = {
    filters: [
        {
            fieldname: "reference_date",
            label: __("Date de reference (J)"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "lot",
            label: __("Lot"),
            fieldtype: "Link",
            options: "Lot"
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }

        if (column.fieldname === "delta_j_vs_j_1") {
            const pct = Number(value);
            let color = "gray";
            if (pct > 0) {
                color = "green";
            } else if (pct < 0) {
                color = pct <= -15 ? "red" : "orange";
            }
            const sign = pct > 0 ? "+" : "";
            return `<span style="color:${color};font-weight:600">${sign}${pct}%</span>`;
        }

        if (["j_2", "j_1", "j", "moyenne_3j"].includes(column.fieldname)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }

        return default_formatter(value, row, column, data);
    }
};
