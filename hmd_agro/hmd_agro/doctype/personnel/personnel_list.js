frappe.listview_settings["Personnel"] = {
    onload: function(listview) {
        listview.page.add_action_item(__("Attribuer une prime"), function() {
            var selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__("Veuillez sélectionner au moins un salarié."));
                return;
            }

            var d = new frappe.ui.Dialog({
                title: __("Attribuer une prime — {0} salarié(s)", [selected.length]),
                fields: [
                    {
                        fieldname: "salaries_info",
                        fieldtype: "HTML",
                        options: "<p>" + selected.map(function(p) {
                            return "<b>" + (p.nom_complet || p.name) + "</b>";
                        }).join(", ") + "</p>"
                    },
                    {
                        fieldname: "montant",
                        fieldtype: "Currency",
                        label: __("Montant (TND)"),
                        default: 50,
                        reqd: 1
                    },
                    {
                        fieldname: "periode",
                        fieldtype: "Data",
                        label: __("Période (AAAA-MM)"),
                        default: frappe.datetime.get_today().slice(0, 7),
                        reqd: 1
                    },
                    {
                        fieldname: "motif",
                        fieldtype: "Data",
                        label: __("Motif")
                    }
                ],
                primary_action_label: __("Attribuer"),
                primary_action: function(values) {
                    d.disable_primary_action();
                    frappe.call({
                        method: "hmd_agro.hmd_agro.doctype.personnel.personnel.attribuer_prime_bulk",
                        args: {
                            personnels: selected.map(function(p) { return p.name; }),
                            montant: values.montant,
                            periode: values.periode,
                            motif: values.motif || ""
                        },
                        freeze: true,
                        freeze_message: __("Création des primes..."),
                        callback: function(r) {
                            if (r.message) {
                                d.hide();
                                var res = r.message;
                                var msg = __("{0} prime(s) créée(s)", [res.created]);
                                if (res.errors && res.errors.length) {
                                    msg += ", " + __("{0} erreur(s)", [res.errors.length]);
                                    frappe.show_alert({ message: msg, indicator: "orange" });
                                    var err_html = res.errors.map(function(e) {
                                        return "<li><b>" + e.personnel + "</b>: " + e.error + "</li>";
                                    }).join("");
                                    frappe.msgprint("<ul>" + err_html + "</ul>", __("Erreurs"));
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
