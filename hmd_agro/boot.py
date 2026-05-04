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
}


def boot_session(bootinfo):
    bootinfo["hmd_config"] = {
        field: get_config(field, default) for field, default in JS_FIELDS.items()
    }
