frappe.ui.form.on("Animal", {
    refresh(frm) {
        frm.trigger("toggle_fields_visibility");
        frm.trigger("set_link_filters");
        
        // Activity buttons
        if (!frm.is_new() && ["VACHE", "GENISSE"].includes(frm.doc.categorie)) {
            // Insémination button with validation
            frm.add_custom_button(__("Insémination"), function() {
                frappe.call({
                    method: "frappe.client.get_count",
                    args: {
                        doctype: "Insemination",
                        filters: {
                            animal: frm.doc.name,
                            resultat: "EN_ATTENTE"
                        }
                    },
                    callback: function(r) {
                        if (r.message > 0) {
                            frappe.msgprint(__("Cet animal a déjà une insémination en attente."));
                        } else {
                            frappe.route_options = {
                                animal: frm.doc.name
                            };
                            frappe.new_doc("Insemination");
                        }
                    }
                });
            }, __("Activité"));
            frm.add_custom_button(__("Velage"), function() {
                if (frm.doc.etat_gestation !== "GESTANTE") {
                    frappe.msgprint(__("Cet animal n'est pas gestante. Vêlage impossible."));
                } else {
                frappe.route_options={
                    animal: frm.doc.name,
                };
                frappe.new_doc("Velage");
                }
            }, __("Activité"));
            frm.add_custom_button(__("Avortement"), function() {
                if (frm.doc.etat_gestation !== "GESTANTE") {
                    frappe.msgprint(__("Cet animal n'est pas gestante. Avortement impossible."));
                } else {
                    frappe.route_options = {
                        animal: frm.doc.name,
                    };
                    frappe.new_doc("Avortement");
                }
            }, __("Activité"));
            // Load reproduction dashboard
            frm.trigger("load_repro_dashboard");
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Pesée"), function() {
                frappe.route_options = { animal: frm.doc.name };
                frappe.new_doc("Pesee");
            }, __("Activité"));

            frm.add_custom_button(__("État Corporel"), function() {
                frappe.route_options = { animal: frm.doc.name };
                frappe.new_doc("Etat Corporel");
            }, __("Activité"));
        }
        
    },

    load_repro_dashboard(frm) {
        frappe.call({
            method: "hmd_agro.hmd_agro.doctype.animal.animal.get_reproduction_dashboard",
            args: { animal: frm.doc.name },
            callback: function(r) {
                if (r.message) {
                    render_repro_dashboard(frm, r.message);
                }
            }
        });
    },

    categorie(frm) {
        const femelles = ["VACHE", "GENISSE", "VELLE"];
        const males = ["VEAU", "TAURILLON"];

        if (femelles.includes(frm.doc.categorie)) {
            frm.set_value("sexe", "F");
        } else if (males.includes(frm.doc.categorie)) {
            frm.set_value("sexe", "M");
        }

        frm.trigger("toggle_fields_visibility");
    },
    statut(frm) {
        frm.trigger("toggle_fields_visibility");
    },

    toggle_fields_visibility(frm) {
        const is_vache = frm.doc.categorie === "VACHE";
        const is_repro = ["VACHE", "GENISSE"].includes(frm.doc.categorie);

        frm.set_df_property("section_dashboard_repro", "hidden", !is_repro);  
        frm.set_df_property("etat_gestation", "hidden", !is_repro);
        frm.set_df_property("etat_lactation", "hidden", !is_vache);
        frm.set_df_property("date_sortie", "hidden", frm.is_new() || frm.doc.statut === "ACTIF");

        // Show "Non évalué" / "Non pesé" instead of 0
        if (!frm.is_new()) {
            frm.refresh_field("etat_corporel");
            frm.refresh_field("dernier_poids");
            setTimeout(() => {
                if (!frm.doc.etat_corporel) {
                    frm.fields_dict.etat_corporel.$wrapper
                        .find(".like-disabled-input, .control-value").text("Non évalué");
                }
                if (!frm.doc.dernier_poids) {
                    frm.fields_dict.dernier_poids.$wrapper
                        .find(".like-disabled-input, .control-value").text("Non pesé");
                }
            }, 100);
        }
    },

    set_link_filters(frm) {
        frm.set_query("id_mere", function () {
            return {
                filters: {
                    categorie:"VACHE",
                    statut: "ACTIF",
                    name: ["!=", frm.doc.name || ""]
                }
            };
        });

        frm.set_query("id_lot", function () {
            return {
                filters: {
                    actif: 1
                }
            };
        });
    }
});


