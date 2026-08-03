"""FIN-S25/S31/S32/S42 — initialize the new configuration fields in
HMD Configuration (personnel, cheptel, maintenance, écart lait).

Same rationale as v1_1/v1_6: after migrate, Int/Float fields land as 0.0 in
tabSingles (not the JSON default), and Select fields land empty — so
`get_config` would return 0 / "" and silently disable the logic they drive.
Seed each NON-ZERO default once.

`cheptel_mode` is seeded to NON_VALORISE on purpose: mettre le cheptel au
bilan est une décision comptable du client, pas un effet de bord de migration.
La bascule se fait ensuite en un champ (HMD Configuration → Personnel &
Cheptel) puis `cheptel_valorisation.synchroniser_cheptel`.

Idempotent: only sets a field while it is None/0/"" (uninitialized).
"""
import frappe

DEFAULTS = {
    # FIN-S42 — masse salariale depuis le registre Personnel
    "taux_charges_patronales_pct": 16.57,
    # FIN-S31 — valorisation du cheptel (le mode reste une décision client)
    "cheptel_mode": "NON_VALORISE",
    "cheptel_duree_amortissement_ans": 5,
    "cheptel_cout_elevage": 2500.0,
    # FIN-S25 — écart lait valorisé
    "ecart_lait_seuil_alarme_pct": 10.0,
    # FIN-S32 — entretien des équipements
    "maintenance_seuil_pct_ca": 3.0,
    "maintenance_seuil_alarme_pct_ca": 6.0,
}


def execute():
    if not frappe.db.exists("DocType", "HMD Configuration"):
        return
    doc = frappe.get_single("HMD Configuration")
    changed = False
    for field, value in DEFAULTS.items():
        current = doc.get(field)
        if current is None or current == 0 or current == "":
            doc.set(field, value)
            changed = True
    if changed:
        doc.save(ignore_permissions=True)
        frappe.db.commit()
