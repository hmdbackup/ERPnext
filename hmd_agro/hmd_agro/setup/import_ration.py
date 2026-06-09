"""Import the Ration master — reads rations.csv (one row per composition line).

Generic: farm data in an external CSV (see data_source.py), not baked here.
CSV columns: nom_ration, aliment, quantite (grouped by nom_ration into a composition).
unite is always KG. cout_estime / sous_total auto-compute from aliment prices on save,
so Aliments must exist first.

PREREQUISITE: import_aliment. Idempotent / dry-run. Run AFTER import_aliment.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_ration.run --kwargs '{"dry_run":1}'
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    missing_aliment = []

    # group CSV rows by ration -> [(aliment, quantite), ...]
    rations = {}
    for r in data_source.read(source, "rations.csv"):
        nom = (r.get("nom_ration") or "").strip()
        aliment = (r.get("aliment") or "").strip()
        if not nom or not aliment:
            continue
        rations.setdefault(nom, []).append((aliment, data_source.num(r.get("quantite"))))

    for nom, comp in rations.items():
        try:
            if frappe.db.exists("Ration", nom):
                skipped += 1
                continue
            absent = [a for a, _ in comp if not frappe.db.exists("Aliment", a)]
            if absent:
                missing_aliment.append((nom, absent))
                continue
            if not dry_run:
                frappe.get_doc({
                    "doctype": "Ration",
                    "nom_ration": nom,
                    "active": 1,
                    "composition": [
                        {"aliment": a, "quantite": q, "unite": "KG"} for a, q in comp
                    ],
                }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Ration import (CSV, {len(rations)}): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    if missing_aliment:
        print(f"  ABORTED rations (missing aliments — run import_aliment first): {missing_aliment}")
    for e in errors[:5]:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "missing_aliment": missing_aliment, "errors": errors}
