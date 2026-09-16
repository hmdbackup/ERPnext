// OPTIONAL — not applied (the real app must not be modified in this eval).
//
// To surface Vaccination like other animal activities, add this block inside the
// existing `refresh(frm)` handler of:
//   hmd_agro/hmd_agro/doctype/animal/animal.js
// alongside the other `frm.add_custom_button(..., __("Activité"))` calls
// (e.g. just after the "Traitement" button in the `statut === "ACTIF"` branch).

if (!frm.is_new() && frm.doc.statut === "ACTIF") {
    frm.add_custom_button(__("Vaccination"), function() {
        frappe.route_options = { animal: frm.doc.name };
        frappe.new_doc("Vaccination");
    }, __("Activité"));
}
