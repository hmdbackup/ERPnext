"""
EPIC G — test séparation des tâches (FIN-S61).

Un utilisateur « Éleveur HMD » peut lire/écrire les DocTypes troupeau mais
ne peut PAS créer ni soumettre d'écriture comptable ; un « Accounts User »
le peut.

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_roles_finance.run
"""
import traceback

import frappe

USER_ELEVEUR = "test-eleveur@hmd.agro"
USER_COMPTA = "test-comptable@hmd.agro"


def _cleanup():
    frappe.set_user("Administrator")
    for u in (USER_ELEVEUR, USER_COMPTA):
        if frappe.db.exists("User", u):
            frappe.delete_doc("User", u, force=True, ignore_permissions=True)
    frappe.db.commit()


def _make_user(email, roles):
    user = frappe.get_doc({
        "doctype": "User", "email": email, "first_name": email.split("@")[0],
        "send_welcome_email": 0, "roles": [{"role": r} for r in roles],
    })
    user.insert(ignore_permissions=True)
    return user


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  EPIC G — Droits par rôle (FIN-S61)")
    print("=" * 70)
    try:
        return _run_inner()
    finally:
        _cleanup()


def _run_inner():
    results = {"pass": 0, "fail": 0}
    _cleanup()

    from hmd_agro.hmd_agro.setup.finance.roles import setup_roles, ROLE_ELEVEUR
    setup_roles()

    _make_user(USER_ELEVEUR, [ROLE_ELEVEUR])
    _make_user(USER_COMPTA, ["Accounts User", "Accounts Manager"])
    frappe.db.commit()

    try:
        # Éleveur : troupeau OK
        _check(frappe.has_permission("Traite", ptype="create", user=USER_ELEVEUR),
               "Éleveur peut créer une Traite", results)
        _check(frappe.has_permission("Animal", ptype="write", user=USER_ELEVEUR),
               "Éleveur peut modifier un Animal", results)
        _check(frappe.has_permission("Bilan Lait Journalier", ptype="create",
                                     user=USER_ELEVEUR),
               "Éleveur peut saisir le Bilan Lait Journalier", results)
        # Éleveur : comptabilité NON
        _check(not frappe.has_permission("Journal Entry", ptype="create",
                                         user=USER_ELEVEUR),
               "Éleveur ne peut PAS créer une écriture comptable", results)
        _check(not frappe.has_permission("Journal Entry", ptype="submit",
                                         user=USER_ELEVEUR),
               "Éleveur ne peut PAS soumettre une écriture comptable", results)
        _check(not frappe.has_permission("Sales Invoice", ptype="create",
                                         user=USER_ELEVEUR),
               "Éleveur ne peut PAS créer une facture", results)
        # Comptable : comptabilité OUI
        _check(frappe.has_permission("Journal Entry", ptype="create",
                                     user=USER_COMPTA),
               "Comptable (Accounts User) peut créer une écriture", results)
        _check(frappe.has_permission("Journal Entry", ptype="submit",
                                     user=USER_COMPTA),
               "Comptable peut soumettre une écriture", results)
    except Exception:
        print(traceback.format_exc())
        results["fail"] += 1

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
