frappe.listview_settings["Animal"] = {
    hide_name_column: true,
    
    formatters: {
        nom_metier: function(value, df, doc) {
            // If nom_metier is empty, extract last 4 digits from name (identification_tn)
            if (!value && doc.name) {
                value = doc.name.slice(-4);
            }
            return value || "";
        }
    }
};