// HMD Agro global JS

/**
 * Make the first N columns of a query report's datatable sticky (frozen)
 * during horizontal scroll. The cells stay opaque on top of the zebra-striped
 * background defined in hmd_agro.css.
 *
 * Usage from a report's after_datatable_render(datatable):
 *     hmd_make_sticky_columns(datatable, 1);   // freeze nom_metier
 *     hmd_make_sticky_columns(datatable, 2);   // freeze nom_metier + lot
 *
 * Idempotent — won't re-inject style if already present in this datatable.
 */
window.hmd_make_sticky_columns = function (datatable, num_cols) {
    if (!datatable || !datatable.wrapper) return;
    if (datatable.wrapper.querySelector(".hmd-sticky-style")) return;

    let css = "";
    let left = 0;
    for (let i = 0; i < num_cols; i++) {
        const col = datatable.getColumn(i);
        const w = (col && col.width) || 90;
        css += `
            .dt-cell--col-${i}, .dt-cell--header-${i} {
                position: sticky !important; left: ${left}px; z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-${i} { z-index: 11; }
            .dt-row:nth-child(even) .dt-cell--col-${i} {
                background: linear-gradient(rgba(127,127,127,0.15), rgba(127,127,127,0.15)),
                            var(--card-bg) !important;
            }
        `;
        left += w;
    }
    // The column sort/options dropdown is rendered inside its own header cell.
    // For a non-frozen column adjacent to the sticky ones, that cell sits below
    // the sticky cells' z-index, so the open menu gets painted *behind* the
    // frozen columns. Lift the dropdown above the sticky stacking level (11).
    css += `
        .datatable .dt-dropdown__list { z-index: 50 !important; }
    `;
    const style = document.createElement("style");
    style.className = "hmd-sticky-style";
    style.textContent = css;
    datatable.wrapper.appendChild(style);
};


/**
 * Shrink the datatable to fit its content's natural width and center it on
 * the page. Useful for small print-out reports (3-4 columns) so the scrollbar
 * and visual gap don't sit awkwardly far from the data.
 *
 * Call from after_datatable_render(datatable):
 *     hmd_fit_table_to_content(datatable);
 */
window.hmd_fit_table_to_content = function (datatable) {
    if (!datatable || !datatable.wrapper) return;
    const cols = (datatable.columnmanager && datatable.columnmanager.columns) || [];
    let total = 0;
    cols.forEach((c) => { total += (c && c.width) || 0; });
    if (!total) return;
    total += 20; // small padding for borders / row-number column

    const dt = datatable.wrapper.querySelector(".datatable");
    if (!dt) return;
    dt.style.maxWidth = total + "px";
    dt.style.marginLeft = "auto";
    dt.style.marginRight = "auto";
};