function render_repro_dashboard(frm, data) {
    let html = `<div class="repro-dashboard" style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:15px;">`;
    
    // ── Card 1: Current Lactation ──
    if (data.current_lactation) {
        let lac = data.current_lactation;
        html += `
        <div class="repro-card" style="flex:1; min-width:200px; border:1px solid var(--border-color); border-radius:8px; padding:15px; background:var(--card-bg);">
            <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px;">Lactation en cours</div>
            <div style="font-size:22px; font-weight:600;">N° ${lac.numero_lactation}</div>
            <div style="margin-top:8px; font-size:13px; color:var(--text-muted);">
                <div>Début: ${frappe.datetime.str_to_user(lac.date_debut)}</div>
                <div>DIM: <strong>${lac.jours_lactation || 0} jours</strong></div>
                <div>IA: ${lac.nb_inseminations || 0}</div>
            </div>
            <div style="margin-top:10px;">
                <a class="btn btn-xs btn-default" href="/app/lactation/${lac.name}">Voir détails</a>
            </div>
        </div>`;
    } else {
        html += `
        <div class="repro-card" style="flex:1; min-width:200px; border:1px solid var(--border-color); border-radius:8px; padding:15px; background:var(--card-bg);">
            <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px;">Lactation en cours</div>
            <div style="font-size:16px; color:var(--text-muted);">Aucune</div>
        </div>`;
    }
    
    // ── Card 2: Insémination Status ──
    html += `
    <div class="repro-card" style="flex:1; min-width:200px; border:1px solid var(--border-color); border-radius:8px; padding:15px; background:var(--card-bg);">
        <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px;">Insémination</div>`;
    
    if (data.pending_ia) {
        let days_ago = frappe.datetime.get_diff(frappe.datetime.get_today(), data.pending_ia.date_ia);
        let color = days_ago >= 21 ? "orange" : "blue";
        html += `
        <div style="font-size:14px;">
            <span class="indicator-pill ${color}">EN ATTENTE</span>
        </div>
        <div style="margin-top:8px; font-size:13px; color:var(--text-muted);">
            <div>Date: ${frappe.datetime.str_to_user(data.pending_ia.date_ia)}</div>
            <div>Il y a ${days_ago} jours</div>
            ${data.pending_ia.taureau ? '<div>Taureau: ' + data.pending_ia.taureau + '</div>' : ''}
        </div>
        <div style="margin-top:10px;">
            <a class="btn btn-xs btn-default" href="/app/insemination/${data.pending_ia.name}">Voir IA</a>
        </div>`;
    } else {
        html += `
        <div style="font-size:14px; color:var(--text-muted);">Aucune IA en attente</div>
        <div style="margin-top:8px; font-size:13px; color:var(--text-muted);">
            Total IA: ${data.total_ia || 0}
        </div>`;
        
        if (data.last_ia) {
            let badge_color = data.last_ia.resultat === "REUSSIE" ? "green" : "red";
            html += `
            <div style="margin-top:5px; font-size:13px;">
                Dernière: <span class="indicator-pill ${badge_color}">${data.last_ia.resultat}</span>
            </div>`;
        }
    }
    html += `</div>`;
    
    // ── Card 3: Lactation History ──
    html += `
    <div class="repro-card" style="flex:1; min-width:200px; border:1px solid var(--border-color); border-radius:8px; padding:15px; background:var(--card-bg);">
        <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px;">Historique Lactations</div>
        <div style="font-size:22px; font-weight:600;">${data.lactations.length}</div>
        <div style="font-size:13px; color:var(--text-muted); margin-bottom:8px;">lactation(s)</div>`;
    
    if (data.lactations.length > 0) {
        html += `<table style="width:100%; font-size:12px; border-collapse:collapse;">
            <tr style="border-bottom:1px solid var(--border-color);">
                <th style="padding:4px 0; text-align:left;">N°</th>
                <th style="padding:4px 0; text-align:left;">IA</th>
                <th style="padding:4px 0; text-align:left;">Jours</th>
                <th style="padding:4px 0; text-align:left;">Statut</th>
            </tr>`;
        
        data.lactations.forEach(function(lac) {
            let statut_color = lac.statut === "EN_COURS" ? "green" : "gray";
            html += `
            <tr style="border-bottom:1px solid var(--light-border-color);">
                <td style="padding:4px 0;"><a href="/app/lactation/${lac.name}">${lac.numero_lactation}</a></td>
                <td style="padding:4px 0;">${lac.nb_inseminations || 0}</td>
                <td style="padding:4px 0;">${lac.jours_lactation || '-'}</td>
                <td style="padding:4px 0;"><span class="indicator-pill ${statut_color}" style="font-size:10px;">${lac.statut}</span></td>
            </tr>`;
        });
        
        html += `</table>`;
    }
    
    html += `</div>`;
    
    html += `</div>`; // close .repro-dashboard
    
    frm.fields_dict.dashboard_repro.$wrapper.html(html);
}