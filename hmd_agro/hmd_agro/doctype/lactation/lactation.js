// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lactation", {
    refresh(frm) {
        frm.trigger("set_filters");
        frm.trigger("filter_statut_options");
        frm.trigger("load_production_data");

        // Lock animal field when pre-filled or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        if (["TARIE", "INTERROMPUE"].includes(frm.doc.statut)) {
            frm.set_intro(__("Lactation clôturée — modification limitée."), "yellow");
        }
    },

    load_production_data(frm) {
        if (frm.is_new()) return;

        frappe.call({
            method: "hmd_agro.hmd_agro.doctype.lactation.lactation.get_production_chart_data",
            args: { lactation: frm.doc.name },
            callback: function(r) {
                frm._chart_data = r.message;
                frm._date_from = null;
                frm._date_to = null;

                frappe.call({
                    method: "hmd_agro.hmd_agro.doctype.lactation.lactation.get_traite_grid_data",
                    args: { lactation: frm.doc.name },
                    callback: function(r2) {
                        frm._grid_data = r2.message;
                        frm.trigger("render_filter_bar");
                        frm.trigger("render_production_chart");
                        frm.trigger("render_traite_grid");
                    }
                });
            }
        });
    },

    render_filter_bar(frm) {
        let chart_wrapper = frm.fields_dict.chart_production.$wrapper;

        // Remove existing filter bar
        chart_wrapper.find(".lac-filter-bar").remove();

        let bar = $('<div class="lac-filter-bar" style="display:flex; align-items:flex-end; gap:12px; margin-bottom:12px; flex-wrap:wrap;"></div>');

        let du_wrapper = $('<div class="lac-ctrl-du"></div>');
        let au_wrapper = $('<div class="lac-ctrl-au"></div>');

        bar.append(du_wrapper).append(au_wrapper);
        chart_wrapper.prepend(bar);

        // Frappe native date controls
        frm._ctrl_date_from = frappe.ui.form.make_control({
            parent: du_wrapper,
            df: { fieldtype: "Date", fieldname: "lac_date_from", label: "Du" },
            render_input: true
        });
        function strip_control_margins(ctrl) {
            ctrl.$wrapper.find(".form-group").css("margin-bottom", "0");
            ctrl.$wrapper.find(".help-box").hide();
        }
        strip_control_margins(frm._ctrl_date_from);

        frm._ctrl_date_to = frappe.ui.form.make_control({
            parent: au_wrapper,
            df: { fieldtype: "Date", fieldname: "lac_date_to", label: "Au" },
            render_input: true
        });
        strip_control_margins(frm._ctrl_date_to);

        let btn = $('<button class="btn btn-xs btn-dark lac-reset-filter" style="background:#1f272e; color:#fff; border:none;">Tout afficher</button>');
        bar.append(btn);

        frm._ctrl_date_from.$input.on("change", function() {
            frm._date_from = frm._ctrl_date_from.get_value() || null;
            frm.trigger("render_production_chart");
            frm.trigger("render_traite_grid");
        });

        frm._ctrl_date_to.$input.on("change", function() {
            frm._date_to = frm._ctrl_date_to.get_value() || null;
            frm.trigger("render_production_chart");
            frm.trigger("render_traite_grid");
        });

        bar.find(".lac-reset-filter").on("click", function() {
            frm._ctrl_date_from.set_value("");
            frm._ctrl_date_to.set_value("");
            frm._date_from = null;
            frm._date_to = null;
            frm.trigger("render_production_chart");
            frm.trigger("render_traite_grid");
        });
    },

    render_production_chart(frm) {
        if (frm.is_new()) return;

        let wrapper = frm.fields_dict.chart_production.$wrapper;
        wrapper.find(".lac-chart-area").remove();
        let chart_area = $('<div class="lac-chart-area"></div>');
        wrapper.append(chart_area);

        let data = frm._chart_data;
        if (!data) {
            chart_area.html('<div class="text-muted text-center" style="padding: 30px;">Aucune donnée de production disponible.</div>');
            return;
        }

        let labels = data.labels;
        let dates = data.dates;
        let values = data.datasets[0].values;
        let filtered_labels = [];
        let filtered_values = [];

        for (let i = 0; i < dates.length; i++) {
            let d = dates[i];
            if (frm._date_from && d < frm._date_from) continue;
            if (frm._date_to && d > frm._date_to) continue;
            filtered_labels.push(labels[i]);
            filtered_values.push(values[i]);
        }

        if (!filtered_labels.length) {
            chart_area.html('<div class="text-muted text-center" style="padding: 30px;">Aucune donnée pour cette période.</div>');
            return;
        }

        new frappe.Chart(chart_area[0], {
            title: __("Production journalière (L)"),
            data: {
                labels: filtered_labels,
                datasets: [{
                    name: __("Production"),
                    values: filtered_values
                }]
            },
            type: "line",
            height: 250,
            colors: ["#4299e1"],
            lineOptions: {
                regionFill: 1
            },
            axisOptions: {
                xIsSeries: true
            }
        });
    },

    render_traite_grid(frm) {
        if (frm.is_new()) return;

        let wrapper = frm.fields_dict.traite_grid.$wrapper;
        wrapper.empty();

        let rows = frm._grid_data;
        if (!rows) {
            wrapper.html('<div class="text-muted text-center" style="padding:20px;">Aucune traite enregistree.</div>');
            return;
        }

        let filtered = rows.filter(function(d) {
            if (frm._date_from && d.date < frm._date_from) return false;
            if (frm._date_to && d.date > frm._date_to) return false;
            return true;
        });

        if (!filtered.length) {
            wrapper.html('<div class="text-muted text-center" style="padding:20px;">Aucune traite pour cette période.</div>');
            return;
        }

        let sum_m = 0, sum_s = 0, sum_t = 0;

        let html = '<div style="max-height:400px; overflow-y:auto;">' +
            '<table class="table table-bordered" style="background:var(--fg-color); margin:0;">' +
            '<thead><tr style="background:var(--bg-color);">' +
            '<th style="text-align:center;">Date</th>' +
            '<th style="text-align:center;">MATIN</th>' +
            '<th style="text-align:center;">SOIR</th>' +
            '<th style="text-align:center;">Total</th>' +
            '</tr></thead><tbody>';

        for (let i = 0; i < filtered.length; i++) {
            let d = filtered[i];
            let m = d.MATIN, s = d.SOIR;
            sum_m += m || 0;
            sum_s += s || 0;
            sum_t += d.total || 0;

            let row_class = "";
            if (i < filtered.length - 1 && filtered[i + 1].total > 0 && d.total > 0) {
                let drop = ((d.total - filtered[i + 1].total) / filtered[i + 1].total) * 100;
                if (drop <= -30) {
                    row_class = ' style="background:var(--bg-red, #fff5f5);"';
                }
            }

            let date_str = frappe.datetime.str_to_user(d.date);
            html += '<tr' + row_class + '>' +
                '<td style="text-align:center;">' + date_str + '</td>' +
                '<td style="text-align:center;">' + (m != null ? m : '-') + '</td>' +
                '<td style="text-align:center;">' + (s != null ? s : '-') + '</td>' +
                '<td style="text-align:center; font-weight:600;">' + d.total + '</td>' +
                '</tr>';
        }

        html += '</tbody>' +
            '<tfoot><tr style="background:var(--bg-color); font-weight:bold;">' +
            '<td style="text-align:right;">TOTAUX</td>' +
            '<td style="text-align:center;">' + sum_m.toFixed(1) + '</td>' +
            '<td style="text-align:center;">' + sum_s.toFixed(1) + '</td>' +
            '<td style="text-align:center;">' + sum_t.toFixed(1) + '</td>' +
            '</tr></tfoot></table></div>';

        let avg = filtered.length > 0 ? (sum_t / filtered.length).toFixed(1) : 0;
        let summary = '<div style="margin-bottom:10px; font-size:13px; color:var(--text-muted);">' +
            '<strong>' + filtered.length + '</strong> jours de traite &nbsp;|&nbsp; ' +
            'Total: <strong>' + sum_t.toFixed(1) + ' L</strong> &nbsp;|&nbsp; ' +
            'Moyenne/jour: <strong>' + avg + ' L</strong>' +
            '</div>';

        wrapper.html(summary + html);
    },

    set_filters(frm) {
        frm.set_query("animal", function() {
            return {
                filters: {
                    categorie: ["in", ["VACHE", "GENISSE"]],
                    sexe: "F",
                    statut: "ACTIF"
                }
            };
        });

        frm.set_query("velage_debut", function() {
            return {
                filters: {
                    animal: frm.doc.animal
                }
            };
        });
    },

    filter_statut_options(frm) {
        if (frm.is_new()) {
            frm.set_df_property("statut", "options", "EN_COURS");
            frm.set_df_property("statut", "read_only", 1);
            return;
        }

        const current = frm.doc.statut;
        const transitions = {
            "EN_COURS":    ["EN_COURS", "TARIE", "INTERROMPUE"],
            "TARIE":       ["TARIE"],
            "INTERROMPUE": ["INTERROMPUE"],
        };

        const allowed = transitions[current] || [current];
        frm.set_df_property("statut", "options", allowed.join("\n"));
        frm.set_df_property("statut", "read_only", allowed.length <= 1 ? 1 : 0);

        if (["TARIE", "INTERROMPUE"].includes(current)) {
            frm.set_df_property("statut", "description", __("État final — aucune transition possible."));
        }
    }
});
