frappe.listview_settings["Animal"] = {
    hide_name_column: true,

    formatters: {
        nom_metier: function(value, df, doc) {
            if (!value && doc.name) {
                value = doc.name.slice(-4);
            }
            return value || "";
        }
    },

    onload: function(listview) {
        listview.page.add_action_item(__("Changer de Lot"), function() {
            var selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint("Veuillez selectionner au moins un animal.");
                return;
            }

            var d = new frappe.ui.Dialog({
                title: "Changer de Lot — " + selected.length + " animal(aux)",
                fields: [
                    {
                        fieldname: "lot",
                        fieldtype: "Link",
                        label: "Nouveau Lot",
                        options: "Lot",
                        reqd: 1
                    }
                ],
                primary_action_label: "Appliquer",
                primary_action: function(values) {
                    d.disable_primary_action();
                    frappe.call({
                        method: "frappe.client.bulk_update",
                        args: {
                            docs: JSON.stringify(selected.map(function(item) {
                                return { doctype: "Animal", docname: item.name, id_lot: values.lot };
                            }))
                        },
                        callback: function(r) {
                            d.hide();
                            if (r.message && r.message.failed_docs && r.message.failed_docs.length) {
                                frappe.msgprint(r.message.failed_docs.length + " erreur(s) lors du changement.");
                            } else {
                                frappe.show_alert({
                                    message: selected.length + " animal(aux) deplace(s) vers " + values.lot,
                                    indicator: "green"
                                });
                            }
                            listview.clear_checked_items();
                            listview.refresh();
                        }
                    });
                }
            });
            d.show();
        });

        listview.page.add_action_item(__("Traitement en Lot"), function() {
            var selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint("Veuillez selectionner au moins un animal.");
                return;
            }

            var d = new frappe.ui.Dialog({
                title: "Traitement en Lot — " + selected.length + " animal(aux)",
                size: "large",
                fields: [
                    {
                        fieldname: "animaux_info",
                        fieldtype: "HTML",
                        options: "<p>" + selected.map(function(a) {
                            return "<b>" + (a.nom_metier || a.name.slice(-4)) + "</b>";
                        }).join(", ") + "</p>"
                    },
                    {
                        fieldname: "section_traitement",
                        fieldtype: "Section Break",
                        label: "Traitement"
                    },
                    {
                        fieldname: "date_traitement",
                        fieldtype: "Date",
                        label: "Date",
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        fieldname: "type_traitement",
                        fieldtype: "Select",
                        label: "Type",
                        options: "TRAITEMENT_MEDICAL\nPARAGE",
                        default: "TRAITEMENT_MEDICAL",
                        reqd: 1,
                        change: function() {
                            var is_medical = d.get_value("type_traitement") === "TRAITEMENT_MEDICAL";
                            d.set_df_property("medicaments", "hidden", !is_medical);
                        }
                    },
                    {
                        fieldname: "cb_traitement",
                        fieldtype: "Column Break"
                    },
                    {
                        fieldname: "praticien",
                        fieldtype: "Data",
                        label: "Praticien"
                    },
                    {
                        fieldname: "observations",
                        fieldtype: "Small Text",
                        label: "Diagnostic / Raison"
                    },
                    {
                        fieldname: "section_medicaments",
                        fieldtype: "Section Break",
                        label: "Medicaments"
                    },
                    {
                        fieldname: "medicaments",
                        fieldtype: "Table",
                        label: "Medicaments",
                        fields: [
                            {
                                fieldname: "medicament",
                                fieldtype: "Link",
                                label: "Medicament",
                                options: "Medicament",
                                in_list_view: 1,
                                reqd: 1
                            },
                            {
                                fieldname: "dose",
                                fieldtype: "Float",
                                label: "Dose",
                                in_list_view: 1
                            },
                            {
                                fieldname: "unite_dose",
                                fieldtype: "Select",
                                label: "Unite",
                                options: "ml\nmg\ng\ncomprime\ndose",
                                in_list_view: 1
                            },
                            {
                                fieldname: "voie_administration",
                                fieldtype: "Select",
                                label: "Voie",
                                options: "ORALE\nINJECTABLE_IM\nSC\nIV\nTOPIQUE\nINTRAMAMMAIRE",
                                in_list_view: 1
                            }
                        ],
                        data: []
                    }
                ],
                primary_action_label: "Appliquer",
                primary_action: function(values) {
                    var medicaments = [];
                    if (values.type_traitement === "TRAITEMENT_MEDICAL") {
                        medicaments = (values.medicaments || []).filter(function(r) { return r.medicament; });
                        if (!medicaments.length) {
                            frappe.msgprint("Un traitement medical doit contenir au moins un medicament.");
                            return;
                        }
                    }

                    d.disable_primary_action();

                    frappe.call({
                        method: "hmd_agro.hmd_agro.doctype.traitement.traitement.create_bulk_traitement",
                        args: {
                            animaux: selected.map(function(a) { return a.name; }),
                            date_traitement: values.date_traitement,
                            type_traitement: values.type_traitement,
                            praticien: values.praticien || "",
                            observations: values.observations || "",
                            medicaments: medicaments
                        },
                        freeze: true,
                        freeze_message: "Creation des traitements...",
                        callback: function(r) {
                            if (r.message) {
                                d.hide();
                                var res = r.message;
                                var msg = res.created + " traitement(s) cree(s)";
                                if (res.errors && res.errors.length) {
                                    msg += ", " + res.errors.length + " erreur(s)";
                                    frappe.show_alert({ message: msg, indicator: "orange" });
                                    var err_html = res.errors.map(function(e) {
                                        return "<li><b>" + e.animal + "</b>: " + e.error + "</li>";
                                    }).join("");
                                    frappe.msgprint("<ul>" + err_html + "</ul>", "Erreurs");
                                } else {
                                    frappe.show_alert({ message: msg, indicator: "green" });
                                }
                                listview.clear_checked_items();
                                listview.refresh();
                            }
                        }
                    });
                }
            });
            d.show();
        });
    }
};