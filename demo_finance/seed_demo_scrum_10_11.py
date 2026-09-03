"""Demo data for SCRUM-10 (FG split by the key) and SCRUM-11 (parc / interventions).

SCRUM-10 since 03/09/2026: the key is a Cost Center Allocation on Frais
Généraux (60 % Lait / 25 % Cultures / 15 % Génisses from 01/08/2026 — posted
with `_skip_from_date_validation`, real August entries already exist on that
center) ; the demo invoices carry NO split table any more, the ledger does it.

Idempotent: every document carries the DEMO_S1011 marker and is removed by
`clear()` before `run()` seeds again. August 2026, company hmd-agro.

Run inside the container (after copying this file into the app package):
    bench --site hmd.agro execute hmd_agro.demo_scrum_10_11.run
    bench --site hmd.agro execute hmd_agro.demo_scrum_10_11.clear
"""
import frappe
from frappe.utils import add_days, today, getdate

COMPANY = "hmd-agro"
MARK = "DEMO_S1011"
FG = "Frais Généraux - HMD"
LAIT = "Lait - HMD"
CULTURES = "Cultures - Fourrage - HMD"
GENISSES = "Élevage - Génisses - HMD"
TRACTION = "Traction - HMD"
FOURNISSEUR = "Fournisseur Divers"
GARAGE = "Garage Mécanique du Sahel"
TRACTEUR = "ACC-ASS-2026-00003"
DATE_FACTURE = "2026-08-05"
DATE_ASSURANCE = "2026-08-10"
DATE_LOCATION = "2026-08-12"
DATE_INTERVENTION = "2026-08-18"


def _acc(number):
    return frappe.db.get_value("Account", {"account_number": number, "company": COMPANY})


def _item(code, name, expense_number):
    if not frappe.db.exists("Item", code):
        frappe.get_doc({
            "doctype": "Item", "item_code": code, "item_name": name,
            "item_group": frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups",
            "stock_uom": "Nos", "is_stock_item": 0, "is_purchase_item": 1,
            "item_defaults": [{"company": COMPANY, "expense_account": _acc(expense_number),
                               "default_supplier": FOURNISSEUR}],
        }).insert(ignore_permissions=True)
    return code


DATE_CLE = "2026-08-01"
CLE = [(LAIT, 60), (CULTURES, 25), (GENISSES, 15)]


def _cle():
    """The key: one submitted Cost Center Allocation on Frais Généraux."""
    doc = frappe.get_doc({
        "doctype": "Cost Center Allocation", "company": COMPANY,
        "main_cost_center": FG, "valid_from": DATE_CLE,
        "allocation_percentages": [{"cost_center": cc, "percentage": pct} for cc, pct in CLE],
    })
    doc._skip_from_date_validation = True
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc.name


def _supprimer_cles():
    for name in frappe.get_all("Cost Center Allocation",
                               filters={"main_cost_center": FG, "valid_from": DATE_CLE}, pluck="name"):
        doc = frappe.get_doc("Cost Center Allocation", name)
        if doc.docstatus == 1:
            doc.cancel()
        frappe.delete_doc("Cost Center Allocation", name, force=1, ignore_permissions=True)


def _facture_energie():
    """STEG août : 1 200 DT on 606 at FG — the key sends 720 Lait / 300 Cultures / 180 Génisses."""
    item = _item("DEMO-ENERGIE", "Électricité et eau (STEG / SONEDE)", "606")
    pi = frappe.get_doc({
        "doctype": "Purchase Invoice", "company": COMPANY, "supplier": FOURNISSEUR,
        "posting_date": DATE_FACTURE, "set_posting_time": 1, "due_date": add_days(DATE_FACTURE, 30),
        "bill_no": f"{MARK}-STEG-0826", "remarks": f"{MARK} Facture STEG août 2026",
        "cost_center": FG,
        "items": [{"item_code": item, "item_name": "Électricité août 2026 — ferme", "qty": 1,
                   "rate": 1200, "expense_account": _acc("606"), "cost_center": FG},
                  {"item_code": item, "item_name": "Eau août 2026 — ferme", "qty": 1,
                   "rate": 300, "expense_account": _acc("606"), "cost_center": FG}],
    })
    pi.insert(ignore_permissions=True)
    pi.submit()
    return pi.name


