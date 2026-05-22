// List view bulk action: assign ONE ration to MANY lots in one click.
// Mirrors the pattern in animal_list.js ("Changer de Lot") — check items in
// the list, click the action, fill a small dialog, submit.

frappe.listview_settings["Ration"] = {
    onload: function(listview) {
        listview.page.add_action_item(__("Affecter aux lots"), function() {
            const selected = listview.get_checked_items();
            if (selected.length !== 1) {
                frappe.msgprint({
                    title: __("Sélection invalide"),
                    message: __("Veuillez sélectionner exactement une ration à affecter."),
                    indicator: "orange"
                });
                return;
            }
            const ration = selected[0];
            if (!ration.active) {
                frappe.msgprint({
                    title: __("Ration inactive"),
                    message: __("La ration {0} n'est pas active. Activez-la avant de l'affecter à des lots.", [ration.name]),
                    indicator: "orange"
                });
                return;
            }
            open_assign_dialog(listview, ration.name);
        });
    }
};

function open_assign_dialog(listview, ration) {
    // Fetch active lots first so we can render them as checkboxes in the dialog.
    frappe.db.get_list("Lot", {
        filters: { actif: 1 },
        fields: ["name", "id_ration_actuelle"],
        limit: 0,
        order_by: "name asc"
    }).then(lots => {
        if (!lots.length) {
            frappe.msgprint(__("Aucun lot actif disponible."));
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Affecter '{0}' aux lots", [ration]),
            fields: [
                {
                    fieldname: "intro_html",
                    fieldtype: "HTML",
                    options: `<p class="text-muted small">${__(
                        "Cochez les lots à affecter. Pour chaque lot, l'épisode actuel sera fermé et un nouvel épisode commencera à la date choisie."
                    )}</p>`
                },
                {
                    fieldname: "lots",
                    fieldtype: "MultiCheck",
                    label: __("Lots actifs"),
                    options: lots.map(l => ({
                        value: l.name,
                        label: l.id_ration_actuelle
                            ? `${l.name}  <span class="text-muted">(${l.id_ration_actuelle})</span>`
                            : l.name
                    })),
                    columns: 2,
                    reqd: 1
                },
                {
                    fieldname: "date_debut",
                    fieldtype: "Date",
                    label: __("Date de début"),
                    default: frappe.datetime.get_today(),
                    reqd: 1,
                    description: __("La date doit être aujourd'hui ou dans le passé. Pas de date future en v1.")
                }
            ],
            primary_action_label: __("Affecter"),
            primary_action(values) {
                if (!values.lots || !values.lots.length) {
                    frappe.msgprint(__("Veuillez cocher au moins un lot."));
                    return;
                }
                dialog.disable_primary_action();
                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.ration.ration.affecter_aux_lots",
                    args: {
                        ration: ration,
                        lots: values.lots,
                        date_debut: values.date_debut
                    },
                    freeze: true,
                    freeze_message: __("Affectation en cours..."),
                    callback: (r) => {
                        if (!r.message) {
                            dialog.enable_primary_action();
                            return;
                        }
                        const { affected, skipped } = r.message;
                        let msg = __("{0} lot(s) affecté(s)", [affected]);
                        if (skipped) {
                            msg += " " + __("({0} déjà sur cette ration)", [skipped]);
                        }
                        frappe.show_alert({ message: msg, indicator: "green" });
                        dialog.hide();
                        listview.clear_checked_items();
                        listview.refresh();
                    },
                    error: () => {
                        dialog.enable_primary_action();
                    }
                });
            }
        });
        dialog.show();
    });
}
