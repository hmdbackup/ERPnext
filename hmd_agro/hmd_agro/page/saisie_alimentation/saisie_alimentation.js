frappe.pages["saisie-alimentation"].on_page_show = function(wrapper) {
    load_saisie_alimentation(wrapper);
};

frappe.pages["saisie-alimentation"].refresh = function(wrapper) {
    load_saisie_alimentation(wrapper);
};

function load_saisie_alimentation(wrapper) {
    var page = wrapper.page || frappe.ui.make_app_page({
        parent: wrapper,
        title: "Saisie Alimentation",
        single_column: true
    });
    if (!wrapper.page) {
        wrapper.page = page;
    }

    if (!wrapper._sa_initialized) {
        wrapper._sa_initialized = true;

        wrapper._sa_date_input = frappe.ui.form.make_control({
            parent: page.page_actions,
            df: {
                fieldtype: "Date",
                fieldname: "saisie_date",
                default: frappe.datetime.add_days(frappe.datetime.get_today(), -1)
            },
            render_input: true
        });
        wrapper._sa_date_input.set_value(
            frappe.datetime.add_days(frappe.datetime.get_today(), -1)
        );
        wrapper._sa_date_input.$wrapper.css({
            "display": "inline-block",
            "margin-left": "15px",
            "width": "160px",
            "vertical-align": "middle"
        });
        wrapper._sa_date_input.$wrapper.appendTo(page.page_actions);
        wrapper._sa_date_input.$input.on("change", function() {
            fetch_and_render(page, wrapper._sa_date_input.get_value());
        });

        var arrow_container = $(
            '<div style="display:inline-block; vertical-align:middle; margin-left:8px;"></div>'
        );
        var btn_prev = $(
            '<button class="btn btn-default btn-xs" title="Jour précédent" ' +
            'style="padding:2px 8px;">&lsaquo;</button>'
        );
        var btn_next = $(
            '<button class="btn btn-default btn-xs" title="Jour suivant" ' +
            'style="padding:2px 8px; margin-left:4px;">&rsaquo;</button>'
        );
        arrow_container.append(btn_prev).append(btn_next).appendTo(page.page_actions);
        btn_prev.on("click", function() {
            var cur = wrapper._sa_date_input.get_value();
            if (cur) {
                var p = frappe.datetime.add_days(cur, -1);
                wrapper._sa_date_input.set_value(p);
                fetch_and_render(page, p);
            }
        });
        btn_next.on("click", function() {
            var cur = wrapper._sa_date_input.get_value();
            if (cur) {
                var n = frappe.datetime.add_days(cur, 1);
                wrapper._sa_date_input.set_value(n);
                fetch_and_render(page, n);
            }
        });

        page.set_primary_action(__("Enregistrer"), function() {
            save_all(page, wrapper._sa_date_input.get_value());
        }, "octicon octicon-check");

        page.menu.parent().hide();
    }

    fetch_and_render(page, wrapper._sa_date_input.get_value());
}

function fetch_and_render(page, date) {
    if (!date) return;
    frappe.call({
        method: "hmd_agro.hmd_agro.page.saisie_alimentation.saisie_alimentation.get_aliment_state",
        args: { date: date },
        callback: function(r) {
            render_state(page, r.message || { date: date, aliments: [] });
        }
    });
}

