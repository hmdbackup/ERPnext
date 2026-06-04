"""Import Batiment(s) — prerequisite for Lots and Animals (Lot.batiment is required).

All 12 real lots reference a single building (bat-velage-1) after repointing the
4 that pointed at test batiments, so only this one Batiment is needed.

Idempotent / dry-run. Run BEFORE import_lot.

Run (dev):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_batiment.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

# (nom_batiment, type_batiment)
BATIMENTS = [
    ("bat-velage-1", "ELEVAGE"),
]


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    for nom, type_bat in BATIMENTS:
        try:
            if frappe.db.exists("Batiment", nom):
                skipped += 1
                continue
            if not dry_run:
                frappe.get_doc({
                    "doctype": "Batiment",
                    "nom_batiment": nom,
                    "type_batiment": type_bat,
                    "actif": 1,
                }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Batiment import: created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
