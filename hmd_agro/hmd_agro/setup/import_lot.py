"""Import the 12 real farm lots — prerequisite for import_animal (cows need id_lot).

Replicates the real lots from the current system. NOT included: the 5 test lots
(*-TEST-*, Test Lot *). All lots are placed in bat-velage-1 (the 4 that pointed at
test batiments — COLLECTIVE/INFIRMERIE/TARISSEMENT/GENISSE — are repointed here).

`id_ration_actuelle` is intentionally LEFT EMPTY (optional field, normally synced from
the "Affecter aux lots" flow which builds Lot Ration History). Assign rations that way
after import — keeps this clean and avoids a Ration dependency.

Required Lot fields covered: nom, batiment, superficie_m2, capacite_optimale,
capacite_maximale. Idempotent / dry-run. Run AFTER import_batiment, BEFORE import_animal.

Run (dev):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_lot.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

BATIMENT = "bat-velage-1"

# (nom, lot_type|None, superficie_m2, capacite_optimale, capacite_maximale,
#  seuil_production_3j|None, adapte_hautes_performances)
LOTS = [
    ("Individuel",  None,          100, 30, 40, None, 0),
    ("LOT1",        "THP",         200, 15, 20, 30,   1),
    ("LOT2",        "HP",          50,  9,  10, 25,   1),
    ("LOT3",        "FV",          20,  5,  10, None, 0),
    ("LOT4",        "MP",          80,  5,  5,  12,   1),
    ("LOT5",        "FP",          80,  9,  11, None, 0),
    ("TARIE",       "TARIE",       20,  6,  10, None, 0),
    ("TARISSEMENT", "TARISSEMENT", 30,  10, 12, None, 0),
    ("COLLECTIVE",  None,          10,  15, 20, None, 0),
    ("INFIRMERIE",  None,          100, 20, 30, None, 0),
    ("GENISSE",     None,          50,  33, 40, None, 0),
    ("VELLE",       None,          50,  35, 40, None, 0),
]


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []

    if not frappe.db.exists("Batiment", BATIMENT):
        print(f"[ABORT] Batiment '{BATIMENT}' missing — run import_batiment first.")
        return {"aborted": True}

    for nom, lot_type, superf, cap_opt, cap_max, seuil, hp in LOTS:
        try:
            if frappe.db.exists("Lot", nom):
                skipped += 1
                continue
            doc_dict = {
                "doctype": "Lot",
                "nom": nom,
                "batiment": BATIMENT,
                "superficie_m2": superf,
                "capacite_optimale": cap_opt,
                "capacite_maximale": cap_max,
                "actif": 1,
                "adapte_hautes_performances": hp,
            }
            if lot_type:
                doc_dict["lot_type"] = lot_type
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
    print(f"\n[{mode}] Lot import (12 real lots, batiment={BATIMENT}): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
