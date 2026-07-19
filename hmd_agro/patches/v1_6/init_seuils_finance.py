"""FIN-S51 (RG-FIN-60) — initialize the finance threshold fields in
HMD Configuration.

Same rationale as v1_1/init_pfe_seuils: after migrate, Float fields land as
0.0 in tabSingles (not the JSON default), so `get_config` would return 0 and
disable the coloring / pricing logic. Seed each NON-ZERO default once.

The TB/TP primes (`lait_prime_tb_par_g` / `lait_prime_tp_par_g`) are NOT
seeded: their real default is 0 (no quality indexation until the client
provides the centrale's grid), and 0 must stay a valid configured value.

Idempotent: only sets a field while it is None/0 (uninitialized).
"""
import frappe

FINANCE_DEFAULTS = {
    "prix_reference_lait": 1.6,
    # TB/TP en % — même unité que Bilan Lait Journalier (taux_tb_max_pct=10)
    "lait_tb_reference": 3.8,
    "lait_tp_reference": 3.2,
    "objectif_cout_litre": 0.65,
    "objectif_cout_litre_alarme": 0.85,
    "pfe_iofc_jour_min": 3.0,
    "pfe_iofc_jour_orange_min": 1.5,
}


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    changed = False
    for field, value in FINANCE_DEFAULTS.items():
        current = doc.get(field)
        if current is None or current == 0:
            doc.set(field, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
