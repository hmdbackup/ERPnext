"""Import farm lots — reads lots.csv. Prerequisite for import_animal (cows need id_lot).

Generic: farm data in an external CSV (see data_source.py), not baked here.
CSV columns: nom, lot_type, superficie, cap_optimale, cap_max, seuil, hp
(lot_type / seuil may be blank). All lots placed in bat-velage-1.
`id_ration_actuelle` left empty on purpose (assigned later via "Affecter aux lots").

Idempotent / dry-run. Run AFTER import_batiment, BEFORE import_animal.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_lot.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source

BATIMENT = "bat-velage-1"


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []

    if not frappe.db.exists("Batiment", BATIMENT):
        print(f"[ABORT] Batiment '{BATIMENT}' missing — run import_batiment first.")
        return {"aborted": True}

    rows = data_source.read(source, "lots.csv")
    for r in rows:
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue
        try:
            if frappe.db.exists("Lot", nom):
                skipped += 1
                continue
            doc_dict = {
                "doctype": "Lot",
                "nom": nom,
                "batiment": BATIMENT,
                "superficie_m2": data_source.num(r.get("superficie")),
                "capacite_optimale": data_source.num(r.get("cap_optimale"), int),
                "capacite_maximale": data_source.num(r.get("cap_max"), int),
                "actif": 1,
                "adapte_hautes_performances": data_source.num(r.get("hp"), int) or 0,
            }
            lot_type = data_source.txt(r.get("lot_type"))
            if lot_type:
                doc_dict["lot_type"] = lot_type
            seuil = data_source.num(r.get("seuil"), int)
            if seuil is not None:
                doc_dict["seuil_production_3j"] = seuil
            if not dry_run:
                frappe.get_doc(doc_dict).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Lot import (CSV, {len(rows)} lots, batiment={BATIMENT}): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
