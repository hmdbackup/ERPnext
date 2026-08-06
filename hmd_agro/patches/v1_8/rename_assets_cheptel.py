"""TASK A1 — retitle cheptel Assets to the working number.

`creer_actif_cheptel` used to name assets "Vache <identification_tn>"
(the 10-digit national ID) while the users know cows by their working
number (`nom_metier`, last 4 digits). Rewrite every Asset carrying an
`id_animal` to "Vache <nom_metier or id_animal>".

Idempotent: skips assets whose name already matches the target; uses
db.set_value because cheptel Assets are submitted documents.
"""
import frappe


def execute():
    if not frappe.db.exists("DocType", "Asset"):
        return
    if not frappe.db.has_column("Asset", "id_animal"):
        return                            # custom field not deployed yet

    assets = frappe.db.sql("""
        SELECT name, asset_name, id_animal
        FROM `tabAsset`
        WHERE COALESCE(id_animal, '') != ''
    """, as_dict=True)

    for row in assets:
        nom_metier = frappe.db.get_value("Animal", row.id_animal, "nom_metier")
        cible = f"Vache {nom_metier or row.id_animal}"
        if row.asset_name == cible:
            continue
        frappe.db.set_value("Asset", row.name, "asset_name", cible,
                            update_modified=False)
