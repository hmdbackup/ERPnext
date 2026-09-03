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


// ─── SCRUM-10 — frais généraux répartis par la clé (Cost Center Allocation) ──
//
// Client side of utils/repartition_charges.py for Purchase Invoice and
// Journal Entry (see purchase_invoice.js / journal_entry.js, which only
// `brancher` this object). Nothing is typed here any more (03/09/2026): the
// accountant books the charge on Frais Généraux and ERPNext's Cost Center
// Allocation splits the GL entries at submit time. The form only SHOWS the
// key in force on the posting date — where the charge will land — and gives
// a button to open the key. The server hook stays the single authority.
window.hmd_cle_repartition = {
    // Mirror of finance_kpis.ATELIER_FRAIS_GENERAUX (a cost center is
    // « Frais Généraux » by its short name, company suffix stripped).
    ATELIER_FRAIS_GENERAUX: "Frais Généraux",
    METHODE: "hmd_agro.hmd_agro.utils.repartition_charges.cle_en_vigueur",

    /**
     * Wire the form events of one parent doctype.
     *   params.table         child table holding the charge lines ("items" / "accounts")
     *   params.child_doctype its doctype (to catch `cost_center` changes)
     *   params.est_charge    (ligne) => bool — is this line a charge (débit) ?
     */
    brancher(doctype, params) {
        const R = this;
        frappe.ui.form.on(doctype, {
            setup(frm) { frm.hmd_cle_repartition = params; },
            refresh(frm) { R.rafraichir(frm); },
            posting_date(frm) { R.rafraichir(frm); },
            cost_center(frm) { R.rafraichir(frm); },
            [`${params.table}_add`](frm) { R.rafraichir(frm); },
            [`${params.table}_remove`](frm) { R.rafraichir(frm); },
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

    /** Frais Généraux cost centers used by the charge lines (or the header). */
    centres_frais_generaux(frm) {
        const params = frm.hmd_cle_repartition;
        const centres = (frm.doc[params.table] || [])
            .filter((l) => params.est_charge(l) && this.est_frais_generaux(l.cost_center))
            .map((l) => l.cost_center);
        if (!centres.length && this.est_frais_generaux(frm.doc.cost_center)) {
            centres.push(frm.doc.cost_center);
        }
        return [...new Set(centres)];
    },

    /** Headline « Clé Frais Généraux en vigueur au … : Lait 60 % · … ». */
    rafraichir(frm) {
        if (!frm.hmd_cle_repartition || !frm.doc.company) return;
        const centres = this.centres_frais_generaux(frm);
        if (!centres.length) {
            frm.dashboard.clear_headline();
            return;
        }
        const cc = centres[0];
        frappe.call({
            method: this.METHODE,
            args: {company: frm.doc.company, posting_date: frm.doc.posting_date, cost_center: cc},
            callback: (r) => {
                if (!r.message) return;
                frm.dashboard.set_headline_alert(
                    this.texte(r.message, frm.doc.posting_date),
                    r.message.cle ? "blue" : (r.message.strict ? "red" : "orange"));
                this.bouton_cle(frm, cc);
            },
        });
    },

    texte(reponse, posting_date) {
        const date = frappe.datetime.str_to_user(posting_date);
        if (reponse.cle) {
            return __("Clé de répartition {0} en vigueur au {1} : <b>{2}</b> — les écritures "
                + "comptables seront réparties ainsi à la validation ({3}, depuis le {4}).",
                [reponse.centre, date, reponse.cle.libelle, reponse.cle.name,
                 reponse.cle.valid_from]);
        }
        return __("Aucune clé de répartition en vigueur au {0} pour {1} : la charge "
            + "restera à {1}, hors coût du litre.{2}",
            [date, reponse.centre,
             reponse.strict ? " " + __("La sauvegarde sera refusée (mode strict).") : ""]);
    },

    bouton_cle(frm, cost_center) {
        const libelle = __("Clé de répartition");
        if (frm.custom_buttons && frm.custom_buttons[libelle]) return;
        frm.add_custom_button(libelle, () => {
            frappe.set_route("List", "Cost Center Allocation",
                {main_cost_center: cost_center, docstatus: 1});
        });
    },
};
