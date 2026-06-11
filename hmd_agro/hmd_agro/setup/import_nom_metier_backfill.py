"""Recompute nom_metier (N° travail) for existing Animals.

Why: the original import set nom_metier = identification_tn[-4:], then identification_fr was
backfilled later via db.set_value (which does not re-run Animal.set_nom_metier). So every
FR-tagged cow still shows the Tunisian last-4 instead of the French N°. The rule is:
    nom_metier = identification_fr[-4:] if id_fr exists, else identification_tn[-4:].

This applies that rule directly via db.set_value (no doc.save → no validate, no cascades).
Pairs with the animal.py fix that makes set_nom_metier take id_fr's last 4 regardless of
length (so future saves stay correct). Idempotent, dry-run by default.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_nom_metier_backfill.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe


def _expected(id_fr, id_tn):
    if id_fr and id_fr.isdigit():
        return id_fr[-4:]
    if id_tn and id_tn.isdigit() and len(id_tn) == 10:
        return id_tn[-4:]
    return ""


def run(dry_run=True):
    dry_run = int(dry_run)
    rows = frappe.get_all("Animal", fields=["name", "identification_tn", "identification_fr", "nom_metier"])
    fixed = unchanged = 0
    samples = []
    for a in rows:
        want = _expected((a.identification_fr or "").strip(), (a.identification_tn or "").strip())
        if want and want != (a.nom_metier or ""):
            if len(samples) < 10:
                samples.append((a.name, a.identification_fr, a.nom_metier, "->", want))
            if not dry_run:
                frappe.db.set_value("Animal", a.name, "nom_metier", want, update_modified=False)
            fixed += 1
        else:
            unchanged += 1

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] nom_metier backfill")
    print(f"  would-fix={fixed}, unchanged={unchanged}, total={len(rows)}")
    for s in samples:
        print(f"  {s[0]}  id_fr={s[1]}  nom_metier {s[2]} {s[3]} {s[4]}")
    return {"fixed": fixed, "unchanged": unchanged, "total": len(rows)}
