"""
EPIC D — Interventions & maintenance des équipements (FIN-S32, RC-FIN-54).

Le MCD porte une entité INTERVENTION ; la carte spec→implémentation la
délègue à ERPNext (`Asset Maintenance` / `Asset Maintenance Log` /
`Asset Repair`). Ce module pose le référentiel manquant pour que ces
DocTypes soient utilisables sur la ferme :

  • Asset Maintenance Team « Maintenance HMD » (obligatoire pour planifier),
    peuplée depuis le registre `Personnel` (rôles MAINTENANCE / TRACTORISTE
    ayant un compte utilisateur) — Administrator en secours.
  • Custom Fields sur `Asset Repair` (DocType core — export fixtures par nom) :
      type_intervention  CURATIVE | PREVENTIVE | REVISION | CONTROLE
      personnel          qui est intervenu (Link Personnel)
      reference_hmd      marqueur d'idempotence (imports / seeds)
  • Vérifie que le compte 615 « Entretien et réparations » existe : c'est lui
    qui porte la charge des interventions (`utils/maintenance_utils`).

Rappel ERPNext v15 : un `Asset Repair` NON capitalisé ne produit AUCUNE
écriture comptable — c'est un document de suivi. La charge est postée
séparément par `maintenance_utils.enregistrer_intervention` (615 / 401·54·532),
sinon on suivrait les pannes sans jamais voir leur coût.

Idempotent — re-run safe.

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.setup.finance.maintenance.setup_maintenance
"""
import frappe

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

EQUIPE_MAINTENANCE = "Maintenance HMD"
COMPTE_ENTRETIEN = "615"
ROLES_MAINTENANCE = ("MAINTENANCE", "TRACTORISTE")

CUSTOM_FIELDS = [
    {
        "dt": "Asset Repair",
        "fieldname": "type_intervention",
        "label": "Type d'intervention",
        "fieldtype": "Select",
        "options": "CURATIVE\nPREVENTIVE\nREVISION\nCONTROLE",
        "default": "CURATIVE",
        "insert_after": "repair_status",
    },
    {
        "dt": "Asset Repair",
        "fieldname": "personnel",
        "label": "Intervenant (Personnel HMD)",
        "fieldtype": "Link",
        "options": "Personnel",
        "insert_after": "type_intervention",
    },
    {
        "dt": "Asset Repair",
        "fieldname": "reference_hmd",
        "label": "Référence HMD",
        "fieldtype": "Data",
        "read_only": 1,
        "description": "Marqueur d'idempotence posé par les imports / scripts HMD.",
        "insert_after": "personnel",
    },
]


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


@frappe.whitelist()
def setup_maintenance():
    print("\n" + "=" * 60)
    print("  EPIC D — Interventions & maintenance équipements (FIN-S32)")
    print("=" * 60)

    _ensure_custom_fields()
    _ensure_maintenance_team()
    _check_compte_entretien()

    frappe.db.commit()
    print("\n  Maintenance équipements OK.\n" + "=" * 60 + "\n")


def _ensure_custom_fields():
    for spec in CUSTOM_FIELDS:
        name = f"{spec['dt']}-{spec['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            print(f"  [skip]   Custom Field {name}")
            continue
        frappe.get_doc({"doctype": "Custom Field", **spec}).insert(ignore_permissions=True)
        print(f"  [create] Custom Field {name}")


def utilisateur_assignable(prefere=None):
    """Utilisateur exploitable par l'assignation de tâches d'ERPNext.

    `Asset Maintenance.on_update` assigne chaque tâche via `assign_to.add`,
    qui écrit `ToDo.allocated_to = User.email`. Pour « Administrator » cet
    email vaut `admin@example.com`, qui n'est pas un compte → LinkValidationError.
    On ne retient donc que les comptes dont l'email EST le nom d'utilisateur.
    """
    def valide(user):
        if not user:
            return False
        email = frappe.db.get_value("User", user, "email")
        return bool(email) and email == user and frappe.db.get_value("User", user, "enabled")

    if valide(prefere):
        return prefere
    for user in _users_personnel_maintenance():
        if valide(user):
            return user
    candidats = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User",
                 "name": ["not in", ["Administrator", "Guest"]]},
        pluck="name", order_by="creation asc",
    )
    for user in candidats:
        if valide(user):
            return user
    return None


def _users_personnel_maintenance():
    """Comptes utilisateurs des salariés en charge du matériel."""
    if not frappe.db.exists("DocType", "Personnel"):
        return []
    return frappe.db.sql_list("""
        SELECT DISTINCT user FROM `tabPersonnel`
        WHERE statut = 'ACTIF' AND IFNULL(user, '') != ''
          AND role_personnel IN %(roles)s
    """, {"roles": ROLES_MAINTENANCE})


def _membres_maintenance():
    """(manager, [membres]) — le manager doit être assignable (il sert de
    destinataire par défaut des tâches) ; les membres sont indicatifs, donc
    Administrator y reste admis comme secours."""
    membres = [u for u in _users_personnel_maintenance()
               if frappe.db.get_value("User", u, "enabled")]
    manager = utilisateur_assignable()
    if manager and manager not in membres:
        membres.insert(0, manager)
    if not membres:
        membres = ["Administrator"]
    return manager or "Administrator", membres


def _ensure_maintenance_team():
    manager, membres = _membres_maintenance()
    role = "System Manager"
    if frappe.db.exists("Asset Maintenance Team", EQUIPE_MAINTENANCE):
        equipe = frappe.get_doc("Asset Maintenance Team", EQUIPE_MAINTENANCE)
        connus = {m.team_member for m in equipe.maintenance_team_members}
        nouveaux = [u for u in membres if u not in connus]
        if not nouveaux:
            print(f"  [skip]   Équipe {EQUIPE_MAINTENANCE} ({len(connus)} membres)")
            return
        for user in nouveaux:
            equipe.append("maintenance_team_members",
                          {"team_member": user, "maintenance_role": role})
        equipe.save(ignore_permissions=True)
        print(f"  [update] Équipe {EQUIPE_MAINTENANCE} + {len(nouveaux)} membre(s)")
        return

    frappe.get_doc({
        "doctype": "Asset Maintenance Team",
        "maintenance_team_name": EQUIPE_MAINTENANCE,
        "company": COMPANY,
        "maintenance_manager": manager,
        "maintenance_team_members": [
            {"team_member": user, "maintenance_role": role} for user in membres
        ],
    }).insert(ignore_permissions=True)
    print(f"  [create] Équipe {EQUIPE_MAINTENANCE} ({len(membres)} membres, "
          f"manager {manager})")


def _check_compte_entretien():
    if _acc(COMPTE_ENTRETIEN):
        print(f"  [skip]   Compte {COMPTE_ENTRETIEN} Entretien et réparations présent")
    else:
        print(f"  [warn]   Compte {COMPTE_ENTRETIEN} absent — lancer le socle "
              "comptable avant d'enregistrer des interventions.")
