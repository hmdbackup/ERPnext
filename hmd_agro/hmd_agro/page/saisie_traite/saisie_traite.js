frappe.pages["saisie-traite"].on_page_show = function(wrapper) {
    load_saisie_traite(wrapper);
};

frappe.pages["saisie-traite"].refresh = function(wrapper) {
    load_saisie_traite(wrapper);
};

var st_wrapper_ref;

function load_saisie_traite(wrapper) {
    st_wrapper_ref = wrapper;

    var page = wrapper.page || frappe.ui.make_app_page({
        parent: wrapper,
        title: "Saisie Traite",
        single_column: true
    });
    if (!wrapper.page) {
        wrapper.page = page;
    }

    if (!wrapper._st_initialized) {
        wrapper._st_initialized = true;

        // Date picker
        wrapper._st_date_input = frappe.ui.form.make_control({
            parent: page.page_actions,
            df: {
                fieldtype: "Date",
                fieldname: "traite_date",
                default: frappe.datetime.get_today()
            },
            render_input: true
        });
        wrapper._st_date_input.set_value(frappe.datetime.get_today());
        wrapper._st_date_input.$wrapper.css({
            "display": "inline-block",
            "margin-left": "15px",
            "margin-right": "0",
            "width": "160px",
            "vertical-align": "middle"
        });
        // Move date input after the buttons so it appears on the right
        wrapper._st_date_input.$wrapper.appendTo(page.page_actions);
        wrapper._st_date_input.$input.on("change", function() {
            fetch_and_render(page, wrapper._st_date_input.get_value());
        });

        // Date navigation arrows
        var arrow_container = $('<div class="st-date-arrows" style="display:inline-block; vertical-align:middle; margin-left:8px;"></div>');
        var btn_prev = $('<button class="btn btn-default btn-xs" title="Jour précédent" style="padding:2px 8px;">&lsaquo;</button>');
        var btn_next = $('<button class="btn btn-default btn-xs" title="Jour suivant" style="padding:2px 8px; margin-left:4px;">&rsaquo;</button>');
        arrow_container.append(btn_prev).append(btn_next);
        arrow_container.appendTo(page.page_actions);

        btn_prev.on("click", function() {
            var current = wrapper._st_date_input.get_value();
            if (current) {
                var prev = frappe.datetime.add_days(current, -1);
                wrapper._st_date_input.set_value(prev);
                fetch_and_render(page, prev);
            }
        });
        btn_next.on("click", function() {
            var current = wrapper._st_date_input.get_value();
            if (current) {
                var next = frappe.datetime.add_days(current, 1);
                wrapper._st_date_input.set_value(next);
                fetch_and_render(page, next);
            }
        });

        // Save button
        page.set_primary_action(__("Enregistrer"), function() {
            save_all(page, wrapper._st_date_input.get_value());
        }, "octicon octicon-check");

        // Fix Enregistrer button text centering
        page.btn_primary.css({
            "display": "inline-flex",
            "align-items": "center",
            "justify-content": "center",
            "gap": "4px"
        });

        // Print button
        var print_btn = page.add_button(__("Imprimer"), function() {
            print_table(page);
        });
        print_btn.css("margin-right", "8px");

        // Hide menu
        page.menu.parent().hide();
    }

    fetch_and_render(page, wrapper._st_date_input.get_value());
}

function fetch_and_render(page, date) {
    if (!date) return;

    frappe.call({
        method: "hmd_agro.hmd_agro.page.saisie_traite.saisie_traite.get_lactating_animals",
        args: { date: date },
        callback: function(r) {
            render_table(page, r.message || [], date);
        }
    });
}

