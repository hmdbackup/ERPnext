"""Diagnose the Effectif 'Vaches Lactante/Tarie' counts for a date (default today) against
the actual Animal.etat_lactation, and pinpoint WHY each cow differs.

The Effectif report reconstructs lactation status from the LACTATION CHAIN: it takes the
lactation with the latest date_debut <= D and calls the cow TARIE iff that lactation's
date_tarissement is set and <= D, else EN_PRODUCTION. A VACHE with no lactation <= D is
counted as Lactante (resolve_col default). The cow page's etat_lactation, by contrast, is
driven by Lactation.statut. So they disagree whenever a lactation's statut and
date_tarissement are inconsistent (a common result of hand-editing tarissement dates).

Read-only. Run:
    bench --site <site> execute hmd_agro.hmd_agro.setup.diagnose_lactante.run --kwargs '{"date":"2026-06-13"}'
"""
import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.utils.live_state import effectif_on_date


def run(date=None):
    d = getdate(date or today())
    ds = str(d)

    eff = effectif_on_date(d)
    actual_lact = frappe.db.count("Animal",
        {"statut": "ACTIF", "categorie": "VACHE", "etat_lactation": "EN_PRODUCTION"})
    actual_tarie = frappe.db.count("Animal",
        {"statut": "ACTIF", "categorie": "VACHE", "etat_lactation": "TARIE"})

    print(f"\n=== Effectif vs actual @ {ds} ===")
    print(f"  REPORT : Lact={eff['Vaches - Lact.']}  Tarie={eff['Vaches - Tarie']}")
    print(f"  ACTUAL : Lact={actual_lact}  Tarie={actual_tarie}  (Animal.etat_lactation)")
    print(f"  DIFF   : Lact {eff['Vaches - Lact.'] - actual_lact:+d}  "
          f"Tarie {eff['Vaches - Tarie'] - actual_tarie:+d}")

    vaches = frappe.get_all("Animal",
        filters={"statut": "ACTIF", "categorie": "VACHE"},
        fields=["name", "nom_metier", "etat_lactation"])

    no_lac, inconsistent = [], []
    for a in vaches:
        lac = frappe.db.sql("""
            SELECT name, date_debut, date_tarissement, statut
            FROM `tabLactation` WHERE animal=%s AND date_debut<=%s
            ORDER BY date_debut DESC LIMIT 1
        """, (a.name, ds), as_dict=True)
        if not lac:
            recon = "EN_PRODUCTION"
            detail = "NO LACTATION <= date"
            no_lac.append((a.nom_metier or a.name, a.etat_lactation))
        else:
            l = lac[0]
            recon = "TARIE" if (l.date_tarissement and getdate(l.date_tarissement) <= d) else "EN_PRODUCTION"
            detail = f"latest_lac statut={l.statut} taris={l.date_tarissement} debut={l.date_debut}"
        if recon != (a.etat_lactation or ""):
            inconsistent.append((a.nom_metier or a.name, a.etat_lactation, recon, detail))

    print(f"\n  {len(inconsistent)} cows where REPORT disagrees with etat_lactation:")
    for nm, etat, recon, det in inconsistent:
        print(f"   {nm}: etat={etat or '∅'} | report={recon} | {det}")

    if no_lac:
        print(f"\n  {len(no_lac)} VACHE with NO lactation <= date (report counts these as Lactante):")
        for nm, etat in no_lac:
            print(f"   {nm}: etat={etat or '∅'}")

    return {"report_lact": eff["Vaches - Lact."], "actual_lact": actual_lact,
            "report_tarie": eff["Vaches - Tarie"], "actual_tarie": actual_tarie,
            "mismatches": len(inconsistent), "vache_no_lactation": len(no_lac)}
