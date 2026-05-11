# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Ration(Document):
    def validate(self):
        self.validate_unique_aliments()
        self.calculate_cout_estime()
        self._validate_immutability()

    def validate_unique_aliments(self):
        """CF-CRA-01: No duplicate aliments in composition"""
        seen = set()
        for row in self.composition:
            if row.aliment in seen:
                frappe.throw(f"L'aliment '{row.aliment}' est deja present dans la composition.")
            seen.add(row.aliment)

    def calculate_cout_estime(self):
        """RC-RAT-01: cout_estime = SUM(quantite x prix_unitaire)"""
        total = 0
        for row in self.composition:
            prix = frappe.db.get_value("Aliment", row.aliment, "prix_unitaire") or 0
            row.sous_total = round(row.quantite * prix, 3)
            total += row.sous_total
        self.cout_estime = round(total, 3)

    def _validate_immutability(self):
        """A ration's name + composition are frozen after first save. To change
        a recipe, create a new ration and use 'Affecter aux lots' to migrate.

        WHY: reports (rapport_mensuel.py) and the upcoming Stock Module daily
        Material Issue generator read composition LIVE from the current Ration.
        Without this guard, editing a recipe today silently rewrites past
        distribution math. Immutability is the schema-level enforcement of the
        "create-a-new-ration" workflow that was previously an unwritten rule.

        `active` (deprecation toggle) and `description` (notes) remain editable.
        """
        if self.is_new():
            return
        prev = self.get_doc_before_save()
        if not prev:
            return  # No prior state available — first fetch in this session

        if prev.nom_ration != self.nom_ration:
            frappe.throw(
                "Le nom d'une ration est figé après création. "
                "Pour utiliser un autre nom, créez une nouvelle ration."
            )

        if _composition_signature(prev.composition) != _composition_signature(self.composition):
            frappe.throw(
                "La composition d'une ration est figée après création. "
                "Pour modifier le mélange, créez une nouvelle ration "
                "(par ex. '{0}-v2') et utilisez le bouton 'Affecter aux lots' "
                "pour réaffecter les lots concernés.".format(self.nom_ration)
            )


def _composition_signature(rows):
    """Order-insensitive fingerprint of a composition table — sorted tuples of
    (aliment, quantite, unite). Ignores row reordering and `sous_total` (which
    is auto-recalculated and would falsely trigger the immutability check when
    aliment prices shift)."""
    return sorted(
        (r.aliment or "", float(r.quantite or 0), r.unite or "")
        for r in rows
    )


@frappe.whitelist()
def affecter_aux_lots(ration, lots, date_debut):
    """Bulk-assign `ration` to multiple `lots` starting `date_debut`.

    Called by the "Affecter aux lots" action in the Ration list view. Each
    picked lot's open episode (if any) is closed at date_debut, then a new
    open episode is opened for `ration`. Routes through Lot.save() so the
    existing _track_ration_change() hook handles the history write — keeps
    a single source of truth for episode close+open semantics.

    Validates:
      - `ration` exists and is `active`
      - `date_debut` not in the future (no scheduling in v1)
      - `date_debut` not earlier than any picked lot's open episode start
        (would scramble the chronological order of episodes)
    """
    if isinstance(lots, str):
        lots = json.loads(lots)
    if not lots:
        frappe.throw(_("Veuillez sélectionner au moins un lot."))

    if not frappe.db.exists("Ration", ration):
        frappe.throw(_("La ration {0} n'existe pas.").format(ration))
    if not frappe.db.get_value("Ration", ration, "active"):
        frappe.throw(_("La ration {0} n'est pas active.").format(ration))

    d = getdate(date_debut)
    if d > getdate(today()):
        frappe.throw(_("La date de début ne peut pas être dans le futur."))

    # Per-lot precondition: backdating can't go before the open episode's start.
    for lot in lots:
        open_ep = frappe.db.sql("""
            SELECT date_debut FROM `tabLot Ration History`
            WHERE lot = %s AND date_fin IS NULL
            ORDER BY date_debut DESC LIMIT 1
        """, (lot,), as_dict=True)
        if open_ep and getdate(open_ep[0].date_debut) > d:
            frappe.throw(_(
                "Pour le lot {0}: la date de début ({1}) ne peut pas être "
                "antérieure à l'épisode actuel commencé le {2}."
            ).format(lot, d, open_ep[0].date_debut))

    affected = 0
    skipped = 0
    for lot_name in lots:
        lot_doc = frappe.get_doc("Lot", lot_name)
        if lot_doc.id_ration_actuelle == ration:
            skipped += 1
            continue
        lot_doc.id_ration_actuelle = ration
        lot_doc.flags.ration_effective_date = d
        lot_doc.flags.ration_change_source = "ASSIGN_BUTTON"
        lot_doc.save()

    affected = len(lots) - skipped
    return {"affected": affected, "skipped": skipped}


@frappe.whitelist()
def lots_using_ration(ration):
    """Lots currently using `ration` (open episodes only). Used by ration.js
    to render the 'Lots utilisant cette ration' display on the detail page."""
    return frappe.db.sql("""
        SELECT lot, date_debut FROM `tabLot Ration History`
        WHERE ration = %s AND date_fin IS NULL
        ORDER BY lot
    """, (ration,), as_dict=True)
