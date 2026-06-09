"""Import the Medicament master — reads medicaments.csv.

Generic: farm data in an external CSV (see data_source.py), not baked here.
CSV columns: nom, type_medicament, delai_attente_lait, delai_attente_viande, prix_unitaire.
Each auto-creates a MED- Item under its type's Item Group (needs import_stock_setup
+ Company first).

Idempotent / dry-run. Run AFTER import_stock_setup.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_medicament.run --kwargs '{"dry_run":1}'
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    rows = data_source.read(source, "medicaments.csv")
    for r in rows:
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue
        try:
            if frappe.db.exists("Medicament", nom):
                skipped += 1
                continue
            if not dry_run:
                frappe.get_doc({
                    "doctype": "Medicament",
                    "nom_medicament": nom,
                    "type_medicament": (r.get("type_medicament") or "").strip(),
                    "delai_attente_lait": data_source.num(r.get("delai_attente_lait"), int),
                    "delai_attente_viande": data_source.num(r.get("delai_attente_viande"), int),
                    "prix_unitaire": data_source.num(r.get("prix_unitaire")),
                }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Medicament import (CSV, {len(rows)}): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors[:5]:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
