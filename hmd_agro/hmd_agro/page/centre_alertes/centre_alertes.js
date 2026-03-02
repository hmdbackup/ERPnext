frappe.pages["centre-alertes"].on_page_show = function(wrapper) {
    wrapper_ref = wrapper;
    load_alerts(wrapper);
};

frappe.pages["centre-alertes"].refresh = function(wrapper) {
    load_alerts(wrapper);
};

var wrapper_ref;
var current_filter = "";

function load_alerts(wrapper) {
    var page = wrapper.page || frappe.ui.make_app_page({
        parent: wrapper,
        title: "Centre Alertes",
        single_column: true
    });
    if (!wrapper.page) {
        wrapper.page = page;
    }
    if (!wrapper._buttons_added) {
        wrapper._buttons_added = true;
        page.add_button(__("Generer Alertes"), function() {
            frappe.call({
                method: "hmd_agro.hmd_agro.doctype.alerte.alerte.generate_alerts",
                callback: function() {
                    frappe.show_alert({ message: "Alertes generees", indicator: "green" });
                    load_alerts(wrapper);
                }
            });
        });

        // Hide the default menu (3 dots)
        page.menu.parent().hide();
    }

    frappe.call({
        method: "hmd_agro.hmd_agro.page.centre_alertes.centre_alertes.get_alerts",
        callback: function(r) {
            if (r.message) {
                render_alerts(page, r.message);
            }
        }
    });
}

