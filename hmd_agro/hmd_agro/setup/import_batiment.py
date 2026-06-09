"""Import Batiment(s) — reads batiments.csv. Prerequisite for Lots and Animals.

Generic: farm data in an external CSV (see data_source.py), not baked here.
CSV columns: nom, type.  actif defaults to 1.
Idempotent / dry-run. Run BEFORE import_lot.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_batiment.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    for r in data_source.read(source, "batiments.csv"):
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue
        try:
            if frappe.db.exists("Batiment", nom):
                skipped += 1
                continue
            if not dry_run:
                frappe.get_doc({
                    "doctype": "Batiment",
                    "nom_batiment": nom,
                    "type_batiment": (r.get("type") or "").strip(),
                    "actif": 1,
                }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Batiment import (CSV): created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
