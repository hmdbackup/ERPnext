"""
FIN-S22 (RG-FIN-20 / CF-FIN-21) — facture à la sortie VENDU / REFORME.

When an Animal's `statut` moves to VENDU or REFORME with a `prix_vente`,
one Sales Invoice is posted (item ANIMAL-VENTE, atelier by categorie).
Symmetric paths (CF-FIN-21):
  • statut leaves VENDU/REFORME (data-entry fix) → the invoice is cancelled
    (compensating GL reversal, audit preserved);
  • Animal deleted → invoice cancelled the same way.

CF-FIN-21 : la facturation n'empêche JAMAIS d'enregistrer la sortie de
l'animal (même stance que le stock) — any invoicing failure downgrades to a
red alert + error log, the Animal save goes through.

Idempotence : marqueur `ANIMAL_VENTE_<animal>` dans remarks — un seul
document actif (docstatus < 2) par animal.
"""
import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_COMPANY as COMPANY

ITEM_ANIMAL = "ANIMAL-VENTE"
CUSTOMER_DEFAULT = "Client Divers"
STATUTS_VENTE = ("VENDU", "REFORME")


def _marker(animal):
    return f"ANIMAL_VENTE_{animal}"


def existing_invoice(animal):
    return frappe.db.get_value(
        "Sales Invoice",
        {"remarks": ["like", f"%{_marker(animal)}%"], "docstatus": ["<", 2]},
        "name",
    )


def _cost_center(categorie):
    """Atelier: vaches → Lait ; jeunes/génisses → Élevage (RG-FIN-40)."""
    abbr = frappe.db.get_value("Company", COMPANY, "abbr")
    atelier = "Lait" if categorie == "VACHE" else "Élevage - Génisses"
    name = f"{atelier} - {abbr}"
    return name if frappe.db.exists("Cost Center", name) else None


def sync_sale_invoice(animal_doc):
    """Called from Animal.on_update (statut change only). Never raises."""
    try:
        if animal_doc.statut in STATUTS_VENTE:
            _create_invoice(animal_doc)
        else:
            # exit reverted (VENDU/REFORME → ACTIF/…) → compensate
            cancel_sale_invoice(animal_doc.name)
    except Exception:
        frappe.log_error(
            title=f"ERR-VTE-01 facture vente {animal_doc.name}",
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            f"ERR-VTE-01 : la facture de vente de {animal_doc.name} n'a pas pu "
            "être synchronisée — voir le journal d'erreurs. La sortie de "
            "l'animal reste enregistrée.",
            indicator="red", alert=True,
        )


def _create_invoice(animal_doc):
    if existing_invoice(animal_doc.name):
        return
    prix = float(animal_doc.prix_vente or 0)
    if prix <= 0:
        frappe.msgprint(
            f"Sortie {animal_doc.statut} de {animal_doc.name} sans prix_vente — "
            "aucune facture émise (renseigner le prix puis repasser le statut "
            "pour facturer).",
            indicator="orange", alert=True,
        )
        return
    if not frappe.db.exists("Item", ITEM_ANIMAL):
        frappe.msgprint(
            f"Item {ITEM_ANIMAL} absent — lancer setup.finance.recettes "
            "(référentiel de vente) pour activer la facturation animaux.",
            indicator="orange", alert=True,
        )
        return

    posting_date = animal_doc.date_sortie or today()
    if getdate(posting_date) > getdate(today()):
        posting_date = today()
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "company": COMPANY,
        "customer": CUSTOMER_DEFAULT,
        "posting_date": posting_date,
        "set_posting_time": 1,
        "items": [{
            "item_code": ITEM_ANIMAL,
            "qty": 1,
            "rate": prix,
            "description": (f"Vente animal {animal_doc.name} "
                            f"({animal_doc.categorie}, statut {animal_doc.statut})"),
            "cost_center": _cost_center(animal_doc.categorie),
        }],
        "remarks": f"{_marker(animal_doc.name)} — {animal_doc.statut}",
    })
    si.insert(ignore_permissions=True)
    si.submit()
    frappe.msgprint(
        f"Facture de vente {si.name} émise : {animal_doc.name} @ {prix} TND "
        f"(RG-FIN-20).",
        indicator="green", alert=True,
    )


def cancel_sale_invoice(animal_name):
    """Compensating reversal — used on statut revert and Animal.on_trash."""
    name = existing_invoice(animal_name)
    if not name:
        return
    si = frappe.get_doc("Sales Invoice", name)
    if si.docstatus == 1:
        si.flags.ignore_permissions = True
        si.cancel()
        frappe.msgprint(
            f"Facture {name} annulée (écriture compensatoire — CF-FIN-21).",
            indicator="orange", alert=True,
        )
    elif si.docstatus == 0:
        si.delete(ignore_permissions=True)
