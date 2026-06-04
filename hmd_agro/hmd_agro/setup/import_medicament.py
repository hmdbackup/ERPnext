"""Import the Medicament master — 4 real medicaments.

Each auto-creates a MED- Item under its type's Item Group (needs import_stock_setup
+ Company first). The 2 dev test rows (`test`, `TEST-Amoxi`) are excluded.

NOTE: on dev all 4 are tagged ANTIBIOTIQUE — Ivermectine is really an antiparasitaire
and Meloxicam an anti-inflammatoire (mislabeled in the source). Replicated AS-IS to
match the farm data; supervisor can correct the type in the UI later.

Idempotent / dry-run. Run AFTER import_stock_setup.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_medicament.run --kwargs '{"dry_run":1}'
"""
import frappe

# (nom, type_medicament, delai_attente_lait, delai_attente_viande, prix_unitaire)
MEDICAMENTS = [
    ("Amoxicilline",     "ANTIBIOTIQUE", 4,  14, 24),
    ("Ivermectine",      "ANTIBIOTIQUE", 28, 49, 33),   # really antiparasitaire — confirm
    ("Meloxicam",        "ANTIBIOTIQUE", 5,  15, 25),   # really anti-inflammatoire — confirm
    ("Oxytétracycline",  "ANTIBIOTIQUE", 7,  28, 56),
]


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    for nom, type_med, d_lait, d_viande, prix in MEDICAMENTS:
        try:
            if frappe.db.exists("Medicament", nom):
                skipped += 1
                continue
            if not dry_run:
                frappe.get_doc({
                    "doctype": "Medicament",
                    "nom_medicament": nom,
                    "type_medicament": type_med,
                    "delai_attente_lait": d_lait,
                    "delai_attente_viande": d_viande,
                    "prix_unitaire": prix,
                }).insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Medicament import ({len(MEDICAMENTS)}): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    for e in errors[:5]:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "errors": errors}
