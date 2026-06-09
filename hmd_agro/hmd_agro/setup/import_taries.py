"""Dry-off overlay — the CURRENTLY-DRY cows — FINAL step of the re-bake.

Data: `taries.csv` — the 18 cows flagged dry ("T") in med.xlsx, the
LATEST snapshot of who is dry right now. med wins over the cascade, so this runs
LAST (after velage/lactation/insemination), as an authoritative overlay.

For each dry cow we close her CURRENT EN_COURS lactation:
    lactation.date_tarissement = dry-off date
    lactation.statut           = TARIE
The Lactation.on_update hook (sync_animal_etat) then sets Animal.etat_lactation =
TARIE. Gestation is untouched (a dry cow is still GESTANTE — dry = late pregnancy).

DRY-OFF DATE: from Repro2026 (Velage Prévu - 60). CAPPED at today: a cow that is
dry *now* cannot have a dry-off date in the future, so 5 cows whose Velage Prévu is
far out (VP-60 in the future) get today() instead. ⚠️ VERIFY those 5 dry-off dates
against farm records: 2300254551, 2300254570, 2300254582, 2300254592, 2300254598.

Idempotent (skips a lactation already TARIE). Run LAST.

Run (dev):
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_taries.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe
from frappe.utils import getdate, today

from hmd_agro.hmd_agro.setup import data_source


def _load_taries(source):
    """taries.csv -> [(animal_tn, date_tarissement|None), ...]."""
    out = []
    for r in data_source.read(source, "taries.csv"):
        tn = (r.get("identification_tn") or "").strip()
        if tn:
            out.append((tn, data_source.txt(r.get("date_tarissement"))))
    return out


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    set_dry = skipped = 0
    errors, missing_animal, no_lactation, capped = [], [], [], []

    for tn, tar_date in _load_taries(source):
        try:
            if not frappe.db.exists("Animal", tn):
                missing_animal.append(tn)
                continue
            lac = frappe.db.get_value("Lactation",
                {"animal": tn, "statut": "EN_COURS"},
                ["name", "date_debut"], as_dict=True)
            if not lac:
                # already TARIE (idempotent re-run) or no open lactation
                if frappe.db.exists("Lactation", {"animal": tn, "statut": "TARIE"}):
                    skipped += 1
                else:
                    no_lactation.append(tn)
                continue

            # dry-off date: VP-60, capped at today, and never before lactation start
            d = getdate(tar_date) if tar_date else getdate(today())
            if d > getdate(today()):
                d = getdate(today()); capped.append(tn)
            if d < getdate(lac.date_debut):
                d = getdate(today())

            if not dry_run:
                doc = frappe.get_doc("Lactation", lac.name)
                # keep a REAL dry-off date already set from the sheet (import_lactation);
                # only fill our VP-60 estimate when none exists
                if not doc.date_tarissement:
                    doc.date_tarissement = str(d)
                doc.statut = "TARIE"
                doc.save(ignore_permissions=True)   # fires sync_animal_etat -> TARIE
            set_dry += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Tarie overlay (med.xlsx — current dry cows) [FINAL]")
    print(f"  set TARIE={set_dry}, skipped(already tarie)={skipped}, errors={len(errors)}")
    if capped:
        print(f"  dry-off date capped at today ({len(capped)} — VP far future): {capped}")
    if missing_animal:
        print(f"  WARN animal not found: {missing_animal}")
    if no_lactation:
        print(f"  WARN no lactation to close: {no_lactation}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']}: {e['error']}")
    return {"set_dry": set_dry, "skipped": skipped, "capped": capped,
            "missing_animal": missing_animal, "no_lactation": no_lactation, "errors": errors}
