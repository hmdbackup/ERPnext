frappe.ui.form.on("Alerte", {
    refresh(frm) {
        var is_chaleur = ["CHALEUR_GENISSE", "CHALEUR_POST_VELAGE"].includes(frm.doc.type_alerte);
        var is_j21 = frm.doc.type_alerte === "VERIFICATION_J21";
        var is_j50 = frm.doc.type_alerte === "VERIFICATION_J50";

        // CHALEUR buttons
        if (is_chaleur) {
            if (frm.doc.statut === "NOUVELLE") {
                frm.add_custom_button(__("Confirmer Chaleur"), function() {
                    frappe.call({
                        method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                        args: { alert_name: frm.doc.name, action: "confirmer" },
                        callback: function() {
                            frm.reload_doc();
                            frappe.show_alert({ message: __("Chaleur confirmée"), indicator: "green" });
                        }
                    });
                }, __("Actions"));

                frm.add_custom_button(__("Non Confirmée"), function() {
                    frappe.call({
                        method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                        args: { alert_name: frm.doc.name, action: "non_confirmer" },
                        callback: function() {
                            frm.reload_doc();
                            frappe.show_alert({ message: __("Chaleur non confirmée"), indicator: "orange" });
                        }
                    });
                }, __("Actions"));
            }

            if (frm.doc.statut === "CONFIRMEE") {
                frm.add_custom_button(__("Créer Insémination"), function() {
                    frappe.route_options = { animal: frm.doc.animal };
                    frappe.new_doc("Insemination");
                }, __("Actions"));
            }
        }

        // J+21 buttons
        if (is_j21 && frm.doc.statut === "NOUVELLE") {
            frm.add_custom_button(__("Retour Chaleur"), function() {
                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                    args: { alert_name: frm.doc.name, action: "retour_chaleur" },
                    callback: function() {
                        frm.reload_doc();
                        frappe.show_alert({ message: __("Retour chaleur — IA échouée"), indicator: "orange" });
                    }
                });
            }, __("Actions"));

            frm.add_custom_button(__("Gestante Probable"), function() {
                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                    args: { alert_name: frm.doc.name, action: "gestante_probable" },
                    callback: function() {
                        frm.reload_doc();
                        frappe.show_alert({ message: __("Gestation probable — vérification J+50 programmée"), indicator: "blue" });
                    }
                });
            }, __("Actions"));

            frm.add_custom_button(__("Gestante Confirmée"), function() {
                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                    args: { alert_name: frm.doc.name, action: "gestante_confirmee" },
                    callback: function() {
                        frm.reload_doc();
                        frappe.show_alert({ message: __("Gestation confirmée!"), indicator: "green" });
                    }
                });
            }, __("Actions"));
        }

        // J+50 buttons
        if (is_j50 && frm.doc.statut === "NOUVELLE") {
            frm.add_custom_button(__("Retour Chaleur"), function() {
                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                    args: { alert_name: frm.doc.name, action: "retour_chaleur" },
                    callback: function() {
                        frm.reload_doc();
                        frappe.show_alert({ message: __("Retour chaleur — IA échouée"), indicator: "orange" });
                    }
                });
            }, __("Actions"));

            frm.add_custom_button(__("Gestante Confirmée"), function() {
                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                    args: { alert_name: frm.doc.name, action: "gestante_confirmee" },
                    callback: function() {
                        frm.reload_doc();
                        frappe.show_alert({ message: __("Gestation confirmée!"), indicator: "green" });
                    }
                });
            }, __("Actions"));
        }

        // After retour chaleur on J+21 or J+50, offer to create IA
        if ((is_j21 || is_j50) && frm.doc.statut === "RETOUR_CHALEUR") {
            frm.add_custom_button(__("Créer Insémination"), function() {
                frappe.route_options = { animal: frm.doc.animal };
                frappe.new_doc("Insemination");
            }, __("Actions"));
        }

        // Intro messages
        if (frm.doc.statut === "NOUVELLE" && is_chaleur) {
            frm.set_intro(__("Alerte en attente — vérifier la chaleur"), "red");
        } else if (frm.doc.statut === "NOUVELLE" && is_j21) {
            frm.set_intro(__("Vérification J+21 — vérifier retour chaleur"), "red");
        } else if (frm.doc.statut === "NOUVELLE" && is_j50) {
            frm.set_intro(__("Vérification J+50 — confirmer la gestation"), "red");
        } else if (frm.doc.statut === "CONFIRMEE") {
            frm.set_intro(__("Chaleur confirmée — prête pour insémination"), "green");
        } else if (frm.doc.statut === "NON_CONFIRMEE") {
            frm.set_intro(__("Chaleur non confirmée"), "orange");
        } else if (frm.doc.statut === "RETOUR_CHALEUR") {
            frm.set_intro(__("Retour chaleur détecté — insémination échouée"), "orange");
        } else if (frm.doc.statut === "GESTANTE_PROBABLE") {
            frm.set_intro(__("Gestation probable — en attente de confirmation J+50"), "blue");
        } else if (frm.doc.statut === "GESTANTE_CONFIRMEE") {
            frm.set_intro(__("Gestation confirmée"), "green");
        }
    }
});