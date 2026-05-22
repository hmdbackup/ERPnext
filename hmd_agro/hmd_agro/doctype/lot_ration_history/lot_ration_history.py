# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class LotRationHistory(Document):
    pass


def record_ration_assignment(lot, new_ration, date_debut, source="MANUAL"):
    """Close any open episode for `lot`, then open a new one starting `date_debut`.

    Single source of truth for ration assignments — both Lot._track_ration_change()
    (auto on form edit) and the Ration list-view bulk action route through here so
    episode close+open semantics stay consistent.

    Args:
        lot: Lot name
        new_ration: Ration name to assign (None = lot being unassigned, just close)
        date_debut: Date string or date object — when the new episode starts
        source: One of MANUAL, ASSIGN_BUTTON, IMPORT, API, BASELINE

    Side effects:
        - Updates the open episode's date_fin to date_debut (if any)
        - Inserts new open episode (date_fin = NULL) if new_ration is set
        - Syncs Lot.date_affectation_actuelle to date_debut (or NULL if cleared)
    """
    d = getdate(date_debut)

    # Find the open episode (date_fin IS NULL) for this lot, if any.
    # Raw SQL because Frappe's filter dict has gotchas with IS NULL.
    open_rows = frappe.db.sql("""
        SELECT name, ration FROM `tabLot Ration History`
        WHERE lot = %s AND date_fin IS NULL
        ORDER BY date_debut DESC LIMIT 1
    """, (lot,), as_dict=True)
    open_ep = open_rows[0] if open_rows else None

    # No-op if the same ration is already in the open episode (idempotent).
    if open_ep and open_ep.ration == new_ration:
        return

    if open_ep:
        frappe.db.set_value("Lot Ration History", open_ep.name, "date_fin", d)

    if new_ration:
        frappe.get_doc({
            "doctype": "Lot Ration History",
            "lot": lot,
            "ration": new_ration,
            "date_debut": d,
            "date_fin": None,
            "changed_by": frappe.session.user,
            "source": source,
        }).insert(ignore_permissions=True)

    frappe.db.set_value(
        "Lot", lot, "date_affectation_actuelle",
        d if new_ration else None,
        update_modified=False,
    )


def ration_on_date(lot, date):
    """Ration assigned to `lot` on `date` (the episode covering it).

    Returns the `ration` of the episode where date_debut <= date < date_fin
    (or date_fin IS NULL). Falls back to Lot.id_ration_actuelle if no history
    covers the date — only happens for lots that never had any assignment recorded.
    """
    d = str(getdate(date))
    row = frappe.db.sql("""
        SELECT ration FROM `tabLot Ration History`
        WHERE lot = %s AND date_debut <= %s AND (date_fin IS NULL OR date_fin > %s)
        ORDER BY date_debut DESC LIMIT 1
    """, (lot, d, d))
    if row and row[0][0]:
        return row[0][0]
    return frappe.db.get_value("Lot", lot, "id_ration_actuelle")


@frappe.whitelist()
def baseline_all_lots():
    """One-shot: for every active lot with a ration but no history, insert an
    open BASELINE episode (date_debut = today, date_fin = NULL).

    Run once after deploying the doctype on a fresh install. Existing installs
    are handled by the v1_3 migration patch instead.
    """
    rows = frappe.db.sql("""
        SELECT l.name, l.id_ration_actuelle
        FROM `tabLot` l
        WHERE l.actif = 1 AND l.id_ration_actuelle IS NOT NULL AND l.id_ration_actuelle != ''
          AND NOT EXISTS (
              SELECT 1 FROM `tabLot Ration History` h WHERE h.lot = l.name
          )
    """, as_dict=True)
    today_d = today()
    created = 0
    for r in rows:
        record_ration_assignment(
            lot=r.name,
            new_ration=r.id_ration_actuelle,
            date_debut=today_d,
            source="BASELINE",
        )
        created += 1
    frappe.db.commit()
    return {"baselined": created}
