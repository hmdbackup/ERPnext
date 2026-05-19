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

        // Date picker — default to yesterday (saisie is for completed days)
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

        // Prev / Next day arrows
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

        // Primary action: save all corrections in one shot
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
        method: "hmd_agro.hmd_agro.page.saisie_alimentation.saisie_alimentation.get_saisie_state",
        args: { date: date },
        callback: function(r) {
            render_state(page, r.message || { date: date, lots: [] });
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

    var lots = state.lots || [];
    if (!lots.length) {
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

    // Help banner
    var help = $(
        '<div style="margin-bottom:15px; padding:10px 14px; background:var(--bg-color); ' +
        'border-left:3px solid var(--blue-500); border-radius:4px; font-size:13px; ' +
        'color:var(--text-muted);">' +
        'Saisissez le total <strong>réellement distribué</strong> par lot (en kg). ' +
        'Le système ajuste proportionnellement chaque aliment et corrige le stock. ' +
        'Laisser vide ou égal au théorique = aucune correction.' +
        '</div>'
    );
    container.append(help);

    // Table
    var table = $(
        '<table class="table table-bordered" style="background:var(--fg-color);">' +
        '<thead>' +
        '<tr style="background:var(--bg-color);">' +
        '<th style="width:120px;">Lot</th>' +
        '<th style="width:130px; text-align:right;">Théorique (kg)</th>' +
        '<th style="width:140px; text-align:center;">Réel (kg)</th>' +
        '<th style="width:110px; text-align:right;">Écart (kg)</th>' +
        '<th style="width:90px; text-align:right;">Écart %</th>' +
        '<th>Composition (ration)</th>' +
        '<th style="width:60px; text-align:center;">État</th>' +
        '</tr>' +
        '</thead>' +
        '<tbody></tbody>' +
        '<tfoot>' +
        '<tr style="background:var(--bg-color); font-weight:bold;">' +
        '<td style="text-align:right;">TOTAUX</td>' +
        '<td class="sa-total-theo" style="text-align:right;">0</td>' +
        '<td class="sa-total-actual" style="text-align:center;">0</td>' +
        '<td class="sa-total-delta" style="text-align:right;">0</td>' +
        '<td></td>' +
        '<td></td>' +
        '<td></td>' +
        '</tr>' +
        '</tfoot>' +
        '</table>'
    );
    var tbody = table.find("tbody");

    for (var i = 0; i < lots.length; i++) {
        var L = lots[i];
        var compo_text = (L.lines || []).map(function(line) {
            return line.aliment + " " + line.qty_theoretical + " kg";
        }).join(" + ");

        var state_pill = L.has_correction
            ? '<span class="indicator-pill orange" style="font-size:11px;">Corrigé</span>'
            : '<span class="indicator-pill green" style="font-size:11px;">Théorique</span>';

        var actual_value = L.has_correction ? L.actual_total : L.theoretical_total;

        var row = $(
            '<tr data-lot="' + L.lot + '" data-theo="' + L.theoretical_total + '">' +
            '<td><strong>' + L.lot + '</strong></td>' +
            '<td class="sa-theo" style="text-align:right;">' + L.theoretical_total.toFixed(2) + '</td>' +
            '<td style="text-align:center;">' +
                '<input type="number" min="0" step="0.1" class="form-control input-xs sa-actual-input" ' +
                'value="' + actual_value + '" ' +
                'data-original="' + actual_value + '" ' +
                'style="width:110px; text-align:center; display:inline-block;">' +
            '</td>' +
            '<td class="sa-delta" style="text-align:right;">0.00</td>' +
            '<td class="sa-delta-pct" style="text-align:right;">0.0%</td>' +
            '<td style="font-size:12px; color:var(--text-muted);">' + compo_text + '</td>' +
            '<td class="sa-state" style="text-align:center;">' + state_pill + '</td>' +
            '</tr>'
        );
        tbody.append(row);
    }

    container.append(table);

    // Input handlers
    container.off("input", ".sa-actual-input").on("input", ".sa-actual-input", function() {
        update_row($(this).closest("tr"));
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

    // Initial render of delta columns
    container.find("tbody tr").each(function() {
        update_row($(this));
    });
    update_totals(container);
}

function update_row(row) {
    var theo = parseFloat(row.data("theo")) || 0;
    var actual = parseFloat(row.find(".sa-actual-input").val()) || 0;
    var delta = actual - theo;
    var pct = theo > 0 ? (delta / theo) * 100 : 0;

    row.find(".sa-delta").text(delta.toFixed(2));
    row.find(".sa-delta-pct").text(pct.toFixed(1) + "%");

    // Color the écart
    var color = "var(--text-muted)";
    if (Math.abs(delta) >= 0.01) {
        color = delta > 0 ? "var(--orange-500)" : "var(--red-500)";
    }
    row.find(".sa-delta").css("color", color);
    row.find(".sa-delta-pct").css("color", color);
}

function update_totals(container) {
    var t_theo = 0, t_actual = 0, t_delta = 0;
    container.find("tbody tr").each(function() {
        var row = $(this);
        var theo = parseFloat(row.data("theo")) || 0;
        var actual = parseFloat(row.find(".sa-actual-input").val()) || 0;
        t_theo += theo;
        t_actual += actual;
        t_delta += (actual - theo);
    });
    container.find(".sa-total-theo").text(t_theo.toFixed(2));
    container.find(".sa-total-actual").text(t_actual.toFixed(2));
    var delta_cell = container.find(".sa-total-delta");
    delta_cell.text(t_delta.toFixed(2));
    delta_cell.css("color",
        Math.abs(t_delta) < 0.01 ? "var(--text-muted)"
        : (t_delta > 0 ? "var(--orange-500)" : "var(--red-500)"));
}

function save_all(page, date) {
    if (!date) {
        frappe.msgprint(__("Sélectionnez une date d'abord."));
        return;
    }
    var container = $(page.body).find(".sa-container");
    var to_save = [];
    container.find("tbody tr").each(function() {
        var row = $(this);
        var lot = row.data("lot");
        var input = row.find(".sa-actual-input");
        var actual = parseFloat(input.val());
        var original = parseFloat(input.data("original"));
        // Only call the backend for rows the user actually edited
        if (!isNaN(actual) && Math.abs(actual - original) > 0.001) {
            to_save.push({ lot: lot, actual: actual });
        }
    });

    if (!to_save.length) {
        frappe.show_alert({ message: __("Aucune modification à enregistrer."), indicator: "blue" });
        return;
    }

    // Build the batch payload the server expects: [{lot, actual_total}, ...]
    var entries = to_save.map(function(item) {
        return { lot: item.lot, actual_total: item.actual };
    });

    page.btn_primary.prop("disabled", true);
    frappe.call({
        method: "hmd_agro.hmd_agro.page.saisie_alimentation.saisie_alimentation.post_corrections_batch",
        args: { date: date, entries: entries },
        callback: function(r) {
            var s = r.message || { posted: 0, no_change: 0, errors: [] };
            var msg = s.posted + " correction(s) enregistrée(s)";
            if (s.no_change) msg += ", " + s.no_change + " sans changement";
            if (s.errors && s.errors.length) {
                msg += ", " + s.errors.length + " erreur(s)";
            }
            frappe.show_alert({
                message: msg,
                indicator: (s.errors && s.errors.length) ? "red" : "green"
            });
            if (s.errors && s.errors.length) {
                var lines = s.errors.map(function(e) {
                    return "<li><strong>" + e.lot + "</strong> : " +
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
