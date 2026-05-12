"""Seed Traite.quantite_litres_brut with quantite_litres for existing rows.

Before this patch, only `quantite_litres` existed and stored whatever the farmer
typed (no reconciliation was happening). After Sprint 5's reconciliation work,
`quantite_litres_brut` carries the original measurement and `quantite_litres`
carries the reconciled value. For historical data we treat the two as equal
(no past reconciliation to undo), so we copy across.

Idempotent: WHERE clause guarantees we only touch rows that don't have a
brut value yet."""

import frappe


def execute():
    updated = frappe.db.sql("""
        UPDATE `tabTraite`
        SET quantite_litres_brut = quantite_litres
        WHERE quantite_litres_brut IS NULL OR quantite_litres_brut = 0
    """)
    frappe.db.commit()
