// SCRUM-10 — Clé de répartition (Cost Center Allocation ERPNext).
// Une NOUVELLE clé arrive pré-remplie : centre Frais Généraux, première date
// qu'ERPNext acceptera (après la dernière écriture du centre), une ligne par
// centre de coûts d'atelier. L'administrateur ne tape que les pourcentages
// (M. Samir, 26/08 : « on le fera une seule fois » ; décision du 04/09 : le
// plus simple pour l'utilisateur). Le serveur (`proposer_cle`) reste seul à
// connaître la règle de date ; ici on ne fait que remplir le formulaire.
frappe.ui.form.on("Cost Center Allocation", {
    onload(frm) {
        if (!frm.is_new() || frm.hmd_prerempli) return;
        frm.hmd_prerempli = true;
        frappe.call({
            method: "hmd_agro.hmd_agro.utils.repartition_charges.proposer_cle",
            args: {company: frm.doc.company || null},
            callback: (r) => {
                const p = r.message;
                if (!p || !p.main_cost_center) return;
                if (!frm.doc.company) frm.set_value("company", p.company);
                if (!frm.doc.main_cost_center) {
                    frm.set_value("main_cost_center", p.main_cost_center);
                }
                frm.set_value("valid_from", p.valid_from);
                // Frappe adds one blank row to a mandatory table on a new
                // document : only rows naming a cost center count as typed in.
                const saisies = (frm.doc.allocation_percentages || [])
                    .filter((ligne) => ligne.cost_center);
                if (!saisies.length) {
                    frm.clear_table("allocation_percentages");
                    p.ateliers.forEach((cc) => {
                        frm.add_child("allocation_percentages", {cost_center: cc});
                    });
                    frm.refresh_field("allocation_percentages");
                }
                frm.hmd_proposition = p;
                hmd_cle_allocation.bandeau(frm);
            },
        });
    },
    refresh(frm) { hmd_cle_allocation.bandeau(frm); },
});

window.hmd_cle_allocation = {
    bandeau(frm) {
        const p = frm.hmd_proposition;
        if (!frm.is_new() || !p) return;
        const date = frappe.datetime.str_to_user(p.valid_from);
        const regle = p.derniere_ecriture
            ? __("dernière écriture sur {0} le {1} — ERPNext refuse une clé datée avant",
                 [p.centre, p.derniere_ecriture])
            : __("aucune écriture sur {0} pour l'instant", [p.centre]);
        frm.dashboard.set_headline_alert(
            __("Clé pré-remplie : {0}, valide à partir du <b>{1}</b> ({2}). "
               + "Saisir les pourcentages — total 100 — puis Enregistrer et Valider. "
               + "La clé s'applique à chaque pièce à partir de cette date, sans rien "
               + "saisir sur la pièce.", [p.centre, date, regle]),
            "blue");
    },
};
