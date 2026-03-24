frappe.listview_settings["Traitement"] = {
    hide_name_column: true,

    onload: function(listview) {
        listview.page.add_button(__("Traitement en Lot"), function() {
            open_bulk_traitement_dialog();
        });
        listview.page.add_button(__("Rafraichir Attente Lait"), function() {
            frappe.call({
                method: "hmd_agro.hmd_agro.doctype.traitement.traitement.refresh_attente_lait",
                callback: function() {
                    frappe.show_alert({ message: "Delais d'attente lait mis a jour", indicator: "green" });
                }
            });
        });
    }
};

function open_bulk_traitement_dialog() {
    var d = new frappe.ui.Dialog({
        title: "Traitement en Lot",
        size: "large",
        fields: [
            {
                fieldname: "section_animals",
                fieldtype: "Section Break",
                label: "Animaux"
            },
            {
                fieldname: "lot",
                fieldtype: "Link",
                label: "Lot",
                options: "Lot",
                description: "Selectionner un lot pour remplir automatiquement les animaux",
                change: function() {
                    var lot = d.get_value("lot");
                    if (!lot) return;
                    frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Animal",
                            filters: { id_lot: lot, statut: "ACTIF" },
                            fields: ["name", "nom_metier"],
                            limit_page_length: 0
                        },
                        callback: function(r) {
                            if (r.message) {
                                var grid = d.fields_dict.animaux.grid;
                                // Remove all existing rows
                                grid.df.data = [];
                                grid.refresh();
                                // Add animals
                                r.message.forEach(function(a) {
                                    grid.df.data.push({
                                        animal: a.name,
                                        nom_metier: a.nom_metier || a.name
                                    });
                                });
                                grid.refresh();
                            }
                        }
                    });
                }
            },
            {
                fieldname: "animaux",
                fieldtype: "Table",
                label: "Animaux",
                cannot_delete_all_rows: 1,
                fields: [
                    {
                        fieldname: "animal",
                        fieldtype: "Link",
                        label: "Animal",
                        options: "Animal",
                        in_list_view: 1,
                        reqd: 1,
                        get_query: function() {
                            return { filters: { statut: "ACTIF" } };
                        }
                    },
                    {
                        fieldname: "nom_metier",
                        fieldtype: "Data",
                        label: "Nom",
                        in_list_view: 1,
                        read_only: 1
                    }
                ],
                data: []
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
            var animaux = values.animaux || [];
            animaux = animaux.filter(function(r) { return r.animal; });

            if (!animaux.length) {
                frappe.msgprint("Veuillez selectionner au moins un animal.");
                return;
            }

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
                    animaux: animaux.map(function(r) { return r.animal; }),
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
                        cur_list.refresh();
                    }
                }
            });
        }
    });

    d.show();
}