function render_alerts(page, groups) {
    var container = $(page.body).find(".alert-container");
    if (!container.length) {
        container = $('<div class="alert-container" style="padding: 15px;"></div>').appendTo(page.body);
    }
    container.empty();

    var total = 0;
    for (var key in groups) {
        total += groups[key].alerts.length;
    }

    if (total === 0) {
        container.html(
            '<div style="text-align:center; padding:60px; color:var(--text-muted);">' +
            '<div style="font-size:48px; margin-bottom:10px;">&#10003;</div>' +
            '<h4>Aucune alerte en attente</h4>' +
            '<p>Toutes les alertes ont ete traitees.</p>' +
            '</div>'
        );
        return;
    }

    // Filter bar - Frappe style
    // Filter bar
    var filter_bar = $(
        '<div style="display:flex; align-items:flex-end; gap:15px; margin-bottom:20px; flex-wrap:wrap;">' +
        '<div class="frappe-control" style="max-width:200px;">' +
        '<div class="form-group" style="margin-bottom:0;">' +
        '<label class="control-label">Animal</label>' +
        '<div class="control-input"><input type="text" class="form-control input-xs alert-filter-input" placeholder="Numero ou nom..." value="' + current_filter + '"></div>' +
        '</div>' +
        '</div>' +
        '<div class="frappe-control" style="max-width:150px;">' +
        '<div class="form-group" style="margin-bottom:0;">' +
        '<label class="control-label">Categorie</label>' +
        '<div class="control-input"><select class="form-control input-xs alert-filter-categorie">' +
        '<option value="">Toutes</option>' +
        '<option value="VACHE">VACHE</option>' +
        '<option value="GENISSE">GENISSE</option>' +
        '</select></div>' +
        '</div>' +
        '</div>' +
        '</div>'
    );
    container.append(filter_bar);

    // Sections
    for (var type in groups) {
        var group = groups[type];
        if (group.alerts.length === 0) continue;

        var indicator = get_indicator_color(type);
        var section = $('<div class="alert-group" data-group-type="' + type + '" style="margin-bottom:30px;"></div>');

        var header = $(
            '<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid var(--border-color);">' +
            '<div style="display:flex; align-items:center; gap:8px;">' +
            '<span class="indicator-pill ' + indicator + '" style="font-size:13px; font-weight:600;">' + group.label + ' (' + group.alerts.length + ')</span>' +
            '</div>' +
            '<label style="font-size:12px; cursor:pointer; color:var(--text-muted);">' +
            '<input type="checkbox" class="select-all-group" data-type="' + type + '" style="margin-right:4px;"> Tout selectionner' +
            '</label>' +
            '</div>'
        );
        section.append(header);

        var rows = $('<div class="alert-rows" style="max-height:400px; overflow-y:auto;"></div>');

        // Column headers
        var col_header = $(
            '<div style="display:flex; align-items:center; padding:6px 15px; margin-bottom:4px; color:var(--text-muted); font-size:12px; font-weight:500; border-bottom:1px solid var(--border-color);">' +
            '<div style="width:30px;"></div>' +
            '<div style="min-width:80px;">Animal</div>' +
            '<div style="min-width:90px; padding-left:15px;">Categorie</div>' +
            '<div style="flex:1; padding-left:15px;">Raison</div>' +
            '<div style="min-width:100px; padding-left:15px; cursor:pointer; text-align:right; margin-right:30px;" class="sort-col" data-sort="date" data-type="' + type + '">Date ▼</div>' +
            '<div style="min-width:' + get_actions_width(type) + 'px;"></div>' +
            '</div>'
        );
        rows.append(col_header);

        for (var i = 0; i < group.alerts.length; i++) {
            var alert = group.alerts[i];
            var display_name = (alert.nom_metier || alert.animal);
           var row = $(
                '<div class="alert-row" style="display:flex; align-items:center; padding:10px 15px; margin-bottom:2px; background:var(--fg-color); border:1px solid var(--border-color); border-radius:6px;">' +
                '<input type="checkbox" class="alert-check" data-name="' + alert.name + '" data-type="' + type + '" style="width:30px; flex-shrink:0;">' +
                '<div style="min-width:80px;"><a href="/app/animal/' + alert.animal + '" style="font-weight:600; font-size:14px;">' + display_name + '</a></div>' +
                '<div style="min-width:90px; padding-left:15px;"><span class="indicator-pill whitespace-nowrap ' + get_category_color(alert.categorie) + '" style="font-size:11px;">' + (alert.categorie || '') + '</span></div>' +
                '<div style="flex:1; padding-left:15px; color:var(--text-muted); font-size:13px;">' + (alert.raison || '') + '</div>' +
                '<div style="min-width:100px; padding-left:15px; text-align:right; color:var(--text-muted); font-size:12px; margin-right:30px;">' + (alert.date_alerte || '') + '</div>' +
                '<div class="row-actions" style="display:flex; gap:6px; flex-shrink:0; min-width:' + get_actions_width(type) + 'px; justify-content:flex-end;">' +
                get_row_buttons(type, alert) +
                '</div>' +
                '</div>'
            );
            // Store filter data as attributes
            row.attr("data-filter-name", display_name.toLowerCase());
            row.attr("data-filter-categorie", (alert.categorie || ""));
            row.attr("data-filter-date", (alert.date_alerte || ""));
            rows.append(row);
        }

        // Bulk actions bar - always present but hidden until selection
        var actions_div = $('<div class="group-actions" data-actions-type="' + type + '" style="margin-top:10px; display:none; padding:10px 12px; background:var(--bg-light-gray); border-radius:6px; display:none;">' +
            '<span class="bulk-count text-muted" style="margin-right:10px; font-size:13px;"></span>' +
            get_bulk_buttons(type) +
            '</div>');

        section.append(rows);
        section.append(actions_div);
        container.append(section);
    }

    // === EVENT HANDLERS ===

    // Filters
    function apply_filters() {
        var text_val = container.find(".alert-filter-input").val().toLowerCase().trim();
        var cat_val = container.find(".alert-filter-categorie").val();
        current_filter = text_val;

        container.find(".alert-row").each(function() {
            var name = $(this).attr("data-filter-name") || "";
            var id = $(this).attr("data-filter-id") || "";
            var cat = $(this).attr("data-filter-categorie") || "";

            var text_match = (text_val === "" || name.indexOf(text_val) !== -1 || id.indexOf(text_val) !== -1);
            var cat_match = (cat_val === "" || cat === cat_val);

            if (text_match && cat_match) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    }

    container.off("input", ".alert-filter-input").on("input", ".alert-filter-input", apply_filters);
    container.off("change", ".alert-filter-categorie").on("change", ".alert-filter-categorie", apply_filters);

    if (current_filter) {
        apply_filters();
    }
    // Column sort
    container.off("click", ".sort-col").on("click", ".sort-col", function() {
        var col = $(this);
        var sort_key = col.data("sort");
        var type = col.data("type");
        var rows_container = col.closest(".alert-rows");
        var alert_rows = rows_container.find(".alert-row").toArray();

        // Toggle sort direction
        var asc = col.data("asc") !== true;
        col.data("asc", asc);

        alert_rows.sort(function(a, b) {
            var va, vb;
            if (sort_key === "name") {
                va = $(a).attr("data-filter-name") || "";
                vb = $(b).attr("data-filter-name") || "";
            } else if (sort_key === "categorie") {
                va = $(a).attr("data-filter-categorie") || "";
                vb = $(b).attr("data-filter-categorie") || "";
            } else if (sort_key === "date") {
                va = $(a).attr("data-filter-date") || "";
                vb = $(b).attr("data-filter-date") || "";
            }
            if (va < vb) return asc ? -1 : 1;
            if (va > vb) return asc ? 1 : -1;
            return 0;
        });

        for (var i = 0; i < alert_rows.length; i++) {
            rows_container.append(alert_rows[i]);
        }
    });

    // Select all
    container.off("change", ".select-all-group").on("change", ".select-all-group", function() {
        var type = $(this).data("type");
        var checked = $(this).is(":checked");
        container.find('.alert-check[data-type="' + type + '"]').prop("checked", checked);
        toggle_bulk_actions(container, type);
    });

    // Individual checkbox
    container.off("change", ".alert-check").on("change", ".alert-check", function() {
        var type = $(this).data("type");
        toggle_bulk_actions(container, type);
    });

    // Row action button
    container.off("click", ".btn-alert-action").on("click", ".btn-alert-action", function() {
        var btn = $(this);
        var alert_name = btn.data("alert");
        var action = btn.data("action");

        if (action === "creer_ia") {
            var animal = btn.data("animal");
            frappe.call({
                method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
                args: { alert_name: alert_name, action: "confirmer" },
                callback: function() {
                    frappe.new_doc("Insemination", { animal: animal });
                }
            });
            return;
        }

        if (action === "non_confirmer") {
            frappe.confirm("Marquer cette chaleur comme non confirmee ?", function() {
                do_alert_action(btn, alert_name, action);
            });
            return;
        }

        if (action === "retour_chaleur") {
            frappe.confirm("Confirmer vide ? L'IA sera marquée ÉCHOUÉE.", function() {
                do_alert_action(btn, alert_name, action);
            });
            return;
        }

        if (action === "gestante_confirmee") {
            frappe.confirm("Confirmer pleine ? L'IA sera marquée RÉUSSIE.", function() {
                do_alert_action(btn, alert_name, action);
            });
            return;
        }

        do_alert_action(btn, alert_name, action);
    });

    // Bulk action button
    container.off("click", ".btn-bulk-action").on("click", ".btn-bulk-action", function() {
        var action = $(this).data("action");
        var type = $(this).data("type");
        var checked = container.find('.alert-check[data-type="' + type + '"]:checked');

        if (!checked.length) return;

        var msg = "Appliquer sur " + checked.length + " alerte(s) ?";
        if (action === "retour_chaleur") {
            msg = "Confirmer vide pour " + checked.length + " alerte(s) ? Les IA seront marquées ÉCHOUÉE.";
        }
        if (action === "gestante_confirmee") {
            msg = "Confirmer pleine pour " + checked.length + " alerte(s) ? Les IA seront marquées RÉUSSIE.";
        }

        frappe.confirm(msg, function() {
            var promises = [];
            checked.each(function() {
                var name = $(this).data("name");
                promises.push(
                    frappe.xcall("hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert", {
                        alert_name: name,
                        action: action
                    })
                );
            });

            Promise.all(promises).then(function() {
                frappe.show_alert({ message: checked.length + " alerte(s) traitee(s)", indicator: "green" });
                load_alerts(wrapper_ref);
            });
        });
    });
}

function do_alert_action(btn, alert_name, action) {
    frappe.call({
        method: "hmd_agro.hmd_agro.doctype.alerte.alerte.mark_alert",
        args: { alert_name: alert_name, action: action },
        callback: function() {
            frappe.show_alert({ message: "Alerte traitee", indicator: "green" });
            btn.closest(".alert-row").fadeOut(300, function() {
                $(this).remove();
                load_alerts(wrapper_ref);
            });
        }
    });
}

function get_row_buttons(type, alert) {
    if (type === "CHALEUR_GENISSE" || type === "CHALEUR_POST_VELAGE") {
        return '<button class="btn btn-xs btn-primary btn-alert-action" data-alert="' + alert.name + '" data-action="creer_ia" data-animal="' + alert.animal + '">Creer IA</button>' +
            '<button class="btn btn-xs btn-default btn-alert-action" data-alert="' + alert.name + '" data-action="confirmer">Confirmer</button>' +
            '<button class="btn btn-xs btn-default btn-alert-action" data-alert="' + alert.name + '" data-action="non_confirmer">Non confirmee</button>';
    }
    if (type === "CONFIRMEE") {
        return '<button class="btn btn-xs btn-primary btn-alert-action" data-alert="' + alert.name + '" data-action="creer_ia" data-animal="' + alert.animal + '">Creer IA</button>';
    }
    if (type === "VERIFICATION_J21") {
        return '<button class="btn btn-xs btn-primary btn-alert-action" data-alert="' + alert.name + '" data-action="gestante_probable">À revoir</button>' +
            '<button class="btn btn-xs btn-success btn-alert-action" data-alert="' + alert.name + '" data-action="gestante_confirmee">Pleine</button>' +
            '<button class="btn btn-xs btn-danger btn-alert-action" data-alert="' + alert.name + '" data-action="retour_chaleur">Vide</button>';
    }
    if (type === "VERIFICATION_J50") {
        return '<button class="btn btn-xs btn-primary btn-alert-action" data-alert="' + alert.name + '" data-action="gestante_confirmee">Pleine</button>' +
            '<button class="btn btn-xs btn-danger btn-alert-action" data-alert="' + alert.name + '" data-action="retour_chaleur">Vide</button>';
    }
    return "";
}

function get_bulk_buttons(type) {
    if (type === "CHALEUR_GENISSE" || type === "CHALEUR_POST_VELAGE") {
        return '<button class="btn btn-sm btn-default btn-bulk-action" data-action="confirmer" data-type="' + type + '">Toutes Confirmer</button>' +
            '<button class="btn btn-sm btn-default btn-bulk-action" data-action="non_confirmer" data-type="' + type + '" style="margin-left:6px;">Toutes Non Confirmees</button>';
    }
    if (type === "CONFIRMEE") {
        return '<span class="text-muted" style="font-size:12px;">Selection: utiliser les boutons individuels pour creer les IA</span>';
    }
    if (type === "VERIFICATION_J21") {
        return '<button class="btn btn-sm btn-primary btn-bulk-action" data-action="gestante_probable" data-type="' + type + '">Toutes à revoir</button>' +
            '<button class="btn btn-sm btn-success btn-bulk-action" data-action="gestante_confirmee" data-type="' + type + '" style="margin-left:6px;">Toutes pleine</button>' +
            '<button class="btn btn-sm btn-danger btn-bulk-action" data-action="retour_chaleur" data-type="' + type + '" style="margin-left:6px;">Toutes vide</button>';
    }
    if (type === "VERIFICATION_J50") {
        return '<button class="btn btn-sm btn-primary btn-bulk-action" data-action="gestante_confirmee" data-type="' + type + '">Toutes pleine</button>' +
            '<button class="btn btn-sm btn-danger btn-bulk-action" data-action="retour_chaleur" data-type="' + type + '" style="margin-left:6px;">Toutes vide</button>';
    }
    return "";
}

function get_indicator_color(type) {
    if (type === "CHALEUR_GENISSE" || type === "CHALEUR_POST_VELAGE") return "red";
    if (type === "CONFIRMEE") return "green";
    if (type === "VERIFICATION_J21") return "orange";
    if (type === "VERIFICATION_J50") return "blue";
    return "grey";
}

function get_category_color(categorie) {
    if (categorie === "VACHE") return "blue";
    if (categorie === "GENISSE") return "orange";
    return "grey";
}

function toggle_bulk_actions(container, type) {
    var checked_count = container.find('.alert-check[data-type="' + type + '"]:checked').length;
    var actions_div = container.find('.group-actions[data-actions-type="' + type + '"]');
    if (checked_count > 0) {
        actions_div.show();
        actions_div.find(".bulk-count").text(checked_count + " selectionnee(s)");
    } else {
        actions_div.hide();
    }
}
function get_actions_width(type) {
    if (type === "CHALEUR_GENISSE" || type === "CHALEUR_POST_VELAGE") return 300;
    if (type === "CONFIRMEE") return 80;
    if (type === "VERIFICATION_J21") return 500;
    if (type === "VERIFICATION_J50") return 500;
    return 100;
}