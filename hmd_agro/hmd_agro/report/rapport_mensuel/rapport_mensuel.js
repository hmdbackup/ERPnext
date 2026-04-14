frappe.query_reports["Rapport Mensuel"] = {
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

        // Bold TOTAL and section header rows
        if (data && (data.is_total || data.is_header)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }

        return default_formatter(value, row, column, data);
    }
};
