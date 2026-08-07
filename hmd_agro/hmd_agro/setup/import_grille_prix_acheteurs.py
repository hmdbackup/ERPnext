"""Create one Grille Prix Lait per milk buyer, from the farm's price note.

Source — `Lait 08-2026.txt`, sent by the farm on 07/08/2026:

    Borj Lella : 2,370 DT/litre   (≈ 400 L tous les 2 jours)
    Souani     : 2,200 DT/litre   (le reste)

Flat price per buyer, no quality grid: the centrale's TB/TP schedule has still
not been received, so the grids are created `PROVISOIRE` with no paliers.

DATE OF EFFECT — the note is dated August 2026 and says nothing about earlier
months, so `date_debut` defaults to 2026-08-01. The daily balances imported for
January→June therefore carry NO price and produce no CA lait. Re-run with an
earlier `date_debut` once the farm confirms the prices were unchanged over the
period; do not assume it here.

Idempotent (skips a buyer that already has a grid) / dry-run.
Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_grille_prix_acheteurs.run --kwargs '{"dry_run": 1}'
"""
import frappe

SOURCE = "Note ferme « Lait 08-2026 » du 07/08/2026 — prix de base, hors grille qualité."

# acheteur -> (prix de base DT/L, commentaire volume)
PRIX = {
    "Borj Lella": (2.370, "≈ 400 L tous les 2 jours"),
    "SOUANI": (2.200, "le reste de la collecte"),
}


def run(dry_run=True, date_debut="2026-08-01"):
    dry_run = int(dry_run)
    created, skipped, missing = [], [], []

    for acheteur, (prix, volume) in PRIX.items():
        if not frappe.db.exists("Customer", acheteur):
            missing.append(acheteur)
            continue
        if frappe.db.exists("Grille Prix Lait", {"centrale": acheteur}):
            skipped.append(acheteur)
            continue

        doc = {
            "doctype": "Grille Prix Lait",
            "nom_grille": f"Prix {acheteur} {date_debut[:4]}",
            "centrale": acheteur,
            "statut": "PROVISOIRE",
            "active": 1,
            "date_debut": date_debut,
            "prix_base": prix,
            "source": SOURCE,
            "notes": f"Volume habituel : {volume}. Grille qualité non communiquée.",
        }
        if not dry_run:
            frappe.get_doc(doc).insert(ignore_permissions=True)
        created.append(f"{acheteur} @ {prix} DT/L")

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Grilles de prix par acheteur — en vigueur au {date_debut}")
    print(f"  créées  : {created or 'aucune'}")
    print(f"  ignorées (grille déjà existante) : {skipped or 'aucune'}")
    if missing:
        print(f"  ! acheteur introuvable en base : {missing} — importer les bilans lait d'abord")
    return {"mode": mode, "created": created, "skipped": skipped, "missing": missing}
