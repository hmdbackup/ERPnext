// SCRUM-11 — fiche d'intervention (Asset Repair) : état lisible dans l'en-tête,
// bouton « Planifier la prochaine », un seul intervenant, coût = pièces + M.O.
// Aucune règle métier ici qui n'existe pas côté serveur
// (utils/maintenance_utils.py, ERR-MNT-09 → 13) : le client ne fait que
// refléter, pour que l'utilisateur voie avant d'enregistrer.

// Statut ERPNext → ce que lit le chef de parc (miroir de `etat_fiche`).
const HMD_ETATS_FICHE = {
    Planned: {libelle: "À venir", couleur: "blue"},
    Pending: {libelle: "En attente", couleur: "orange"},
    Completed: {libelle: "Terminée", couleur: "green"},
    Cancelled: {libelle: "Annulée", couleur: "red"},
};
const HMD_STATUT_TERMINEE = "Completed";
const HMD_STATUT_PLANIFIEE = "Planned";
const HMD_STATUT_EN_ATTENTE = "Pending";
const HMD_AIDE_STATUT = "Choisir le statut : En attente (Pending) = panne déclarée, "
    + "l'équipement passe hors service · Planned = intervention à venir.";
const HMD_METHODE_PLANIFIER = "hmd_agro.hmd_agro.utils.maintenance_utils.planifier_intervention";

frappe.ui.form.on("Asset Repair", {
    setup(frm) {
        frm.set_query("prestataire", () => ({filters: {disabled: 0}}));
        // Le coût peut venir des champs Pièces / M.O. sans facture rattachée
        // (hook serveur `completer_couts_fiche`) : ERPNext n'a donc plus à
        // exiger la facture dès qu'un coût est saisi sur une fiche Terminée.
        frm.set_df_property("purchase_invoice", "mandatory_depends_on", "");
    },

    refresh(frm) {
        hmd_statut_nouvelle_fiche(frm);
        hmd_afficher_etat(frm);
        hmd_bouton_planifier(frm);
    },

    // Un seul intervenant (ERR-MNT-09) : saisir l'un vide l'autre.
    personnel(frm) {
        if (frm.doc.personnel && frm.doc.prestataire) {
            frm.set_value("prestataire", null);
        }
    },
    prestataire(frm) {
        if (frm.doc.prestataire && frm.doc.personnel) {
            frm.set_value("personnel", null);
        }
    },

    cout_pieces: hmd_recalculer_cout,
    cout_main_oeuvre: hmd_recalculer_cout,
});

// Fiche nouvelle : le statut est visible (Property Setter depends_on vidé)
// et expliqué. Une fiche issue de « Dupliquer » arrive avec équipement et
// description déjà remplis mais un statut remis à « Pending » (no_copy) : on
// propose « Planned » pour ne pas mettre l'équipement hors service au premier
// enregistrement. Une déclaration de panne (fiche vierge) garde « Pending ».
function hmd_statut_nouvelle_fiche(frm) {
    if (!frm.is_new() || frm.doc.amended_from) return;
    frm.set_df_property("repair_status", "description", __(HMD_AIDE_STATUT));
    const copie = frm.doc.__islocal && frm.doc.asset && frm.doc.description;
    const statut_vide = !frm.doc.repair_status || frm.doc.repair_status === HMD_STATUT_EN_ATTENTE;
    if (copie && statut_vide && !frm.__hmd_statut_propose) {
        frm.__hmd_statut_propose = true;
        frm.set_value("repair_status", HMD_STATUT_PLANIFIEE);
    }
}

function hmd_afficher_etat(frm) {
    // Un document nouveau ou modifié garde l'indicateur Frappe (« Non enregistré »).
    if (frm.is_new() || frm.is_dirty()) return;
    const etat = frm.doc.docstatus === 2
        ? HMD_ETATS_FICHE.Cancelled
        : HMD_ETATS_FICHE[frm.doc.repair_status];
    if (etat) frm.page.set_indicator(__(etat.libelle), etat.couleur);
}

function hmd_bouton_planifier(frm) {
    if (frm.doc.docstatus !== 1 || frm.doc.repair_status !== HMD_STATUT_TERMINEE) return;
    frm.add_custom_button(__("Planifier la prochaine"), () => hmd_dialogue_planifier(frm));
}

function hmd_dialogue_planifier(frm) {
    const dialogue = new frappe.ui.Dialog({
        title: __("Planifier la prochaine intervention"),
        fields: [
            {fieldname: "date_prevue", label: __("Date prévue"), fieldtype: "Date", reqd: 1},
            {
                fieldname: "description",
                label: __("Libellé"),
                fieldtype: "Data",
                description: __("Vide : « Prochaine : {0} »", [frm.doc.description || frm.doc.asset_name]),
            },
        ],
        primary_action_label: __("Créer la fiche"),
        primary_action(valeurs) {
            frappe.call({
                method: HMD_METHODE_PLANIFIER,
                args: {
                    source: frm.doc.name,
                    date_prevue: valeurs.date_prevue,
                    description: valeurs.description,
                },
                callback(r) {
                    if (!r.message) return;
                    dialogue.hide();
                    frappe.set_route("Form", "Asset Repair", r.message);
                },
            });
        },
    });
    dialogue.show();
}

// Miroir du hook serveur `completer_couts_fiche` : sans facture rattachée, le
// coût de réparation = pièces + main-d'œuvre ; sans pièces ni M.O., on ne
// touche pas au coût existant.
function hmd_recalculer_cout(frm) {
    if (frm.doc.purchase_invoice) return;
    if (!frm.doc.cout_pieces && !frm.doc.cout_main_oeuvre) return;
    frm.set_value("repair_cost", flt(frm.doc.cout_pieces) + flt(frm.doc.cout_main_oeuvre));
}