def _ecriture(date, compte, montant, libelle, cost_center=FG):
    je = frappe.get_doc({
        "doctype": "Journal Entry", "company": COMPANY, "posting_date": date,
        "voucher_type": "Journal Entry", "user_remark": f"{MARK} {libelle}",
        "accounts": [
            {"account": _acc(compte), "cost_center": cost_center,
             "debit_in_account_currency": montant, "user_remark": libelle},
            {"account": _acc("401"), "party_type": "Supplier", "party": FOURNISSEUR,
             "credit_in_account_currency": montant},
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()
    return je.name


def _equipement(nom, montant, cout_horaire):
    existing = frappe.db.get_value("Asset", {"asset_name": nom, "docstatus": 1})
    if existing:
        return existing
    asset = frappe.get_doc({
        "doctype": "Asset", "company": COMPANY, "asset_name": nom, "item_code": "EQUIP-TRACTEUR",
        "asset_category": "Matériel de transport", "location": "Ferme HMD",
        "gross_purchase_amount": montant, "purchase_date": "2026-01-01",
        "available_for_use_date": "2026-01-01", "is_existing_asset": 1,
        "calculate_depreciation": 0, "cout_horaire": cout_horaire, "asset_owner": "Company",
    })
    asset.insert(ignore_permissions=True)
    asset.submit()
    return asset.name


def _fiche(asset, statut, date, description, **extra):
    doc = frappe.get_doc({
        "doctype": "Asset Repair", "company": COMPANY, "asset": asset,
        "failure_date": f"{date} 08:00:00", "repair_status": statut,
        "description": description, "reference_hmd": MARK, **extra,
    })
    doc.insert(ignore_permissions=True)
    return doc


def _intervention_terminee():
    """Tractor: completed and submitted intervention by an external garage, 250 parts + 150 labour."""
    doc = _fiche(TRACTEUR, "Completed", DATE_INTERVENTION, "Remplacement courroie et filtres hydrauliques",
                 completion_date=f"{DATE_INTERVENTION} 12:00:00", type_intervention="CURATIVE",
                 prestataire=GARAGE, cout_pieces=250, cout_main_oeuvre=150, cost_center=TRACTION)
    doc.submit()
    from hmd_agro.hmd_agro.utils.maintenance_utils import _poster_charge
    _poster_charge(doc.name, 400, DATE_INTERVENTION, TRACTION, "FOURNISSEUR", GARAGE,
                   "Remplacement courroie et filtres hydrauliques")
    return doc.name


def _heures(asset, date, heures, atelier):
    frappe.get_doc({"doctype": "Utilisation Equipement", "equipement": asset, "date": date,
                    "heures": heures, "atelier": atelier, "notes": MARK}).insert(ignore_permissions=True)


def clear():
    for dt in ("Asset Repair", "Journal Entry", "Purchase Invoice"):
        field = {"Asset Repair": "reference_hmd", "Journal Entry": "user_remark",
                 "Purchase Invoice": "remarks"}[dt]
        for name in frappe.get_all(dt, filters={field: ["like", f"%{MARK}%"]}, pluck="name"):
            doc = frappe.get_doc(dt, name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
    # JE 615 posted by _poster_charge carries MAINT_<repair> — remove those tied to demo repairs
    for name in frappe.get_all("Journal Entry", filters={"user_remark": ["like", "%MAINT_ACC-ASR-%"],
                                                         "posting_date": DATE_INTERVENTION}, pluck="name"):
        if not frappe.db.exists("Asset Repair", frappe.db.get_value("Journal Entry", name, "user_remark").split("MAINT_")[-1].split()[0]):
            doc = frappe.get_doc("Journal Entry", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Journal Entry", name, force=1, ignore_permissions=True)
    _supprimer_cles()
    for name in frappe.get_all("Utilisation Equipement", filters={"notes": MARK}, pluck="name"):
        frappe.delete_doc("Utilisation Equipement", name, force=1, ignore_permissions=True)
    for nom in ("Pompe à vide — salle de traite", "Presse à balles"):
        for name in frappe.get_all("Asset", filters={"asset_name": nom}, pluck="name"):
            doc = frappe.get_doc("Asset", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Asset", name, force=1, ignore_permissions=True)
    frappe.db.commit()
    print("demo cleared")


def run():
    clear()
    cle = _cle()
    pi = _facture_energie()
    je_assur = _ecriture(DATE_ASSURANCE, "616", 900, "Assurance multirisque exploitation — août")
    # Posted before the key: stays on Frais Généraux, the report names it.
    je_loc = _ecriture("2026-07-28", "613", 300, "Location bureau — juillet (avant la clé)")
    pompe = _equipement("Pompe à vide — salle de traite", 12000, 15)
    presse = _equipement("Presse à balles", 28000, 40)
    fiche_ok = _intervention_terminee()
    panne = _fiche(pompe, "Pending", today(), "Perte de vide — joint de pompe HS", type_intervention="CURATIVE")
    planifiee = _fiche(presse, "Planned", add_days(today(), 12), "Graissage et contrôle des couteaux avant fenaison",
                       type_intervention="PREVENTIVE", personnel="PERS-00134")
    _heures(TRACTEUR, "2026-08-04", 6, CULTURES)
    _heures(TRACTEUR, "2026-08-11", 5, LAIT)
    _heures(presse, "2026-08-07", 8, CULTURES)
    _heures(pompe, "2026-08-20", 4, LAIT)
    frappe.db.commit()
    print({"cle": cle, "facture": pi, "assurance": je_assur, "location": je_loc, "pompe": pompe, "presse": presse,
           "intervention_terminee": fiche_ok, "panne": panne.name, "planifiee": planifiee.name})
