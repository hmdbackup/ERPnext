"""Import the FIRST-cycle (heifer) inseminations for the ex-génisses — reads genisses_ia.csv.

Generic: farm data in an external CSV (see data_source.py), not baked here.
CSV columns: identification_tn, date_ia, taureau, resultat  (one row per IA, ascending;
resultat = REUSSIE for the fecundating IA, else ECHOUEE — precomputed at generation).

These are CLOSED past pregnancies, so they must NOT fire the gestation cascade: insert
with resultat=EN_ATTENTE, then db.set_value the final result → bypasses
Insemination.on_update (update_animal_on_resultat). The fecundating IA is then linked to
the cow's first velage. lactation=None (heifer IA precedes the first lactation).

Idempotent on (animal, date_ia). Run AFTER import_velage + import_insemination.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_insemination_genisses.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
from collections import OrderedDict

import frappe

from hmd_agro.hmd_agro.setup import data_source


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = reussie = velage_linked = 0
    errors = []
    no_fecundating = []

    # group CSV rows by cow, preserving order
    cows = OrderedDict()
    for r in data_source.read(source, "genisses_ia.csv"):
        tn = (r.get("identification_tn") or "").strip()
        date = (r.get("date_ia") or "").strip()
        if not tn or not date:
            continue
        cows.setdefault(tn, []).append(
            (date, data_source.txt(r.get("taureau")), (r.get("resultat") or "").strip()))

    for tn, ias in cows.items():
        if not frappe.db.exists("Animal", tn):
            errors.append({"tn": tn, "error": "animal not found"})
            continue
        if not any(res == "REUSSIE" for _, _, res in ias):
            no_fecundating.append(tn)

        fecundating_ia_name = None
        for i, (date, taureau, resultat) in enumerate(ias):
            if taureau and not frappe.db.exists("Taureau", taureau):
                errors.append({"tn": tn, "date": date, "error": f"taureau {taureau} not found"})
                continue
            try:
                existing = frappe.db.exists("Insemination", {"animal": tn, "date_ia": date})
                if existing:
                    skipped += 1
                    if resultat == "REUSSIE":
                        fecundating_ia_name = existing
                    continue
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Insemination",
                        "animal": tn,
                        "date_ia": date,
                        "taureau": taureau,
                        "type_semence": "CONVENTIONNELLE",
                        "resultat": "EN_ATTENTE",   # pending first, then set final via db (no cascade)
                        "numero_ia": i + 1,
                        "lactation": None,
                    })
                    doc.flags.ignore_validate = True
                    doc.flags.ignore_mandatory = True
                    doc.flags.skip_semence_decrement = True
                    doc.insert(ignore_permissions=True)
                    frappe.db.set_value("Insemination", doc.name, "resultat", resultat)
                    if resultat == "REUSSIE":
                        fecundating_ia_name = doc.name
                created += 1
                if resultat == "REUSSIE":
                    reussie += 1
            except Exception as e:
                errors.append({"tn": tn, "date": date, "error": str(e)})

        if not dry_run and fecundating_ia_name:
            first_velage = frappe.db.get_value("Velage", {"animal": tn}, "name",
                                               order_by="date_velage asc")
            if first_velage and not frappe.db.get_value("Velage", first_velage, "insemination"):
                frappe.db.set_value("Velage", first_velage, "insemination", fecundating_ia_name)
                velage_linked += 1

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Insemination import — first cycle (ex-génisses, CSV)")
    print(f"  IA records would-create={created} (REUSSIE={reussie}), skipped(existing)={skipped}, errors={len(errors)}")
    print(f"  fecundating IA linked to first velage: {velage_linked}")
    print(f"  cows with NO fecundating match (all ECHOUEE, gap): {no_fecundating}")
    for e in errors[:5]:
        print(f"  ERR {e.get('tn')} {e.get('date','')}: {e['error']}")

    return {"created": created, "reussie": reussie, "skipped": skipped,
            "velage_linked": velage_linked, "no_fecundating": no_fecundating, "errors": errors}
