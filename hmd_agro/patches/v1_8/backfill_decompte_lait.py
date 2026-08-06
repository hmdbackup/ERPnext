"""FIN-B1 — backfill `Decompte Lait Mensuel` from historical milk invoices.

Every already-billed period (Sales Invoice carrying the legacy remarks marker
`LAIT_FACT_<debut>_<fin>`) gets a submitted Decompte snapshot AT THE INVOICE'S
RATE — history is frozen as it was actually billed, not recomputed from
today's grid (recomputing is exactly the bug FIN-B1 removes).

The snapshot is deliberately flat: prix_base = invoice rate, primes = 0,
grille left empty — the real decomposition of an old price is unknowable and
guessing it would freeze a lie. TB/TP are recovered from the remarks when the
marker line carries them ("TB 3.9, TP 3.2").

Idempotent & tolerant: skips periods that already have a live Decompte, skips
unparseable remarks, and never lets one bad invoice abort the migration.
"""
import re

import frappe

RE_MARKER = re.compile(r"LAIT_FACT_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})")
RE_TB = re.compile(r"TB\s+(\d+(?:\.\d+)?)")
RE_TP = re.compile(r"TP\s+(\d+(?:\.\d+)?)")


def execute():
    if not frappe.db.table_exists("Decompte Lait Mensuel"):
        return

    factures = frappe.get_all(
        "Sales Invoice",
        filters={"remarks": ["like", "%LAIT_FACT_%"], "docstatus": 1},
        fields=["name", "customer", "remarks"],
    )
    for facture in factures:
        try:
            _backfill_one(facture)
        except Exception:
            frappe.log_error(
                title=f"backfill_decompte_lait: facture {facture.name} ignorée",
                message=frappe.get_traceback(),
            )
    frappe.db.commit()


def _backfill_one(facture):
    match = RE_MARKER.search(facture.remarks or "")
    if not match:
        return
    debut, fin = match.group(1), match.group(2)

    # Never duplicate: any live Decompte overlapping the period wins.
    if frappe.db.exists(
        "Decompte Lait Mensuel",
        {"docstatus": ["<", 2],
         "periode_debut": ["<=", fin],
         "periode_fin": [">=", debut]},
    ):
        return

    item = frappe.db.get_value(
        "Sales Invoice Item", {"parent": facture.name}, ["qty", "rate"],
        as_dict=True,
    )
    if not item:
        return

    tb = RE_TB.search(facture.remarks or "")
    tp = RE_TP.search(facture.remarks or "")
    dlm = frappe.get_doc({
        "doctype": "Decompte Lait Mensuel",
        "periode_debut": debut,
        "periode_fin": fin,
        "acheteur": facture.customer,
        "volume_litres": item.qty,
        "tb_moyen": float(tb.group(1)) if tb else None,
        "tp_moyen": float(tp.group(1)) if tp else None,
        "prix_base": item.rate,        # frozen at the billed rate (see docstring)
        "prime_qualite": 0,
        "prime_quantite": 0,
        "ajustement_manuel": 0,
        "facture": facture.name,
    })
    dlm.insert(ignore_permissions=True)
    dlm.submit()
    print(f"  [backfill] Décompte {dlm.name} figé depuis {facture.name} "
          f"({debut} → {fin}, {item.qty:.0f} L @ {item.rate})")
