"""Scoped RESET of the reproduction layer — FIRST step of the 2026 re-bake.

Clears ONLY the reproduction records and the cows' reproduction-state fields, so the
re-bake (velage -> lactation -> insemination -> genisses -> taries) starts from a
clean, fully-derivable state. Everything else is untouched:
  KEPT: Company, stock (Aliment/Medicament/Ration/Items), Batiment, Lot, Taureau,
        and the Animal records themselves (identity, dams, birth dates, lot, est_achat).
  WIPED: tabVelage, tabLactation, tabInsemination, and (derived) tabAlerte.
  RESET on tabAnimal: etat_gestation, etat_lactation, date_velage_prevue,
        id_ia_fecondante, date_tarissement, date_premier_velage.

Done via raw SQL to bypass the doctype on_trash guards (Lactation.on_trash blocks
while velages/IAs exist; deleting in any order via SQL avoids that). frappe.clear_cache()
after, so the UI reflects the empty state.

⚠️ DESTRUCTIVE within its scope. Run ONLY as the first step of a full re-bake, and
ONLY after a backup. dry_run prints what WOULD be deleted.

Run (dev):
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_reset_reproduction.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

WIPE = ["Insemination", "Lactation", "Velage", "Alerte"]
ANIMAL_FIELDS = [
    "etat_gestation", "etat_lactation", "date_velage_prevue",
    "id_ia_fecondante", "date_tarissement", "date_premier_velage",
]


def run(dry_run=True):
    dry_run = int(dry_run)
    counts = {dt: frappe.db.count(dt) for dt in WIPE}
    n_animals = frappe.db.count("Animal")

    if not dry_run:
        for dt in WIPE:
            frappe.db.sql(f"DELETE FROM `tab{dt}`")
        sets = ", ".join(
            (f"`{f}`=''" if f in ("etat_gestation", "etat_lactation") else f"`{f}`=NULL")
            for f in ANIMAL_FIELDS
        )
        # etat_gestation back to the VIDE default; etat_lactation cleared
        frappe.db.sql(f"UPDATE `tabAnimal` SET {sets}")
        frappe.db.sql("UPDATE `tabAnimal` SET `etat_gestation`='VIDE'")
        frappe.db.commit()
        frappe.clear_cache()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Reset reproduction layer")
    for dt in WIPE:
        print(f"  {'would delete' if dry_run else 'deleted'} {counts[dt]:>4} {dt}")
    print(f"  {'would reset' if dry_run else 'reset'} reproduction fields on {n_animals} Animal rows")
    print(f"  (kept: Company/stock/Batiment/Lot/Taureau/Animal identity)")
    return {"deleted": counts, "animals_reset": n_animals}
