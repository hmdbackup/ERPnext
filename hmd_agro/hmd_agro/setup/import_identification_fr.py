"""Backfill Animal.identification_fr from a CSV — GENERIC, non-baked.

The Traite import (and any milk file) can match a row keyed by the French working
number (N°Fr) only if each cow's `identification_fr` is recorded. Cows were imported
without it. This reads a CSV of (identification_tn, identification_fr) pairs — per-farm
DATA, kept OUTSIDE the code — and sets the field on each matching Animal.

CSV format (header required):
    identification_tn,identification_fr
    2300254525,2876
    ...

No farm-specific data is baked here; pass the CSV path. Idempotent (skips rows
already correct), dry-run aware.

Run:
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_identification_fr.run \
        --kwargs '{"source":"/path/to/identification_fr.csv","dry_run":1}'
Set dry_run=0 to commit.
"""
import csv
import frappe


def run(source, dry_run=True):
    dry_run = int(dry_run)
    set_ = same = 0
    errors, missing = [], []

    with open(source, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        tn = (row.get("identification_tn") or "").strip()
        fr = (row.get("identification_fr") or "").strip()
        if not tn or not fr:
            continue
        try:
            if not frappe.db.exists("Animal", tn):
                missing.append(tn)
                continue
            current = frappe.db.get_value("Animal", tn, "identification_fr")
            if str(current or "").strip() == fr:
                same += 1
                continue
            if not dry_run:
                frappe.db.set_value("Animal", tn, "identification_fr", fr)
            set_ += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] identification_fr backfill (source: {source})")
    print(f"  rows={len(rows)} | set={set_} | already-correct={same} | "
          f"animal-not-found={len(missing)} | errors={len(errors)}")
    if missing:
        print(f"  WARN not found ({len(missing)}): {missing[:20]}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']}: {e['error']}")
    return {"set": set_, "same": same, "missing": missing, "errors": errors}
