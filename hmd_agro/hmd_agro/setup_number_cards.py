"""
Create Number Card documents for the HMD AGRO workspace.
Run: bench execute hmd_agro.hmd_agro.setup_number_cards.create_number_cards
"""
import frappe


def create_number_cards():
    cards = [
        {
            "name": "Animaux Actifs",
            "label": "Animaux Actifs",
            "document_type": "Animal",
            "filters_json": '[["Animal", "statut", "=", "ACTIF"]]',
            "function": "Count",
            "color": "#2490EF",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Alertes en Attente",
            "label": "Alertes en Attente",
            "document_type": "Alerte",
            "filters_json": '[["Alerte", "statut", "=", "NOUVELLE"]]',
            "function": "Count",
            "color": "#E24C4C",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Lactations en Cours",
            "label": "Lactations en Cours",
            "document_type": "Lactation",
            "filters_json": '[["Lactation", "statut", "=", "EN_COURS"]]',
            "function": "Count",
            "color": "#48BB74",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Attente Lait",
            "label": "Attente Lait",
            "document_type": "Animal",
            "filters_json": '[["Animal", "attente_lait_active", "=", 1]]',
            "function": "Count",
            "color": "#ED8936",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        }
    ]

    for card_data in cards:
        if frappe.db.exists("Number Card", card_data["name"]):
            print(f"  Already exists: {card_data['name']}")
            continue

        doc = frappe.get_doc({
            "doctype": "Number Card",
            "type": "Document Type",
            **card_data
        })
        doc.insert(ignore_permissions=True)
        print(f"  Created: {card_data['name']}")

    frappe.db.commit()
    print("\nNumber cards ready.")
