frappe.query_reports["Allotement Animaux"] = {
    onload(report) {
        if (report.__allotement_actions_added) {
            return;
        }
        report.__allotement_actions_added = true;

        report.page.add_inner_button(__("Panneau Suggestions"), () => {
            if (is_session_mode(report)) return;
            const rows = (frappe.query_report.data || []).filter((r) => r.animal);
            if (!rows.length) {
                frappe.msgprint(__("Aucune ligne disponible."));
                return;
            }
            open_suggestion_dialog(report, rows);
        });

        report.page.add_inner_button(__("Mouvements Manuels"), () => {
            if (is_session_mode(report)) return;
            const rows = (frappe.query_report.data || []).filter((r) => r.animal);
            if (!rows.length) {
                frappe.msgprint(__("Aucune ligne disponible."));
                return;
            }
            open_manual_dialog(report, rows);
        });

        report.page.add_inner_button(__("Historique"), () => open_history_dialog(report));

        report.page.add_inner_button(__("Live"), () => {
            report.set_filter_value("session", "");
            report.set_filter_value("today_display", frappe.datetime.get_today());
            report.refresh();
        }).hide();

        // Toggle Live button visibility based on whether a session is selected.
        const refreshLiveBtn = () => {
            const btn = report.page.inner_toolbar.find('.btn:contains("Live")');
            is_session_mode(report) ? btn.show() : btn.hide();
        };
        const origRefresh = report.refresh.bind(report);
        report.refresh = function () {
            const r = origRefresh();
            setTimeout(refreshLiveBtn, 100);
            return r;
        };
    },

    filters: [
        {
            fieldname: "today_display",
            label: __("Aujourd'hui"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            read_only: 1
        },
        {
            fieldname: "lot",
            label: __("Lot"),
            fieldtype: "Link",
            options: "Lot"
        },
        {
            fieldname: "session",
            label: __("Session"),
            fieldtype: "Link",
            options: "Allotment Session",
            hidden: 1
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }

        if (column.fieldname === "delta_j_vs_j_1") {
            const pct = Number(value);
            let color = "gray";
            if (pct > 0) {
                color = "green";
            } else if (pct < 0) {
                color = pct <= -15 ? "red" : "orange";
            }
            const sign = pct > 0 ? "+" : "";
            return `<span style="color:${color};font-weight:600">${sign}${pct}%</span>`;
        }

        if (["j_2", "j_1", "j", "moyenne_3j"].includes(column.fieldname)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }

        return default_formatter(value, row, column, data);
    }
};


function is_session_mode(report) {
    return !!report.get_filter_value("session");
}


function open_history_dialog(report) {
    frappe.call({
        method: "hmd_agro.hmd_agro.doctype.allotment_session.allotment_session.list_sessions",
        args: { limit: 50 },
        callback(r) {
            const sessions = r.message || [];
            if (!sessions.length) {
                frappe.msgprint(__("Aucune session enregistrée pour le moment."));
                return;
            }
            const html = `
                <table style="width:100%;font-size:13px;border-collapse:collapse;">
                  <thead>
                    <tr style="border-bottom:1px solid var(--border-color);">
                      <th style="padding:6px;text-align:left;">Date</th>
                      <th style="padding:6px;text-align:left;">Mouvements</th>
                      <th style="padding:6px;text-align:left;">Créée par</th>
                      <th style="padding:6px;text-align:left;">Notes</th>
                      <th style="padding:6px;"></th>
                    </tr>
                  </thead>
                  <tbody>
                  ${sessions.map((s) => `
                    <tr style="border-bottom:1px solid var(--light-border-color);">
                      <td style="padding:6px;">${s.session_date}</td>
                      <td style="padding:6px;">${s.moves_count}</td>
                      <td style="padding:6px;">${s.created_by || ""}</td>
                      <td style="padding:6px;color:var(--text-muted);">${s.notes || ""}</td>
                      <td style="padding:6px;text-align:right;">
                        <button class="btn btn-xs btn-default" data-session="${s.name}" data-date="${s.session_date}">${__("Voir")}</button>
                      </td>
                    </tr>`).join("")}
                  </tbody>
                </table>`;

            const d = new frappe.ui.Dialog({
                title: __("Historique des sessions"),
                size: "large",
                fields: [{ fieldname: "list", fieldtype: "HTML", options: html }]
            });
            d.show();
            d.$wrapper.find("button[data-session]").on("click", function () {
                const name = $(this).data("session");
                const date = $(this).data("date");
                d.hide();
                report.set_filter_value("session", name);
                report.set_filter_value("today_display", date);
                report.refresh();
            });
        }
    });
}


const MOVE_TABLE_FIELDS = [
    { fieldname: "animal", fieldtype: "Link", options: "Animal", label: __("Animal"), hidden: 1 },
    { fieldname: "nom_metier", fieldtype: "Data", label: __("N° Travail"),
      in_list_view: 1, read_only: 1, columns: 2 },
    { fieldname: "lot_actuel", fieldtype: "Data", label: __("Lot actuel"),
      in_list_view: 1, read_only: 1, columns: 2 },
    { fieldname: "lot_destination", fieldtype: "Link", options: "Lot",
      label: __("Lot destination"), in_list_view: 1, columns: 2 }
];

// DIM stage boundaries — must mirror Python `_get_suggestion`.
// Used only for the Consideration column to detect "last third of stage".
const LOT_DIM_RANGE_MULTI = {
    FV: [0, 30], THP: [30, 120], HP: [120, 240], MP: [240, 305], FP: [305, 9999]
};
const LOT_DIM_RANGE_PRIMI = { FV: [0, 300], FP: [300, 9999] };
const LOT_DEMOTE_NEXT_MULTI = { FV: "THP", THP: "HP", HP: "MP", MP: "FP" };
const LOT_DEMOTE_NEXT_PRIMI = { FV: "FP" };
// Stage progression rank: cows advance through these stages with DIM.
// Used to distinguish demote (target rank > current) from promote (target rank < current).
// TARISSEMENT/TARIE are after FP in the lifecycle; included here so the rank
// comparison classifies FP→TARISSEMENT as "demote" (always shown, never suppressed).
const LOT_RANK = { FV: 1, THP: 2, HP: 3, MP: 4, FP: 5, TARISSEMENT: 6, TARIE: 7 };

function get_lot_dim_range(lot_type, numero_lactation) {
    const map = (numero_lactation === 1) ? LOT_DIM_RANGE_PRIMI : LOT_DIM_RANGE_MULTI;
    return map[lot_type] || null;
}

function get_next_lot_type(lot_type, numero_lactation) {
    const map = (numero_lactation === 1) ? LOT_DEMOTE_NEXT_PRIMI : LOT_DEMOTE_NEXT_MULTI;
    return map[lot_type] || null;
}

function compute_consideration(row, lots_by_name, current_seuils) {
    // Consideration = production OVERRIDES the DIM rule.
    // No flag when DIM and production agree.
    const cur_lot = lots_by_name[row.lot_actuel];
    if (!cur_lot) return { color: "", text: "", sortKey: 2 };
    const seuil_cur = current_seuils[row.lot_actuel] || cur_lot.seuil_production_3j || 0;
    const prod = Number(row.moyenne_3j || 0);
    if (!prod) return { color: "", text: "", sortKey: 2 };

    const dim_says_move = !!(row.suggestion_lot && row.suggestion_lot !== row.lot_actuel);

    // ── DIM-mismatch row: green if production wants to KEEP (override DIM move) ──
    if (dim_says_move) {
        if (!seuil_cur) return { color: "", text: "", sortKey: 2 };
        const tgt_lot = lots_by_name[row.suggestion_lot];
        const seuil_tgt = tgt_lot
            ? (current_seuils[row.suggestion_lot] || tgt_lot.seuil_production_3j || 0)
            : 0;
        const cur_rank = LOT_RANK[cur_lot.lot_type] || 0;
        const tgt_rank = tgt_lot ? (LOT_RANK[tgt_lot.lot_type] || 0) : 0;

        // Demote (DIM advances cow to next stage): override = production justifies CURRENT
        if (tgt_rank > cur_rank && prod >= seuil_cur) {
            return {
                color: "green",
                subType: "demote_keep",
                text: `Peut rester (${prod.toFixed(1)} ≥ ${seuil_cur.toFixed(1)} en ${cur_lot.lot_type})`,
                sortKey: 1,
            };
        }
        // Promote (cow placed in lower-tier than DIM says): override = not ready for TARGET.
        // build_suggestion_items SUPPRESSES this case entirely (production is ratchet:
        // a cow whose prod fell below seuil rarely climbs back, so DIM-driven re-promotion
        // would just nag forever).
        if (tgt_rank < cur_rank && seuil_tgt && prod < seuil_tgt) {
            return {
                color: "green",
                subType: "promote_not_ready",
                text: `Pas prête pour ${tgt_lot.lot_type} (${prod.toFixed(1)} < ${seuil_tgt.toFixed(1)}), garder en ${cur_lot.lot_type}`,
                sortKey: 1,
            };
        }
        // DIM and production agree → no consideration
        return { color: "", text: "", sortKey: 2 };
    }

    // ── DIM says stay: yellow if production wants to DEMOTE early ──
    if (!seuil_cur) return { color: "", text: "", sortKey: 2 };
    if (prod < seuil_cur) {
        const range = get_lot_dim_range(cur_lot.lot_type, row.numero_lactation);
        if (range && row.dim != null) {
            const [lo, hi] = range;
            const last_third_start = lo + (2 / 3) * (hi - lo);
            if (Number(row.dim) >= last_third_start) {
                return {
                    color: "yellow",
                    subType: "yellow_demote",
                    text: `Démettre tôt (${prod.toFixed(1)} < ${seuil_cur.toFixed(1)}, fin de stage)`,
                    sortKey: 0,
                };
            }
        }
    }

    return { color: "", text: "", sortKey: 2 };
}


// Build the rows that should appear in the Suggestions dialog table.
// Inclusion rule: include if DIM rule wants to move OR consideration is yellow.
// Sort: yellow first, green next, neutral last.
function build_suggestion_items(allRows, lots, lots_by_name, current_seuils) {
    const items = [];
    allRows.forEach((row) => {
        const cons = compute_consideration(row, lots_by_name, current_seuils);
        const dim_moves = !!(row.suggestion_lot && row.suggestion_lot !== row.lot_actuel);
        if (dim_moves) {
            // Production ratchet: a DIM-promote suggestion the cow can't fulfill is futile.
            if (cons.subType === "promote_not_ready") return;
            items.push({ row, lot_destination: row.suggestion_lot, cons, source: "dim" });
        } else if (cons.color === "yellow") {
            const cur_type = (lots_by_name[row.lot_actuel] || {}).lot_type;
            const next_type = get_next_lot_type(cur_type, row.numero_lactation);
            const next_lot = next_type
                ? (lots.find((l) => l.lot_type === next_type) || {}).name || ""
                : "";
            items.push({ row, lot_destination: next_lot, cons, source: "prod" });
        }
    });
    items.sort((a, b) => a.cons.sortKey - b.cons.sortKey);
    return items.map((it) => ({
        animal: it.row.animal,
        nom_metier: it.row.nom_metier,
        lot_actuel: it.row.lot_actuel,
        lot_destination: it.lot_destination,
        consideration: it.cons.text,
        _source: it.source,
        _cons_color: it.cons.color,
    }));
}


function open_suggestion_dialog(report, allRows) {
    frappe.call({
        method: "hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux.get_lots_capacity",
        callback(r) {
            const lots = r.message || [];
            const lots_by_name = Object.fromEntries(lots.map((l) => [l.name, l]));
            const table_data = build_suggestion_items(allRows, lots, lots_by_name, {});

            if (!table_data.length) {
                frappe.msgprint(__("Aucune suggestion disponible pour le moment."));
                return;
            }

            _build_moves_dialog(report, {
                title: __("Suggestions de mouvements"),
                help: __("<b>Jaune</b> : suggestion de la production. <b>Rouge</b> : suggestion du DIM, mais la production veut garder l'animal. <b>Blanc</b> : suggestion du DIM seul."),
                table_data,
                lots,
                with_consideration: true,
            });
        }
    });
}


function open_manual_dialog(report, rows) {
    const table_data = rows.map((r) => ({
        animal: r.animal,
        nom_metier: r.nom_metier,
        lot_actuel: r.lot_actuel,
        lot_destination: ""
    }));
    _open_moves_dialog(report, {
        title: __("Mouvements manuels"),
        help: __("Renseignez le lot destination (manuellement ou via 'Appliquer lot commun' sur les animaux cochés), cochez les lignes à déplacer, puis confirmez."),
        table_data
    });
}


function _open_moves_dialog(report, { title, help, table_data }) {
    frappe.call({
        method: "hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux.get_lots_capacity",
        callback(r) {
            const lots = r.message || [];
            _build_moves_dialog(report, { title, help, table_data, lots, with_consideration: false });
        }
    });
}


function _build_moves_dialog(report, { title, help, table_data, lots, with_consideration }) {
    const fields_for_grid = with_consideration
        ? [...MOVE_TABLE_FIELDS, {
            fieldname: "consideration", fieldtype: "Data",
            label: __("Considération"), in_list_view: 1, read_only: 1, columns: 4
          }]
        : MOVE_TABLE_FIELDS;

    const d = new frappe.ui.Dialog({
        title,
        size: "extra-large",
        fields: [
            { fieldname: "capacity_preview", fieldtype: "HTML",
              options: render_capacity_table(lots, new Map(), {}, with_consideration) },
            { fieldname: "btn_refresh", fieldtype: "Button",
              label: __("Actualiser capacité"),
              click() { actualiser(d); } },
            { fieldname: "help", fieldtype: "HTML",
              options: `<div style="margin:8px 0;color:var(--text-muted);font-size:13px;">${help}</div>` },
            { fieldname: "lot_destination_bulk", fieldtype: "Link",
              label: __("Lot commun"), options: "Lot" },
            { fieldname: "btn_apply_bulk", fieldtype: "Button",
              label: __("Appliquer lot commun"),
              click() { apply_common_lot(d); } },
            { fieldname: "moves", fieldtype: "Table",
              label: __("Mouvements"),
              cannot_add_rows: true, cannot_delete_rows: true, in_place_edit: true, reqd: 1,
              fields: fields_for_grid, data: table_data }
        ],
        primary_action_label: __("Confirmer transfert"),
        primary_action() { confirm_transfer(d, report); }
    });
    d.user_data = { lots, with_consideration };
    d.show();
    if (with_consideration) apply_row_colors(d);
}


function apply_common_lot(d) {
    const lot = d.get_value("lot_destination_bulk");
    if (!lot) { frappe.msgprint(__("Sélectionnez un lot commun.")); return; }
    const checked = checked_rows(d);
    if (!checked.length) { frappe.msgprint(__("Cochez les animaux à modifier.")); return; }
    const names = new Set(checked.map((doc) => doc.animal));
    d.fields_dict.moves.grid.grid_rows.forEach((row) => {
        if (names.has(row.doc.animal)) {
            row.doc.lot_destination = lot;
            row.refresh_field("lot_destination");
        }
    });
    refresh_capacity(d);
}


function confirm_transfer(d, report) {
    const toMove = checked_rows(d).filter((doc) =>
        doc.lot_destination && doc.lot_destination !== doc.lot_actuel
    );
    if (!toMove.length) {
        frappe.msgprint(__("Cochez des animaux avec un lot destination différent de leur lot actuel."));
        return;
    }
    apply_moves(d, report, toMove);
}


function checked_rows(d) {
    // blur() commits any in-flight cell edit before reading selection.
    if (document.activeElement) document.activeElement.blur();
    return d.fields_dict.moves.grid.get_selected_children() || [];
}


function compute_pending_deltas(d) {
    const deltas = new Map();
    checked_rows(d).forEach((doc) => {
        const dest = doc.lot_destination;
        const cur = doc.lot_actuel;
        if (!dest || dest === cur) return;
        if (cur) deltas.set(cur, (deltas.get(cur) || 0) - 1);
        deltas.set(dest, (deltas.get(dest) || 0) + 1);
    });
    return deltas;
}


// Read current seuil DOM values — used to preserve user edits across re-renders.
function read_seuil_inputs(d) {
    const seuils = {};
    d.fields_dict.capacity_preview.$wrapper.find("input.lot-seuil-input").each(function () {
        const lot = $(this).data("lot");
        const val = parseFloat($(this).val());
        seuils[lot] = isNaN(val) ? 0 : val;
    });
    return seuils;
}


// Re-render capacity preview without saving. Used after pending-deltas change.
function refresh_capacity(d) {
    const lots = (d.user_data || {}).lots || [];
    const with_consideration = (d.user_data || {}).with_consideration || false;
    const current_seuils = read_seuil_inputs(d);
    const deltas = compute_pending_deltas(d);
    const html = render_capacity_table(lots, deltas, current_seuils, with_consideration);
    d.fields_dict.capacity_preview.$wrapper.html(html);
}


// Save edited seuils to DB → re-fetch lots → re-render capacity preview
// AND fully rebuild the Suggestions grid (rows can appear/disappear when
// seuils change, so just updating the consideration text isn't enough).
function actualiser(d) {
    const with_consideration = (d.user_data || {}).with_consideration || false;
    const seuils = read_seuil_inputs(d);

    const after_save = () => {
        frappe.call({
            method: "hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux.get_lots_capacity",
            callback(r) {
                const lots = r.message || [];
                d.user_data.lots = lots;
                refresh_capacity(d);
                if (with_consideration) {
                    rebuild_suggestion_grid(d, lots);
                }
            }
        });
    };

    if (with_consideration && Object.keys(seuils).length) {
        frappe.call({
            method: "hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux.update_lot_seuils",
            args: { seuils: JSON.stringify(seuils) },
            callback() { after_save(); }
        });
    } else {
        after_save();
    }
}


// Rebuild the Suggestions grid from scratch using current lots/seuils.
// Preserves checkbox selections for animals that still appear in the new grid:
// Frappe's grid reads `doc.__checked` to render the checkbox state, so we set
// it on the new data BEFORE refresh — no DOM manipulation, no timing hacks.
function rebuild_suggestion_grid(d, lots) {
    const field = d.fields_dict.moves;
    const checked_animals = new Set(
        (field.grid.get_selected_children() || []).map((row) => row.animal)
    );

    const lots_by_name = Object.fromEntries(lots.map((l) => [l.name, l]));
    const allRows = (frappe.query_report.data || []).filter((r) => r.animal);
    const table_data = build_suggestion_items(allRows, lots, lots_by_name, {});

    table_data.forEach((row) => {
        if (checked_animals.has(row.animal)) row.__checked = 1;
    });

    field.df.data = table_data;
    field.grid.df.data = table_data;
    field.grid.refresh();
    apply_row_colors(d);
}


// Color the considération + destination cells based on signal source.
// Tone: red = production says "garder" (overrides DIM move).
//       yellow = production says "demote" OR destination came from production.
function apply_row_colors(d) {
    const field = d.fields_dict.moves;
    if (!field || !field.grid) return;
    setTimeout(() => {
        (field.grid.grid_rows || []).forEach((gr) => {
            if (!gr.doc || !gr.wrapper) return;
            const cons_color = gr.doc._cons_color || "";
            const source = gr.doc._source || "";
            const cons_bg = cons_color === "green" ? "#f8d7da"
                          : cons_color === "yellow" ? "#fff3cd"
                          : "";
            const dest_bg = source === "prod" ? "#fff3cd" : "";
            const consCell = gr.wrapper.find('[data-fieldname="consideration"]');
            const destCell = gr.wrapper.find('[data-fieldname="lot_destination"]');
            if (consCell.length) consCell.css("background-color", cons_bg);
            if (destCell.length) destCell.css("background-color", dest_bg);
        });
    }, 30);
}


function render_capacity_table(lots, deltas, current_seuils, show_seuil_row) {
    if (!lots.length) {
        return '<div style="color:var(--text-muted);font-size:13px;">Aucun lot actif.</div>';
    }
    const cellStyle = "padding:5px 8px;border:1px solid var(--border-color);text-align:center;font-size:12px;white-space:nowrap;";
    const headerStyle = cellStyle + "background:var(--fg-color);font-weight:600;";
    const rowLabel = "padding:5px 8px;border:1px solid var(--border-color);font-size:12px;font-weight:600;background:var(--fg-color);text-align:left;";

    const headerCells = lots.map((l) => {
        const label = l.name + (l.lot_type ? `<br><span style="font-size:10px;color:var(--text-muted);">${l.lot_type}</span>` : "");
        return `<th style="${headerStyle}">${label}</th>`;
    }).join("");

    const effectifCells = lots.map((l) => {
        const delta = deltas.get(l.name) || 0;
        const after = (l.nb_animaux || 0) + delta;
        const opt = l.capacite_optimale || 0;
        const max = l.capacite_maximale || 0;
        let color = "";
        if (max && after > max) color = "background:#fee;color:#c00;font-weight:600;";
        else if (opt && after > opt) color = "background:#ffe;color:#c80;font-weight:600;";
        const arrow = delta !== 0 ? `<span style="color:var(--text-muted);"> (${delta > 0 ? "+" : ""}${delta})</span>` : "";
        return `<td style="${cellStyle}${color}">${after}${arrow}</td>`;
    }).join("");

    const capacityCells = lots.map((l) => {
        const opt = l.capacite_optimale || 0;
        const max = l.capacite_maximale || 0;
        return `<td style="${cellStyle}">${opt} / ${max}</td>`;
    }).join("");

    const hpCells = lots.map((l) => {
        const flag = l.adapte_hautes_performances
            ? '<span style="color:#080;">✓</span>'
            : '<span style="color:#aaa;">✗</span>';
        return `<td style="${cellStyle}">${flag}</td>`;
    }).join("");

    // Seuil row: editable, only rendered in the Suggestions dialog.
    let seuilRow = "";
    if (show_seuil_row) {
        const seuilCells = lots.map((l) => {
            const edited = (current_seuils || {})[l.name];
            const stored = l.seuil_production_3j;
            const val = (edited !== undefined && edited !== null) ? edited : (stored || "");
            const display = (val === "" || val === 0) ? "" : String(val);
            return `<td style="${cellStyle}padding:2px 4px;">
                <input type="number" data-lot="${l.name}" class="lot-seuil-input"
                    value="${display}" step="0.5" min="0"
                    style="width:60px;padding:3px 5px;font-size:12px;text-align:right;border:1px solid var(--border-color);border-radius:3px;">
            </td>`;
        }).join("");
        seuilRow = `<tr><td style="${rowLabel}">Seuil prod. 3j (L)</td>${seuilCells}</tr>`;
    }

    return `
        <div style="overflow-x:auto;margin-bottom:6px;">
        <table style="border-collapse:collapse;width:100%;">
          <thead><tr><th style="${headerStyle}"></th>${headerCells}</tr></thead>
          <tbody>
            <tr><td style="${rowLabel}">Effectif</td>${effectifCells}</tr>
            <tr><td style="${rowLabel}">Capacité (opt / max)</td>${capacityCells}</tr>
            <tr><td style="${rowLabel}">Hautes perf.</td>${hpCells}</tr>
            ${seuilRow}
          </tbody>
        </table>
        </div>`;
}


function apply_moves(dialog, report, toMove) {
    dialog.disable_primary_action();
    frappe.call({
        method: "frappe.client.bulk_update",
        args: {
            docs: JSON.stringify(
                toMove.map((r) => ({
                    doctype: "Animal",
                    docname: r.animal,
                    id_lot: r.lot_destination
                }))
            )
        },
        freeze: true,
        freeze_message: __("Application des mouvements..."),
        callback(res) {
            const failed = (res.message && res.message.failed_docs) || [];
            const failedNames = new Set(failed.map((f) => f.name || f.docname));
            const succeeded = toMove.filter((r) => !failedNames.has(r.animal));

            // Snapshot = full report grid + the moves just applied. Session dates to today.
            const sessionDate = frappe.datetime.get_today();
            const allRows = (frappe.query_report.data || []).filter((r) => r.animal);
            const movedMap = new Map(succeeded.map((r) => [r.animal, r.lot_destination]));
            const snapshot = allRows.map((r) => ({
                animal: r.animal,
                nom_metier: r.nom_metier,
                lot_before: r.lot_actuel,
                lot_after: movedMap.get(r.animal) || r.lot_actuel,
                dim: r.dim,
                jours_gestation: r.jours_gestation,
                production_j_2: r.j_2,
                production_j_1: r.j_1,
                production_j: r.j,
                delta: r.delta_j_vs_j_1,
                moyenne_3j: r.moyenne_3j,
                suggestion: r.suggestion_lot
            }));

            frappe.call({
                method: "hmd_agro.hmd_agro.doctype.allotment_session.allotment_session.confirm_session",
                args: {
                    session_date: sessionDate,
                    rows: JSON.stringify(snapshot)
                },
                callback() {
                    dialog.hide();
                    if (failed.length) {
                        frappe.msgprint(
                            __("{0} mouvement(s) appliqué(s), {1} erreur(s). Session enregistrée.",
                                [succeeded.length, failed.length])
                        );
                    } else {
                        frappe.show_alert({
                            message: __("{0} mouvement(s) appliqué(s). Session enregistrée.",
                                [succeeded.length]),
                            indicator: "green"
                        });
                    }
                    report.refresh();
                }
            });
        }
    });
}
