# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

"""A2 — immutable salary history row (child of Personnel).

Rows are appended automatically by `Personnel.maintenir_historique` whenever a
remuneration field changes; editing or deleting past rows is rejected by
`Personnel.proteger_historique` (ERR-PERS-09). The payroll build
(`charges_utils.masse_salariale`) reads the row effective for the computed
month, so a raise never rewrites an already-posted month.
"""
from frappe.model.document import Document


class PersonnelSalaireHistorique(Document):
    pass
