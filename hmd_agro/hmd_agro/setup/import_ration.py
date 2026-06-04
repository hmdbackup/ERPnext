"""Import the Ration master — 2 rations with their compositions.

Rations reference Aliments in their composition (child table), and cout_estime /
sous_total auto-compute from current aliment prices on save. So Aliments must exist
first. These are the rations Lots get assigned to via "Affecter aux lots".

PREREQUISITE: import_aliment (compositions reference Mais, Soja, Dreche, Foin d'Avoine).
Idempotent / dry-run. Run AFTER import_aliment.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_ration.run --kwargs '{"dry_run":1}'
"""
import frappe

# nom_ration -> composition: [(aliment, quantite_kg), ...]
RATIONS = {
    "Ration VL HP":  [("Mais", 1.5), ("Soja", 1.5), ("Dreche de Brasserie", 7.0)],
    "Ration VL THP": [("Mais", 2.5), ("Soja", 2.0), ("Foin d'Avoine", 8.0)],
}


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    missing_aliment = []

    for nom, comp in RATIONS.items():
        try:
            if frappe.db.exists("Ration", nom):
                skipped += 1
                continue
            # verify the composition's aliments exist (else the link fails)
            absent = [a for a, _ in comp if not frappe.db.exists("Aliment", a)]
            if absent:
                missing_aliment.append((nom, absent))
                continue
            if not dry_run:
                doc = frappe.get_doc({
                    "doctype": "Ration",
                    "nom_ration": nom,
                    "active": 1,
                    "composition": [
                        {"aliment": a, "quantite": q, "unite": "KG"} for a, q in comp
                    ],
                })
                doc.insert(ignore_permissions=True)
            created += 1
        except Exception as e:
            errors.append({"nom": nom, "error": str(e)})

    if not dry_run:
        frappe.db.commit()
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Ration import ({len(RATIONS)}): "
          f"created={created}, skipped(existing)={skipped}, errors={len(errors)}")
    if missing_aliment:
        print(f"  ABORTED rations (missing aliments — run import_aliment first): {missing_aliment}")
    for e in errors[:5]:
        print(f"  ERR {e['nom']}: {e['error']}")
    return {"created": created, "skipped": skipped, "missing_aliment": missing_aliment, "errors": errors}
