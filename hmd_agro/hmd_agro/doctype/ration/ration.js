frappe.ui.form.on("Ration", {
    refresh(frm) {
        frm.fields_dict.composition.grid.get_field("aliment").get_query = function() {
            return {};
        };

        // Composition + name are immutable after first save (enforced by
        // ration.py:_validate_immutability). Lock the UI to match — no point
        // letting users edit fields that will reject on save.
        if (!frm.is_new()) {
            frm.set_df_property("composition", "read_only", 1);
            frm.set_df_property("nom_ration", "read_only", 1);
            render_lots_utilisateurs(frm);
        }
    }
});

function render_lots_utilisateurs(frm) {
    frappe.call({
        method: "hmd_agro.hmd_agro.doctype.ration.ration.lots_using_ration",
        args: { ration: frm.doc.name },
        callback: (r) => {
            const rows = (r.message || []);
            let html;
            if (!rows.length) {
                html = `<p class="text-muted">${__("Aucun lot n'utilise actuellement cette ration.")}</p>`;
            } else {
                const items = rows.map(row => {
                    const lot_link = `<a href="/app/lot/${encodeURIComponent(row.lot)}">${frappe.utils.escape_html(row.lot)}</a>`;
                    const date = frappe.datetime.str_to_user(row.date_debut);
                    return `<tr><td>${lot_link}</td><td>${date}</td></tr>`;
                }).join("");
                html =
                    `<table class="table table-bordered" style="margin: 0;">` +
                    `<thead><tr><th>${__("Lot")}</th><th>${__("Affecté depuis")}</th></tr></thead>` +
                    `<tbody>${items}</tbody></table>`;
            }
            frm.fields_dict.lots_utilisateurs_html.$wrapper.html(html);
        }
    });
}

frappe.ui.form.on("Composition Ration", {
    aliment(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.aliment) {
            frappe.db.get_value("Aliment", row.aliment, ["prix_unitaire", "unite"], function(r) {
                if (r) {
                    frappe.model.set_value(cdt, cdn, "unite", r.unite);
                    let sous_total = (row.quantite || 0) * (r.prix_unitaire || 0);
                    frappe.model.set_value(cdt, cdn, "sous_total", sous_total);
                    calculate_cout_estime(frm);
                }
            });
        }
    },

    quantite(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.aliment) {
            frappe.db.get_value("Aliment", row.aliment, "prix_unitaire", function(r) {
                if (r) {
                    let sous_total = (row.quantite || 0) * (r.prix_unitaire || 0);
                    frappe.model.set_value(cdt, cdn, "sous_total", sous_total);
                    calculate_cout_estime(frm);
                }
            });
        }
    },

    composition_remove(frm) {
        calculate_cout_estime(frm);
    }
});

function calculate_cout_estime(frm) {
    let total = 0;
    (frm.doc.composition || []).forEach(function(row) {
        total += row.sous_total || 0;
    });
    frm.set_value("cout_estime", total);
}
