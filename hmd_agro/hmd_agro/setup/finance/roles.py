"""
EPIC G — Séparation des tâches (FIN-S61).

Creates the « Éleveur HMD » role: full day-to-day access to the herd
DocTypes (saisie terrain) but NO accounting permissions — an éleveur can
neither create nor submit a Journal Entry / facture. Accounting stays with
the standard ERPNext roles (« Accounts User » saisie, « Accounts Manager »
validation), assigned to the comptable via User → Roles.

Idempotent — re-run safe.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.roles.setup_roles
"""
import frappe

ROLE_ELEVEUR = "Éleveur HMD"

# Herd DocTypes an éleveur works with daily (saisie + consultation)
ELEVEUR_DOCTYPES = [
    "Animal", "Lactation", "Traite", "Insemination", "Velage", "Avortement",
    "Alerte", "Lot", "Batiment", "Pesee", "Etat Corporel", "Semence",
    "Taureau", "Mere externe", "Traitement", "Medicament", "Aliment",
    "Ration", "Bilan Lait Journalier", "Note Mobilite",
]
ELEVEUR_PERMS = {"read": 1, "write": 1, "create": 1, "report": 1,
                 "export": 1, "print": 1}


@frappe.whitelist()
def setup_roles():
    print("\n" + "=" * 60)
    print("  EPIC G — Rôles & séparation des tâches (FIN-S61)")
    print("=" * 60)

    if not frappe.db.exists("Role", ROLE_ELEVEUR):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE_ELEVEUR,
                        "desk_access": 1}).insert(ignore_permissions=True)
        print(f"  [create] Role {ROLE_ELEVEUR}")
    else:
        print(f"  [skip]   Role {ROLE_ELEVEUR}")

    from frappe.permissions import add_permission, update_permission_property
    for dt in ELEVEUR_DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            print(f"  [warn]   DocType {dt} introuvable — ignoré")
            continue
        if frappe.db.exists("Custom DocPerm", {"parent": dt, "role": ROLE_ELEVEUR}):
            print(f"  [skip]   {dt}")
            continue
        add_permission(dt, ROLE_ELEVEUR, permlevel=0)
        for ptype, value in ELEVEUR_PERMS.items():
            update_permission_property(dt, ROLE_ELEVEUR, 0, ptype, value)
        print(f"  [create] {dt} → {ROLE_ELEVEUR} (read/write/create)")

    frappe.db.commit()
    print("\n  Rôles OK. Comptable = rôles standards « Accounts User » /")
    print("  « Accounts Manager » (Role Permission Manager, rien à créer).")
    print("=" * 60 + "\n")
