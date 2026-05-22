"""Generate synthetic Traites to fill the gap between the last imported
data and yesterday. Idempotent — skips if a Traite already exists for
(animal, date, session).

Usage:
  bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.seed_recent_traites.run
  bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.seed_recent_traites.run \
        --kwargs '{"dry_run": 1}'
"""
import random

import frappe
from frappe.utils import add_days, getdate, today


def daily_litres_for_dim(dim):
    """Piecewise lactation curve for an average-performing Holstein.
    Returns total daily litres (sum of MATIN + SOIR)."""
    if dim < 0:
        return 0
    if dim < 10:
        return 12 + (25 - 12) * (dim / 10)              # ramp 12 → 25
    if dim < 60:
        return 25 + (38 - 25) * ((dim - 10) / 50)       # ramp to peak 38
    if dim < 120:
        return 38 - (38 - 32) * ((dim - 60) / 60)       # decline 38 → 32
    if dim < 240:
        return 32 - (32 - 22) * ((dim - 120) / 120)     # decline 32 → 22
    if dim < 305:
        return 22 - (22 - 14) * ((dim - 240) / 65)      # decline 22 → 14
    return 14


def perf_multiplier(animal_name):
    """Stable per-cow multiplier (0.65 to 1.25) so each cow keeps a
    consistent profile across days. Hash-based → reproducible."""
    h = hash(animal_name) % 1000
    return 0.65 + (h / 1000) * 0.60


def run(start=None, end=None, dry_run=0):
    end = getdate(end) if end else getdate(add_days(today(), -1))
    start = getdate(start) if start else add_days(end, -6)

    rows = frappe.db.sql("""
        SELECT l.name AS lact, l.animal, l.date_debut
        FROM `tabLactation` l
        INNER JOIN `tabAnimal` a ON a.name = l.animal
        WHERE l.statut = 'EN_COURS' AND a.statut = 'ACTIF'
    """, as_dict=True)

    print(f"\n=== Generating Traites for {len(rows)} cows ===")
    print(f"Date range: {start} → {end}  ({(end - start).days + 1} days)")
    print(f"Mode: {'DRY-RUN' if dry_run else 'INSERT'}\n")

    inserted, skipped = 0, 0
    for r in rows:
        debut = getdate(r.date_debut)
        mult = perf_multiplier(r.animal)
        for d_offset in range((end - start).days + 1):
            date = add_days(start, d_offset)
            dim = (date - debut).days
            if dim < 0:
                continue
            base = daily_litres_for_dim(dim) * mult
            base *= random.uniform(0.92, 1.08)
            for sess, share in [("MATIN", 0.55), ("SOIR", 0.45)]:
                if frappe.db.exists("Traite", {
                    "animal": r.animal, "date_traite": date, "session": sess
                }):
                    skipped += 1
                    continue
                qty = round(base * share, 1)
                if dry_run:
                    inserted += 1
                    continue
                frappe.get_doc({
                    "doctype": "Traite",
                    "animal": r.animal,
                    "date_traite": date,
                    "session": sess,
                    "quantite_litres": qty,
                }).insert(ignore_permissions=True)
                inserted += 1

    if not dry_run:
        frappe.db.commit()

    print(f"  {'WOULD INSERT' if dry_run else 'INSERTED'}: {inserted}")
    print(f"  SKIPPED (already exists): {skipped}")