function render_table(page, data, date) {
    var container = $(page.body).find(".st-container");
    if (!container.length) {
        container = $('<div class="st-container" style="padding: 15px;"></div>').appendTo(page.body);
    }
    container.empty();

    if (!data.length) {
        container.html(
            '<div style="text-align:center; padding:60px; color:var(--text-muted);">' +
            '<h4>Aucun animal en lactation</h4>' +
            '<p>Aucune lactation EN_COURS trouvee.</p>' +
            '</div>'
        );
        return;
    }

    // Summary bar
    var summary = $('<div class="st-summary" style="margin-bottom:15px; display:flex; gap:20px; flex-wrap:wrap;"></div>');
    container.append(summary);

    // Table
    var table = $(
        '<table class="table table-bordered" style="background:var(--fg-color);">' +
        '<thead>' +
        '<tr style="background:var(--bg-color);">' +
        '<th style="width:40px; text-align:center;">#</th>' +
        '<th style="min-width:80px;">Nom</th>' +
        '<th style="min-width:80px;">Lot</th>' +
        '<th style="width:110px; text-align:center;">MATIN</th>' +
        '<th style="width:110px; text-align:center;">SOIR</th>' +
        '<th style="width:80px; text-align:center;">Total</th>' +
        '<th style="width:90px; text-align:center;">Alerte</th>' +
        '</tr>' +
        '</thead>' +
        '<tbody></tbody>' +
        '<tfoot>' +
        '<tr style="background:var(--bg-color); font-weight:bold;">' +
        '<td></td>' +
        '<td></td>' +
        '<td style="text-align:right;">TOTAUX</td>' +
        '<td class="st-total-matin" style="text-align:center;">0</td>' +
        '<td class="st-total-soir" style="text-align:center;">0</td>' +
        '<td class="st-total-grand" style="text-align:center;">0</td>' +
        '<td></td>' +
        '</tr>' +
        '</tfoot>' +
        '</table>'
    );

    var tbody = table.find("tbody");

    for (var i = 0; i < data.length; i++) {
        var d = data[i];
        var row = $(
            '<tr data-animal="' + d.animal + '" data-prev-total="' + d.prev_total + '">' +
            '<td style="text-align:center; color:var(--text-muted);">' + (i + 1) + '</td>' +
            '<td><a href="/app/animal/' + d.animal + '" style="font-weight:600;">' + d.nom_metier + '</a></td>' +
            '<td style="color:var(--text-muted); font-size:13px;">' + (d.lot && d.lot !== "Individuel" ? d.lot : "") + '</td>' +
            '<td style="text-align:center;">' + make_input(d, "MATIN") + '</td>' +
            '<td style="text-align:center;">' + make_input(d, "SOIR") + '</td>' +
            '<td class="st-row-total" style="text-align:center; font-weight:600;">0</td>' +
            '<td class="st-row-alert" style="text-align:center;"></td>' +
            '</tr>'
        );
        tbody.append(row);
    }

    container.append(table);

    // Bind input events
    container.off("input", ".st-qty-input").on("input", ".st-qty-input", function() {
        update_totals(container);
    });

    // Keyboard navigation + block negative input
    container.off("keydown", ".st-qty-input").on("keydown", ".st-qty-input", function(e) {
        if (e.key === "-" || e.key === "e") {
            e.preventDefault();
            return;
        }
        if (e.key === "Enter") {
            e.preventDefault();
            var inputs = container.find(".st-qty-input");
            var idx = inputs.index(this);
            if (idx < inputs.length - 1) {
                inputs.eq(idx + 1).focus().select();
            }
        }
    });

    // Clamp on blur: force value into 0-60 range
    container.off("blur", ".st-qty-input").on("blur", ".st-qty-input", function() {
        var val = parseFloat($(this).val());
        if (isNaN(val)) return;
        if (val < 0) {
            $(this).val(0);
            update_totals(container);
        } else if (val > 60) {
            $(this).val(60);
            update_totals(container);
        }
    });

    // Initial calculation
    update_totals(container);
}

function make_input(d, session) {
    var session_key = session.toLowerCase();
    var existing = d[session_key];
    var val = existing ? existing.qty : "";
    var traite_name = existing ? existing.name : "";

    return '<input type="number" min="0" max="60" step="0.1" ' +
        'class="form-control input-xs st-qty-input" ' +
        'data-animal="' + d.animal + '" ' +
        'data-session="' + session + '" ' +
        'data-traite-name="' + traite_name + '" ' +
        'value="' + val + '" ' +
        'style="width:90px; display:inline-block; text-align:center;">';
}

function update_totals(container) {
    var total_matin = 0, total_soir = 0, grand_total = 0;

    container.find("tbody tr").each(function() {
        var row = $(this);
        var row_total = 0;

        row.find(".st-qty-input").each(function() {
            var val = parseFloat($(this).val()) || 0;
            var session = $(this).data("session");
            row_total += val;
            if (session === "MATIN") total_matin += val;
            else if (session === "SOIR") total_soir += val;
        });

        row.find(".st-row-total").text(row_total ? row_total.toFixed(1) : "0");

        // Drop detection
        var prev = parseFloat(row.data("prev-total")) || 0;
        var alert_cell = row.find(".st-row-alert");
        alert_cell.empty();
        row.css("background", "");

        if (prev > 0 && row_total > 0) {
            var drop_pct = ((row_total - prev) / prev) * 100;
            if (drop_pct <= -30) {
                alert_cell.html(
                    '<span class="indicator-pill red" style="font-size:11px;">' +
                    Math.round(drop_pct) + '%</span>'
                );
                row.css("background", "var(--bg-red, #fff5f5)");
            }
        }

        grand_total += row_total;
    });

    container.find(".st-total-matin").text(total_matin.toFixed(1));
    container.find(".st-total-soir").text(total_soir.toFixed(1));
    container.find(".st-total-grand").text(grand_total.toFixed(1));

    // Update summary
    var animal_count = container.find("tbody tr").length;
    var filled = container.find(".st-qty-input").filter(function() {
        return $(this).val() !== "" && $(this).val() !== "0";
    }).length;
    container.find(".st-summary").html(
        '<span style="font-size:14px; color:var(--text-muted);">' +
        '<strong>' + animal_count + '</strong> animaux &nbsp;|&nbsp; ' +
        '<strong>' + filled + '</strong> saisies &nbsp;|&nbsp; ' +
        'Total: <strong>' + grand_total.toFixed(1) + ' L</strong>' +
        '</span>'
    );
}

