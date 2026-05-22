"""Populate the HMD Configuration Single with the documented defaults so the
form opens with values pre-filled on existing installs."""
import frappe


DEFAULTS = {
    # Section A — Alertes
    "chaleur_genisse_age_mois": 14,
    "chaleur_post_velage_jours": 45,
    "verification_j21_jours": 18,
    "tarissement_advance_jours": 7,
    "velage_advance_jours": 15,
    "delvo_advance_jours": 1,
    "chaleur_cycle_jours": 21,
    "alerte_lead_jours": 2,
    # Section B — Lactation & Production
    "tarissement_window_jours": 60,
    "traite_max_litres": 60,
    "production_initiale_jours": 60,
    "pic_production_jours": 150,
    "taux_tb_max_pct": 10,
    "taux_tp_max_pct": 10,
    # Section C — Allotement DIM
    "dim_fv_max_multi": 30,
    "dim_thp_max": 120,
    "dim_hp_max": 240,
    "dim_mp_max": 305,
    "dim_primipare_cap": 300,
    "last_third_pct": 66.7,
    "production_drop_alert_pct": -15,
}


def execute():
    """Initialize fields that don't yet have a row in tabSingles. JSON-level
    defaults aren't materialized to tabSingles automatically, so without this
    `frappe.db.get_single_value` would return 0 for Int fields (cast quirk)."""
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    needs_init = [
        field for field in DEFAULTS
        if not frappe.db.sql(
            "SELECT 1 FROM `tabSingles` WHERE doctype=%s AND field=%s LIMIT 1",
            ("HMD Configuration", field),
        )
    ]
    if not needs_init:
        return
    doc = frappe.get_single("HMD Configuration")
    for field in needs_init:
        doc.set(field, DEFAULTS[field])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