function render_state(page, state) {
    var container = $(page.body).find(".sa-container");
    if (!container.length) {
        container = $('<div class="sa-container" style="padding:15px;"></div>')
            .appendTo(page.body);
    }
    container.empty();

    var aliments = state.aliments || [];
    if (!aliments.length) {
        container.html(
            '<div style="text-align:center; padding:60px; color:var(--text-muted);">' +
            '<h4>Aucune distribution prévue</h4>' +
            '<p>Aucun Stock Entry RATION_DIST n\'a été posté pour cette date. ' +
            'Le générateur quotidien tourne à minuit pour la veille — vérifiez ' +
            'que la date sélectionnée est antérieure à aujourd\'hui.</p>' +
            '</div>'
        );
        return;
    }

    var help = $(
        '<div style="margin-bottom:15px; padding:10px 14px; background:var(--bg-color); ' +
        'border-left:3px solid var(--blue-500); border-radius:4px; font-size:13px; ' +
        'color:var(--text-muted);">' +
        'Saisissez le total <strong>réellement distribué</strong> par aliment (en kg). ' +
        'Le système répartit proportionnellement la différence entre tous les lots ' +
        'qui consomment cet aliment, puis met à jour stock, coûts et rapports. ' +
        'Cliquez sur la flèche pour voir la répartition par lot.' +
        '</div>'
    );
    container.append(help);

    var table = $(
        '<table class="table table-bordered" style="background:var(--fg-color);">' +
        '<thead>' +
        '<tr style="background:var(--bg-color);">' +
        '<th style="width:30px;"></th>' +
        '<th>Aliment</th>' +
        '<th style="width:160px; text-align:right;">Théorique (kg)</th>' +
        '<th style="width:170px; text-align:center;">Réel (kg)</th>' +
        '<th style="width:80px; text-align:center;">État</th>' +
        '</tr>' +
        '</thead>' +
        '<tbody></tbody>' +
        '<tfoot>' +
        '<tr style="background:var(--bg-color); font-weight:bold;">' +
        '<td></td>' +
        '<td style="text-align:right;">TOTAUX</td>' +
        '<td class="sa-total-theo" style="text-align:right;">0</td>' +
        '<td class="sa-total-actual" style="text-align:center;">0</td>' +
        '<td></td>' +
        '</tr>' +
        '</tfoot>' +
        '</table>'
    );
    var tbody = table.find("tbody");

    for (var i = 0; i < aliments.length; i++) {
        var A = aliments[i];
        var state_pill = A.has_correction
            ? '<span class="indicator-pill orange" style="font-size:11px;">Corrigé</span>'
            : '<span class="indicator-pill green" style="font-size:11px;">Théorique</span>';
        var actual_value = A.has_correction ? A.actual_total : A.theoretical_total;

        var main_row = $(
            '<tr class="sa-aliment-row" data-item="' + A.item_code + '" ' +
            'data-theo="' + A.theoretical_total + '">' +
            '<td style="text-align:center; cursor:pointer;" class="sa-expand">' +
            '<span class="sa-caret">&#9656;</span></td>' +
            '<td><strong>' + frappe.utils.escape_html(A.aliment) + '</strong> ' +
            '<span style="color:var(--text-muted); font-size:11px;">' +
            frappe.utils.escape_html(A.item_code) + '</span></td>' +
            '<td class="sa-theo" style="text-align:right;">' +
            A.theoretical_total.toFixed(2) + '</td>' +
            '<td style="text-align:center;">' +
            '<input type="number" min="0" step="0.1" class="form-control input-xs sa-actual-input" ' +
            'value="' + actual_value + '" ' +
            'data-original="' + actual_value + '" ' +
            'style="width:120px; text-align:center; display:inline-block;">' +
            '</td>' +
            '<td class="sa-state" style="text-align:center;">' + state_pill + '</td>' +
            '</tr>'
        );
        tbody.append(main_row);

        // Drill-down row (initially hidden)
        var drill_inner = '<table style="width:100%; margin:0;">' +
            '<thead style="font-size:11px; color:var(--text-muted);">' +
            '<tr><th>Lot</th><th style="text-align:right;">Théorique</th>' +
            '<th style="text-align:right;">Projeté (réel × part)</th></tr></thead><tbody>';
        var theoSum = A.theoretical_total || 1;
        (A.lots || []).forEach(function(L) {
            var share = L.qty_theoretical / theoSum;
            drill_inner += '<tr><td>' + frappe.utils.escape_html(L.lot) + '</td>' +
                '<td style="text-align:right;">' + L.qty_theoretical.toFixed(2) + '</td>' +
                '<td class="sa-projected" data-share="' + share + '" ' +
                'style="text-align:right;">' + L.qty_actual.toFixed(2) + '</td></tr>';
        });
        drill_inner += '</tbody></table>';
        var drill_row = $(
            '<tr class="sa-drill" data-item="' + A.item_code + '" style="display:none;">' +
            '<td></td>' +
            '<td colspan="4" style="background:var(--bg-color); padding:6px 12px;">' +
            drill_inner + '</td></tr>'
        );
        tbody.append(drill_row);
    }

    container.append(table);

    container.off("click", ".sa-expand").on("click", ".sa-expand", function() {
        var main = $(this).closest("tr");
        var item = main.data("item");
        var drill = container.find('.sa-drill[data-item="' + item + '"]');
        var caret = $(this).find(".sa-caret");
        if (drill.is(":visible")) {
            drill.hide();
            caret.html("&#9656;");
        } else {
            drill.show();
            caret.html("&#9662;");
        }
    });

    container.off("input", ".sa-actual-input").on("input", ".sa-actual-input", function() {
        update_row($(this).closest("tr"), container);
        update_totals(container);
    });
    container.off("keydown", ".sa-actual-input").on("keydown", ".sa-actual-input", function(e) {
        if (e.key === "-" || e.key === "e") { e.preventDefault(); }
        if (e.key === "Enter") {
            e.preventDefault();
            var inputs = container.find(".sa-actual-input");
            var idx = inputs.index(this);
            if (idx < inputs.length - 1) inputs.eq(idx + 1).focus().select();
        }
    });

    container.find("tbody tr.sa-aliment-row").each(function() {
        update_row($(this), container);
    });
    update_totals(container);
}

