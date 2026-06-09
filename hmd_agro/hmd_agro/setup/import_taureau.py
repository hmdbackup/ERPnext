"""Import Taureau (sire) records — reads taureaux.csv.

Generic: the farm data lives in an external CSV (see data_source.py), not baked here.
CSV columns: nom, izu, lait.  Race defaults to "Holstein"; code_taureau = nom.
Idempotent (skips existing) / dry-run.

Run:
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_taureau.run --kwargs '{"dry_run": 1}'
    (override the CSV folder with "source": "/path/to/data")
Set dry_run=0 to commit.
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    posted, skipped, errors = 0, 0, []

    for row in data_source.read(source, "taureaux.csv"):
        nom = (row.get("nom") or "").strip()
        if not nom:
            continue
        try:
            if frappe.db.exists("Taureau", nom):
                skipped += 1
                continue
            doc = frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": nom,
                "code_taureau": nom,
                "race": "Holstein",
                "izu": data_source.num(row.get("izu"), int),
                "lait": data_source.num(row.get("lait"), int),
            })
            if not dry_run:
                doc.insert(ignore_permissions=True)
            posted += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Taureau import (CSV): posted={posted}, skipped={skipped}, errors={len(errors)}")
    for e in errors[:5]:
        print(f"  {e['nom']}: {e['error']}")
    return {"posted": posted, "skipped": skipped, "errors": errors}
