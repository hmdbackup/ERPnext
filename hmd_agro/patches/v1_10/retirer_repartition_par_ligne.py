"""
SCRUM-10 (03/09/2026) — retire la répartition des frais généraux ligne par
ligne : la clé de répartition est désormais une « Cost Center Allocation »
ERPNext, qui ventile les écritures comptables à la validation.

Supprime les quatre Custom Fields (section + table sur Purchase Invoice et
Journal Entry) et le DocType enfant « Repartition Atelier Charge » avec sa
table. Les parts déjà saisies (pièces de démonstration du 29/08) sont
comptées et annoncées avant suppression : leurs pièces restent au Grand Livre
à Frais Généraux, c'est la clé qui répartira les suivantes.

Idempotent : chaque suppression est conditionnée à l'existence.
"""
import frappe

CUSTOM_FIELDS = (
    "Purchase Invoice-repartition_atelier",
    "Purchase Invoice-section_repartition_atelier",
    "Journal Entry-repartition_atelier",
    "Journal Entry-section_repartition_atelier",
)
DOCTYPE_ENFANT = "Repartition Atelier Charge"


def execute():
    for nom in CUSTOM_FIELDS:
        if frappe.db.exists("Custom Field", nom):
            frappe.delete_doc("Custom Field", nom, force=1, ignore_permissions=True)
            print(f"  [retrait] Custom Field {nom}")

    if frappe.db.table_exists(DOCTYPE_ENFANT):
        parts = frappe.db.count(DOCTYPE_ENFANT)
        pieces = frappe.db.sql_list(
            f"SELECT DISTINCT parent FROM `tab{DOCTYPE_ENFANT}` ORDER BY parent")
        if parts:
            print(f"  [retrait] {parts} part(s) de répartition saisie(s) sur "
                  f"{len(pieces)} pièce(s) : {', '.join(pieces)} — ces pièces "
                  f"restent à Frais Généraux au Grand Livre.")
    if frappe.db.exists("DocType", DOCTYPE_ENFANT):
        frappe.delete_doc("DocType", DOCTYPE_ENFANT, force=1, ignore_permissions=True)
        print(f"  [retrait] DocType {DOCTYPE_ENFANT}")
    if frappe.db.table_exists(DOCTYPE_ENFANT):
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{DOCTYPE_ENFANT}`")
        print(f"  [retrait] table tab{DOCTYPE_ENFANT}")
    frappe.clear_cache(doctype="Purchase Invoice")
    frappe.clear_cache(doctype="Journal Entry")