function update_row(row, container) {
    var theo = parseFloat(row.data("theo")) || 0;
    var actual = parseFloat(row.find(".sa-actual-input").val()) || 0;
    var item = row.data("item");

    // Refresh drill-down projected quantities live so user sees how their
    // entry will distribute across lots before saving.
    container.find('.sa-drill[data-item="' + item + '"] .sa-projected').each(function() {
        var share = parseFloat($(this).data("share")) || 0;
        $(this).text((actual * share).toFixed(2));
    });
}

function update_totals(container) {
    var t_theo = 0, t_actual = 0;
    container.find("tbody tr.sa-aliment-row").each(function() {
        var row = $(this);
        var theo = parseFloat(row.data("theo")) || 0;
        var actual = parseFloat(row.find(".sa-actual-input").val()) || 0;
        t_theo += theo;
        t_actual += actual;
    });
    container.find(".sa-total-theo").text(t_theo.toFixed(2));
    container.find(".sa-total-actual").text(t_actual.toFixed(2));
}

function save_all(page, date) {
    if (!date) {
        frappe.msgprint(__("Sélectionnez une date d'abord."));
        return;
    }
    var container = $(page.body).find(".sa-container");
    var to_save = [];
    container.find("tbody tr.sa-aliment-row").each(function() {
        var row = $(this);
        var item = row.data("item");
        var input = row.find(".sa-actual-input");
        var actual = parseFloat(input.val());
        var original = parseFloat(input.data("original"));
        if (!isNaN(actual) && Math.abs(actual - original) > 0.001) {
            to_save.push({ item_code: item, actual_total: actual });
        }
    });

    if (!to_save.length) {
        frappe.show_alert({ message: __("Aucune modification à enregistrer."), indicator: "blue" });
        return;
    }

    page.btn_primary.prop("disabled", true);
    frappe.call({
        method: "hmd_agro.hmd_agro.page.saisie_alimentation.saisie_alimentation.post_aliment_corrections_batch",
        args: { date: date, entries: to_save },
        callback: function(r) {
            var s = r.message || { posted: 0, no_change: 0, errors: [] };
            var msg = s.posted + " ligne(s) de stock enregistrée(s)";
            if (s.no_change) msg += ", " + s.no_change + " aliment(s) sans changement";
            if (s.errors && s.errors.length) {
                msg += ", " + s.errors.length + " erreur(s)";
            }
            frappe.show_alert({
                message: msg,
                indicator: (s.errors && s.errors.length) ? "red" : "green"
            });
            if (s.errors && s.errors.length) {
                var lines = s.errors.map(function(e) {
                    return "<li><strong>" + frappe.utils.escape_html(e.item_code || "?") + "</strong> : " +
                           frappe.utils.escape_html(e.error) + "</li>";
                }).join("");
                frappe.msgprint({
                    title: __("Erreurs de saisie"),
                    indicator: "red",
                    message: "<ul>" + lines + "</ul>"
                });
            }
        },
        always: function() {
            page.btn_primary.prop("disabled", false);
            fetch_and_render(page, date);
        }
    });
}