// ─── SCRUM-10 — répartition des frais généraux par ligne de charge ───────────
//
// Client side of utils/repartition_charges.py for Purchase Invoice and
// Journal Entry (see purchase_invoice.js / journal_entry.js, which only
// `brancher` this object): show the « Répartition par atelier » section as
// soon as a charge line is booked on Frais Généraux, tell the accountant how
// much of each line is split so far, restrict the atelier picker, pre-fill
// `ligne`. Display only — the server hook remains the single authority
// (ERR-FIN-11..17).
window.hmd_repartition = {
    // Mirror of finance_kpis.ATELIER_FRAIS_GENERAUX (a cost center is
    // « Frais Généraux » by its short name, company suffix stripped).
    ATELIER_FRAIS_GENERAUX: "Frais Généraux",
    // Mirror of personnel.TOLERANCE_PCT — display tolerance on the 100 % check.
    TOLERANCE_PCT: 0.01,
    PCT_TOTAL: 100,
    CHAMP_SECTION: "section_repartition_atelier",
    CHAMP_TABLE: "repartition_atelier",
    DOCTYPE_ENFANT: "Repartition Atelier Charge",

    /**
     * Wire the form events of one parent doctype.
     *   params.table         child table holding the charge lines ("items" / "accounts")
     *   params.child_doctype its doctype (to catch `cost_center` changes)
     *   params.est_charge    (ligne) => bool — is this line a charge (débit) ?
     */
    brancher(doctype, params) {
        const R = this;
        frappe.ui.form.on(doctype, {
            setup(frm) {
                frm.hmd_repartition = params;
                R.filtrer_ateliers(frm);
            },
            refresh(frm) { R.rafraichir(frm); },
            [`${params.table}_add`](frm) { R.rafraichir(frm); },
            [`${params.table}_remove`](frm) { R.rafraichir(frm); },
            [`${R.CHAMP_TABLE}_add`](frm, cdt, cdn) {
                R.preremplir_ligne(frm, cdt, cdn);
                R.rafraichir(frm);
            },
            [`${R.CHAMP_TABLE}_remove`](frm) { R.rafraichir(frm); },
        });
        frappe.ui.form.on(params.child_doctype, {
            cost_center(frm) { R.rafraichir(frm); },
        });
    },

    nom_court(cost_center) {
        if (!cost_center) return cost_center;
        const coupure = cost_center.lastIndexOf(" - ");
        return coupure === -1 ? cost_center : cost_center.substring(0, coupure);
    },

    est_frais_generaux(cost_center) {
        return this.nom_court(cost_center) === this.ATELIER_FRAIS_GENERAUX;
    },

    /** idx of the parent's charge lines booked on Frais Généraux. */
    lignes_frais_generaux(frm) {
        const params = frm.hmd_repartition;
        return (frm.doc[params.table] || [])
            .filter((l) => params.est_charge(l) && this.est_frais_generaux(l.cost_center))
            .map((l) => l.idx);
    },

    /** Section shown only when something is to split (or already split). */
    rafraichir(frm) {
        if (!frm.hmd_repartition || !frm.fields_dict[this.CHAMP_TABLE]) return;
        const lignes = this.lignes_frais_generaux(frm);
        const parts = frm.doc[this.CHAMP_TABLE] || [];
        frm.toggle_display(this.CHAMP_SECTION, lignes.length > 0 || parts.length > 0);
        const texte = this.description(lignes, parts);
        frm.set_df_property(this.CHAMP_TABLE, "description", texte);
        // The grid renders its description once at creation: refresh the DOM too.
        const grille = frm.fields_dict[this.CHAMP_TABLE].grid;
        if (grille && grille.wrapper) grille.wrapper.find(".grid-description").html(texte);
    },

    /** « Ligne N — total réparti X % — il manque Y % » per Frais Généraux line. */
    description(lignes, parts) {
        if (!lignes.length) {
            return __("Aucune ligne de charge imputée à {0}.", [this.ATELIER_FRAIS_GENERAUX]);
        }
        const totaux = {};
        parts.forEach((p) => { totaux[p.ligne] = (totaux[p.ligne] || 0) + flt(p.pourcentage); });
        return lignes.map((idx) => this.etat_ligne(idx, flt(totaux[idx] || 0))).join("<br>");
    },

    etat_ligne(idx, total) {
        const manque = this.PCT_TOTAL - total;
        const pct = (v) => frappe.format(v, {fieldtype: "Float", precision: 2});
        if (Math.abs(manque) <= this.TOLERANCE_PCT) {
            return `<span style="color:green;font-weight:600">`
                + __("Ligne {0} — total réparti {1} % ✓", [idx, pct(total)]) + "</span>";
        }
        const reste = manque > 0
            ? __("il manque {0} %", [pct(manque)])
            : __("{0} % de trop", [pct(-manque)]);
        return `<span style="color:orange;font-weight:600">`
            + __("Ligne {0} — total réparti {1} % — {2}", [idx, pct(total), reste]) + "</span>";
    },

    /** Leaf cost centers of the company, Frais Généraux excluded. */
    filtrer_ateliers(frm) {
        frm.set_query("atelier", this.CHAMP_TABLE, () => ({
            filters: [
                ["Cost Center", "company", "=", frm.doc.company],
                ["Cost Center", "is_group", "=", 0],
                ["Cost Center", "name", "not like", `${this.ATELIER_FRAIS_GENERAUX} - %`],
            ],
        }));
    },

    /** New split row → `ligne` = first Frais Généraux line, if not set. */
    preremplir_ligne(frm, cdt, cdn) {
        const lignes = this.lignes_frais_generaux(frm);
        const row = locals[cdt] && locals[cdt][cdn];
        if (!row || row.ligne || !lignes.length) return;
        frappe.model.set_value(cdt, cdn, "ligne", lignes[0]);
    },
};

frappe.ui.form.on(window.hmd_repartition.DOCTYPE_ENFANT, {
    ligne(frm) { window.hmd_repartition.rafraichir(frm); },
    pourcentage(frm) { window.hmd_repartition.rafraichir(frm); },
});
