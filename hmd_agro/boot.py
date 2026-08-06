"""boot_session — pushes the JS-relevant subset of HMD Configuration into
`frappe.boot.hmd_config` so report .js files can read values without
extra HTTP requests."""
from hmd_agro.hmd_agro.utils.config import get_config


JS_FIELDS = {
    "dim_fv_max_multi": 30,
    "dim_thp_max": 120,
    "dim_hp_max": 240,
    "dim_mp_max": 305,
    "dim_primipare_cap": 300,
    "last_third_pct": 66.7,
    "production_drop_alert_pct": -15,
    "ecart_lait_seuil_negatif_l": 1,
    "ecart_lait_seuil_perte_pct": 5,
    "ecart_lait_seuil_alarme_pct": 10,
    # FIN-S51 — seuils économiques (coloration côté client si besoin)
    "prix_reference_lait": 1.6,
    "objectif_cout_litre": 0.65,
    "objectif_cout_litre_alarme": 0.85,
    "pfe_iofc_jour_min": 3.0,
    "pfe_iofc_jour_orange_min": 1.5,
    # Seuils L/C (réunion 05/08/2026 : rouge < 1,8, cible 2,2). Reports color
    # thresholds server-side today; these are exposed pre-emptively for future
    # client-side use (house rule: JS_FIELDS is the only channel to client code).
    "pfe_lc_optimal_min": 2.0,
    "pfe_lc_optimal_max": 2.4,
    "pfe_lc_alarm_min": 1.8,
    "pfe_lc_alarm_max": 3.0,
    "pfe_lc_cible": 2.2,
}


def boot_session(bootinfo):
    bootinfo["hmd_config"] = {
        field: get_config(field, default) for field, default in JS_FIELDS.items()
    }
