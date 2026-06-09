"""Import the feed (Aliment) master — reads aliments.csv.

Generic: farm data lives in an external CSV (see data_source.py), not baked here.
CSV columns: nom, type_aliment, prix_unitaire, ms_pct (ms_pct may be blank).
unite is always KG. Each Aliment auto-creates an ALI- Item under its type's Item Group.

PREREQUISITE: import_stock_setup (item groups + warehouse) + Company hmd-agro.
Idempotent / dry-run. Run AFTER import_stock_setup.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_aliment.run --kwargs '{"dry_run":1}'
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    rows = data_source.read(source, "aliments.csv")
    for r in rows:
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue
        try:
            if frappe.db.exists("Aliment", nom):
                skipped += 1
                continue
            doc_dict = {
                "doctype": "Aliment",
                "nom_aliment": nom,
                "type_aliment": (r.get("type_aliment") or "").strip(),
                "unite": "KG",
                "prix_unitaire": data_source.num(r.get("prix_unitaire")),
            }
            ms = data_source.num(r.get("ms_pct"))
            if ms is not None:
                doc_dict["ms_pct"] = ms
            if not dry_run:
                frappe.get_doc(doc_dict).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Aliment import (CSV, {len(rows)} feeds): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors[:5]:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
