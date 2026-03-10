// Copyright (c) 2026, Mouhib Bouzamita and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lactation", {
    refresh(frm) {
        frm.trigger("set_filters");
        frm.trigger("filter_statut_options");
        frm.trigger("render_production_chart");
        frm.trigger("render_traite_grid");

        // Lock animal field when pre-filled or already saved
        if (frm.doc.animal) {
            frm.set_df_property("animal", "read_only", 1);
        }

        if (["TARIE", "INTERROMPUE"].includes(frm.doc.statut)) {
            frm.set_intro(__("Lactation clôturée — modification limitée."), "yellow");
        }
    },

    render_production_chart(frm) {
        if (frm.is_new()) return;

        let wrapper = frm.fields_dict.chart_production.$wrapper;
        wrapper.empty();

        frappe.call({
            method: "hmd_agro.hmd_agro.doctype.lactation.lactation.get_production_chart_data",
            args: { lactation: frm.doc.name },
            callback: function(r) {
                if (!r.message) {
                    wrapper.html('<div class="text-muted text-center" style="padding: 30px;">Aucune donnée de production disponible.</div>');
                    return;
                }

                let chart_data = r.message;
                new frappe.Chart(wrapper[0], {
                    title: __("Production journalière (L)"),
                    data: {
                        labels: chart_data.labels,
                        datasets: [{
                            name: __("Production"),
                            values: chart_data.datasets[0].values
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
            }
        });
    },

    render_traite_grid(frm) {
        if (frm.is_new()) return;

        let wrapper = frm.fields_dict.traite_grid.$wrapper;
        wrapper.empty();

        frappe.call({
            method: "hmd_agro.hmd_agro.doctype.lactation.lactation.get_traite_grid_data",
            args: { lactation: frm.doc.name },
            callback: function(r) {
                if (!r.message) {
                    wrapper.html('<div class="text-muted text-center" style="padding:20px;">Aucune traite enregistree.</div>');
                    return;
                }

                let rows = r.message;
                let sum_m = 0, sum_s = 0, sum_t = 0;

                let html = '<div style="max-height:400px; overflow-y:auto;">' +
                    '<table class="table table-bordered" style="background:var(--fg-color); margin:0;">' +
                    '<thead><tr style="background:var(--bg-color);">' +
                    '<th style="text-align:center;">Date</th>' +
                    '<th style="text-align:center;">MATIN</th>' +
                    '<th style="text-align:center;">SOIR</th>' +
                    '<th style="text-align:center;">Total</th>' +
                    '</tr></thead><tbody>';

                for (let i = 0; i < rows.length; i++) {
                    let d = rows[i];
                    let m = d.MATIN, s = d.SOIR;
                    sum_m += m || 0;
                    sum_s += s || 0;
                    sum_t += d.total || 0;

                    // Highlight: compare with previous day (next in array since sorted DESC)
                    let row_class = "";
                    if (i < rows.length - 1 && rows[i + 1].total > 0 && d.total > 0) {
                        let drop = ((d.total - rows[i + 1].total) / rows[i + 1].total) * 100;
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

                // Summary line above table
                let avg = rows.length > 0 ? (sum_t / rows.length).toFixed(1) : 0;
                let summary = '<div style="margin-bottom:10px; font-size:13px; color:var(--text-muted);">' +
                    '<strong>' + rows.length + '</strong> jours de traite &nbsp;|&nbsp; ' +
                    'Total: <strong>' + sum_t.toFixed(1) + ' L</strong> &nbsp;|&nbsp; ' +
                    'Moyenne/jour: <strong>' + avg + ' L</strong>' +
                    '</div>';

                wrapper.html(summary + html);
            }
        });
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
        /**
         * Restrict the "statut" dropdown to valid transitions only.
         * EN_COURS    → TARIE, INTERROMPUE
         * TARIE       → (final)
         * INTERROMPUE → (final)
         * New doc     → EN_COURS only
         */
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