function save_all(page, date) {
    var container = $(page.body).find(".st-container");
    var entries = [];

    container.find(".st-qty-input").each(function() {
        var val = $(this).val();
        if (val !== "" && val !== null) {
            var qty = parseFloat(val);
            if (!isNaN(qty) && qty >= 0) {
                entries.push({
                    animal: $(this).data("animal"),
                    session: $(this).data("session"),
                    quantite_litres: qty,
                    traite_name: $(this).data("traite-name") || null
                });
            }
        }
    });

    if (!entries.length) {
        frappe.show_alert({ message: "Aucune saisie a enregistrer", indicator: "orange" });
        return;
    }

    frappe.call({
        method: "hmd_agro.hmd_agro.page.saisie_traite.saisie_traite.save_traites",
        args: {
            date: date,
            entries: JSON.stringify(entries)
        },
        freeze: true,
        freeze_message: "Enregistrement en cours...",
        callback: function(r) {
            if (r.message) {
                var res = r.message;
                var msg = "";
                if (res.created) msg += res.created + " creee(s) ";
                if (res.updated) msg += res.updated + " mise(s) a jour ";
                if (res.errors && res.errors.length) {
                    msg += res.errors.length + " erreur(s)";
                    frappe.show_alert({ message: msg, indicator: "orange" });
                    // Show error details
                    var err_html = res.errors.map(function(e) {
                        return "<li><b>" + e.animal + " " + e.session + "</b>: " + e.error + "</li>";
                    }).join("");
                    frappe.msgprint("<ul>" + err_html + "</ul>", "Erreurs");
                } else {
                    frappe.show_alert({ message: msg || "OK", indicator: "green" });
                }
                // Reload to get traite names for future updates
                fetch_and_render(page, date);
            }
        }
    });
}

function print_table(page) {
    var container = $(page.body).find(".st-container");
    var date_val = st_wrapper_ref._st_date_input.get_value();

    var html = '<!DOCTYPE html><html><head><title>Saisie Traite - ' + date_val + '</title>' +
        '<style>' +
        'body { font-family: Arial, sans-serif; margin: 20px; }' +
        'h2 { margin-bottom: 5px; }' +
        'table { border-collapse: collapse; width: 100%; margin-top: 15px; }' +
        'th, td { border: 1px solid #333; padding: 6px 10px; text-align: center; font-size: 13px; }' +
        'th { background: #f0f0f0; }' +
        '.text-left { text-align: left; }' +
        '.alert-cell { color: red; font-weight: bold; }' +
        'tfoot td { font-weight: bold; background: #f0f0f0; }' +
        '@media print { body { margin: 10px; } }' +
        '</style></head><body>';

    html += '<h2>Saisie Traite</h2>';
    html += '<p>Date: <strong>' + date_val + '</strong></p>';

    html += '<table><thead><tr>' +
        '<th>#</th><th class="text-left">Nom</th><th class="text-left">Lot</th>' +
        '<th>MATIN</th><th>SOIR</th><th>Total</th><th>Alerte</th>' +
        '</tr></thead><tbody>';

    var total_m = 0, total_s = 0, total_g = 0;

    container.find("tbody tr").each(function(idx) {
        var row = $(this);
        var nom = row.find("td:eq(1)").text();
        var lot = row.find("td:eq(2)").text();
        var inputs = row.find(".st-qty-input");
        var m = parseFloat(inputs.eq(0).val()) || 0;
        var s = parseFloat(inputs.eq(1).val()) || 0;
        var t = m + s;
        var alert_text = row.find(".st-row-alert").text().trim();

        total_m += m; total_s += s; total_g += t;

        html += '<tr>' +
            '<td>' + (idx + 1) + '</td>' +
            '<td class="text-left">' + nom + '</td>' +
            '<td class="text-left">' + lot + '</td>' +
            '<td>' + (m || '') + '</td>' +
            '<td>' + (s || '') + '</td>' +
            '<td>' + (t ? t.toFixed(1) : '') + '</td>' +
            '<td class="alert-cell">' + alert_text + '</td>' +
            '</tr>';
    });

    html += '</tbody><tfoot><tr>' +
        '<td></td><td></td><td>TOTAUX</td>' +
        '<td>' + total_m.toFixed(1) + '</td>' +
        '<td>' + total_s.toFixed(1) + '</td>' +
        '<td>' + total_g.toFixed(1) + '</td>' +
        '<td></td></tr></tfoot></table>';

    html += '</body></html>';

    var w = window.open('', '_blank');
    w.document.write(html);
    w.document.close();
    w.focus();
    w.print();
}
