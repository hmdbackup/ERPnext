"""
EPIC E — Charges & main-d'œuvre ventilées par atelier (FIN-S40/S41, RG-FIN-40).

Les charges diverses (énergie, eau, loyer, assurances…) se saisissent en
Purchase Invoice / Journal Entry standard, imputées aux comptes 60x/61x/62x
et au Cost Center atelier — rien à coder, le socle porte le référentiel.

Ce module ajoute le flux salaires (FIN-S41) sans module Payroll : UNE
écriture mensuelle ventilée — débit 640 (Salaires) par atelier, crédit 421
(Personnel - Rémunérations dues). Idempotente par marqueur `SALAIRES_<période>`
dans user_remark (pattern maison).

Run:
    bench --site hmd.agro execute \\
        hmd_agro.hmd_agro.utils.charges_utils.post_salaires \\
        --kwargs "{'periode': '2026-07', 'montants_par_atelier':
                   {'Lait': 4000, 'Élevage - Génisses': 1500}}"
"""
import json

import frappe
from frappe.utils import get_last_day, getdate

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

COMPTE_SALAIRES = "640"
COMPTE_PERSONNEL = "421"


def _acc(number):
    return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})


def _marker(periode):
    return f"SALAIRES_{periode}"


def existing_entry(periode):
    return frappe.db.get_value(
        "Journal Entry",
        {"user_remark": ["like", f"%{_marker(periode)}%"], "docstatus": ["<", 2]},
        "name",
    )


@frappe.whitelist()
def post_salaires(periode, montants_par_atelier, submit=True):
    """Poste la masse salariale du mois ventilée par atelier (RG-FIN-40).

    Args:
        periode:              'YYYY-MM' (écriture datée au dernier jour du mois)
        montants_par_atelier: dict {atelier: montant DT} — l'atelier est le
                              nom court du Cost Center (ex. 'Lait')
    Returns: le nom du Journal Entry (existant si déjà posté — idempotent).
    """
    if isinstance(montants_par_atelier, str):
        montants_par_atelier = json.loads(montants_par_atelier)

    existing = existing_entry(periode)
    if existing:
        print(f"  [skip]   Salaires {periode} déjà postés ({existing})")
        return existing

    montants = {k: float(v) for k, v in montants_par_atelier.items() if float(v) > 0}
    if not montants:
        print(f"  [skip]   Salaires {periode} : aucun montant")
        return None

    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    compte_640, compte_421 = _acc(COMPTE_SALAIRES), _acc(COMPTE_PERSONNEL)
    if not (compte_640 and compte_421):
        frappe.throw("ERR-FIN-05 : comptes 640/421 introuvables — lancer le socle comptable.")

    accounts = []
    total = 0.0
    for atelier, montant in montants.items():
        cc = f"{atelier} - {abbr}"
        if not frappe.db.exists("Cost Center", cc):
            frappe.throw(f"ERR-FIN-06 : Cost Center '{cc}' introuvable (RG-FIN-40).")
        accounts.append({
            "account": compte_640,
            "debit_in_account_currency": montant,
            "cost_center": cc,
        })
        total += montant
    accounts.append({
        "account": compte_421,
        "credit_in_account_currency": total,
    })

    date_ecriture = get_last_day(getdate(f"{periode}-01"))
    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": COMPANY,
        "posting_date": date_ecriture,
        "accounts": accounts,
        "user_remark": f"{_marker(periode)} — masse salariale ventilée "
                       f"({len(montants)} ateliers, {total} TND)",
    })
    je.insert(ignore_permissions=True)
    if submit:
        je.submit()
    print(f"  [create] Salaires {periode} : {je.name} — {total} TND "
          f"sur {len(montants)} ateliers")
    return je.name
