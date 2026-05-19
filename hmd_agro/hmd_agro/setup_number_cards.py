"""
Create Number Card and Dashboard Chart documents for the HMD AGRO workspace.

NOTE — fixtures are now the canonical source. On a normal install:
- `bench install-app hmd_agro` → fixture loader auto-creates these from
  `fixtures/number_card.json` and `fixtures/dashboard_chart.json` (registered
  in `hooks.py` since today).
- Re-running `bench migrate` re-applies the fixtures.

This script remains as a fallback for explicit/manual recreation. Keep it in
sync with the fixture JSON files when adding/renaming cards in the UI.

Run (rarely needed):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup_number_cards.create_number_cards

Note about Custom-type cards (PL_VL, L_C, Production Journaliere, Alertes en
Attente): they call a Python method to compute their value. The methods live in
`utils/dashboard_kpis.py` (for PL_VL, L_C) and respective doctype modules.
"""
import frappe
import json


def create_number_cards():
    cards = [
        # ── Document Type cards (count or sum over a single doctype) ─────
        {
            "name": "Animaux Actifs",
            "label": "Animaux Actifs",
            "type": "Document Type",
            "document_type": "Animal",
            "filters_json": '[["Animal", "statut", "=", "ACTIF"]]',
            "function": "Count",
            "color": "#2490EF",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        {
            "name": "Lactations en Cours",
            "label": "Lactations en Cours",
            "type": "Document Type",
            "document_type": "Lactation",
            "filters_json": '[["Lactation", "statut", "=", "EN_COURS"]]',
            "function": "Count",
            "color": "#48BB74",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        {
            "name": "Animal Sous Traitement",
            "label": "Animal Sous Traitement",
            "type": "Document Type",
            "document_type": "Animal",
            "filters_json": '[["Animal", "attente_lait_active", "=", 1]]',
            "function": "Count",
            "color": "#CB2929",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        {
            "name": "Gestantes",
            "label": "Gestantes",
            "type": "Document Type",
            "document_type": "Animal",
            "filters_json": ('[["Animal", "etat_gestation", "=", "GESTANTE"], '
                             '["Animal", "statut", "=", "ACTIF"]]'),
            "function": "Count",
            "color": "#9F7AEA",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        # ── Custom cards (call a whitelisted Python method) ──────────────
        {
            "name": "Alertes en Attente",
            "label": "Alertes en Attente",
            "type": "Custom",
            "method": "hmd_agro.hmd_agro.doctype.alerte.alerte.get_alertes_count",
            "function": "Count",
            "color": "#E24C4C",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        {
            "name": "Production Journaliere",
            "label": "Production Journaliere (L)",
            "type": "Custom",
            "method": ("hmd_agro.hmd_agro.doctype.traite.traite"
                       ".get_production_journaliere"),
            "function": "Sum",
            "aggregate_function_based_on": "quantite_litres",
            "color": "#4299E1",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        {
            "name": "PL_VL",
            "label": "PL_VL (L/tête)",
            "type": "Custom",
            "method": "hmd_agro.hmd_agro.utils.dashboard_kpis.get_pl_vl",
            "function": "Count",
            "color": "#9F7AEA",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
        {
            "name": "L_C",
            "label": "L_C (L/kg)",
            "type": "Custom",
            "method": "hmd_agro.hmd_agro.utils.dashboard_kpis.get_lc_ratio",
            "function": "Count",
            "color": "#ED8936",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        },
    ]

    for card_data in cards:
        if frappe.db.exists("Number Card", card_data["name"]):
            print(f"  Already exists: {card_data['name']}")
            continue
        doc = frappe.get_doc({"doctype": "Number Card", **card_data})
        doc.insert(ignore_permissions=True)
        print(f"  Created: {card_data['name']}")

    # Dashboard Charts
    charts = [
        {
            "name": "Production Lait Journaliere",
            "chart_name": "Production Lait Journaliere",
            "chart_type": "Sum",
            "document_type": "Traite",
            "based_on": "date_traite",
            "value_based_on": "quantite_litres",
            "timespan": "Last Month",
            "time_interval": "Daily",
            "timeseries": 1,
            "type": "Bar",
            "color": "#4299E1",
            "filters_json": "[]",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO",
        }
    ]

    for chart_data in charts:
        if frappe.db.exists("Dashboard Chart", chart_data["name"]):
            print(f"  Chart already exists: {chart_data['name']}")
            continue
        doc = frappe.get_doc({"doctype": "Dashboard Chart", **chart_data})
        doc.insert(ignore_permissions=True)
        print(f"  Chart created: {chart_data['name']}")

    frappe.db.commit()
    print("\nSetup complete.")
