# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

"""A2 — one-off bonus (prime) granted to an employee for a pay month.

Primes are added to the gross of `charges_utils.masse_salariale(periode)`
(account 640) and enter the CNSS base (647) only when the employee is
`soumis_cnss`. Bulk attribution lives in `personnel.attribuer_prime_bulk`
(listview action « Attribuer une prime »).

A prime cannot target a month whose salaries are already posted to the GL
(marker `SALAIRES_<periode>`) — otherwise it would never reach the ledger
and the registre/GL would silently diverge (ERR-PRIME-04).
"""
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

PERIODE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class PrimePersonnel(Document):
    def validate(self):
        if flt(self.montant) <= 0:
            frappe.throw(
                _("ERR-PRIME-01 : le montant de la prime doit être strictement "
                  "positif (saisi : {0}).").format(self.montant)
            )
        if not PERIODE_RE.match(self.periode or ""):
            frappe.throw(
                _("ERR-PRIME-02 : la période doit être au format AAAA-MM, "
                  "ex. 2026-08 (saisi : {0}).").format(self.periode)
            )
        self.validate_doublon()
        self.validate_periode_non_postee()

    def validate_periode_non_postee(self):
        """A prime on an already-posted month would never reach the GL :
        `post_salaires` is idempotent by marker and will skip the month —
        the registre and the ledger would diverge silently."""
        from hmd_agro.hmd_agro.utils.charges_utils import existing_entry

        je = existing_entry(self.periode)
        if je:
            frappe.throw(
                _("ERR-PRIME-04 : les salaires de {0} sont déjà postés au "
                  "Grand Livre ({1}) — annuler ou régulariser cette écriture "
                  "avant d'attribuer une prime sur ce mois.").format(self.periode, je)
            )

    def validate_doublon(self):
        """Same (personnel, periode, motif) twice is almost always a double
        entry — the amount can be adjusted on the existing record instead."""
        doublon = frappe.db.sql("""
            SELECT name FROM `tabPrime Personnel`
            WHERE personnel = %s AND periode = %s
              AND IFNULL(motif, '') = %s AND name != %s
        """, (self.personnel, self.periode, self.motif or "", self.name or ""))
        if doublon:
            frappe.throw(
                _("ERR-PRIME-03 : une prime identique existe déjà pour ce "
                  "salarié sur {0} ({1}) — modifier son montant plutôt que "
                  "d'en créer une seconde.").format(self.periode, doublon[0][0])
            )
