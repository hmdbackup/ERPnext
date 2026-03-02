frappe.listview_settings["Alerte"] = {
    hide_name_column: true,
    default_filters: {
        "statut": "NOUVELLE"
    },

    onload: function(listview) {
        listview.page.add_inner_button(__("Générer Alertes"), function() {
            frappe.call({
                method: "hmd_agro.hmd_agro.doctype.alerte.alerte.generate_alerts",
                callback: function() {
                    listview.refresh();
                    frappe.show_alert({
                        message: __("Alertes générées"),
                        indicator: "green"
                    });
                }
            });
        });
    },

    get_indicator: function(doc) {
        if (doc.statut === "NOUVELLE") {
            return [__("NOUVELLE"), "red", "statut,=,NOUVELLE"];
        } else if (doc.statut === "CONFIRMEE") {
            return [__("CONFIRMEE"), "green", "statut,=,CONFIRMEE"];
        } else if (doc.statut === "NON_CONFIRMEE") {
            return [__("NON CONFIRMEE"), "orange", "statut,=,NON_CONFIRMEE"];
        } else if (doc.statut === "RETOUR_CHALEUR") {
            return [__("RETOUR CHALEUR"), "orange", "statut,=,RETOUR_CHALEUR"];
        } else if (doc.statut === "GESTANTE_PROBABLE") {
            return [__("GESTANTE PROBABLE"), "blue", "statut,=,GESTANTE_PROBABLE"];
        }else if (doc.statut === "GESTANTE_CONFIRMEE") {
            return [__("GESTANTE CONFIRMEE"), "green", "statut,=,GESTANTE_CONFIRMEE"];
        }

    }
};