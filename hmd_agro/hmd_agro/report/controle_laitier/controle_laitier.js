frappe.query_reports["Controle Laitier"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("Du"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("Au"),
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
    ]
};
