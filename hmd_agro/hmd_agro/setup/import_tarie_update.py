"""Tarie reconcile — authoritative current-dry overlay from the fresh ETABLE HMD 2026.

Background: the original import set 18 TARIE from med.xlsx; 5 of those were flagged
in import_taries.py as VP-60-capped-at-today (i.e. "verify — maybe not really dry").
The fresh Repro2026 tarissement column gives 25 currently-dry cows, and confirms those
5 are lactating again. This script reconciles the clone/prod to that fresh truth.

Data: `tarie_update.csv` (identification_tn, date_tarissement) — the 25 cows that are
CURRENTLY dry (tarissement date already passed, no calving since). Logic:
  - cow in the list, lactation EN_COURS -> set TARIE (+ date_tarissement)  [12 expected]
  - cow in the list, already TARIE       -> skip, keep existing date       [13 expected]
  - cow currently TARIE but NOT in list  -> revert lactation to EN_COURS    [5 expected]
                                            (un-dry; clears the estimated date)

Mechanism mirrors import_taries: edits the Lactation doc so Lactation.on_update
(sync_animal_etat) flips Animal.etat_lactation. ORM, idempotent, dry-run by default.
Target end state: 74 EN_PRODUCTION / 25 TARIE.

Run (dev/clone):
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_tarie_update.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.setup import data_source


def _load(source):
    """tarie_update.csv -> {animal_tn: date_tarissement|None}."""
    out = {}
    for r in data_source.read(source, "tarie_update.csv"):
        tn = (r.get("identification_tn") or "").strip()
        if tn:
            out[tn] = data_source.txt(r.get("date_tarissement"))
    return out


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    dry_list = _load(source)
    set_dry = skipped = undried = 0
    missing_animal, no_lactation, errors = [], [], []

    # 1) ensure each listed cow is TARIE
    for tn, tar_date in dry_list.items():
        try:
            if not frappe.db.exists("Animal", tn):
                missing_animal.append(tn)
                continue
            lac = frappe.db.get_value("Lactation",
                {"animal": tn, "statut": "EN_COURS"},
                ["name", "date_debut"], as_dict=True)
            if not lac:
                if frappe.db.exists("Lactation", {"animal": tn, "statut": "TARIE"}):
                    skipped += 1   # idempotent: already dry, keep its real date
                else:
                    no_lactation.append(tn)
                continue

            d = getdate(tar_date) if tar_date else None
            if d and d < getdate(lac.date_debut):
                d = getdate(lac.date_debut)   # never before lactation start (ERR-LAC-04)

            if not dry_run:
                doc = frappe.get_doc("Lactation", lac.name)
                if d and not doc.date_tarissement:
                    doc.date_tarissement = str(d)
                doc.statut = "TARIE"
                doc.save(ignore_permissions=True)   # fires sync_animal_etat -> TARIE
            set_dry += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    # 2) revert cows currently TARIE but NOT in the fresh dry list (un-dry)
    current_tarie = frappe.get_all("Animal",
        filters={"statut": "ACTIF", "etat_lactation": "TARIE"}, pluck="name")
    for tn in current_tarie:
        if tn in dry_list:
            continue
        try:
            # reopen the LATEST lactation (highest date_debut), never an old one —
            # picking an arbitrary TARIE lactation here would invert the chain (an old
            # lactation EN_COURS while the newest stays TARIE) and mis-route recent traites.
            lac = frappe.db.get_value("Lactation", {"animal": tn, "statut": "TARIE"}, "name",
                                      order_by="date_debut desc")
            if not lac:
                continue
            if not dry_run:
                doc = frappe.get_doc("Lactation", lac)
                doc.date_tarissement = None
                doc.statut = "EN_COURS"   # TARIE -> EN_COURS is an allowed transition
                doc.save(ignore_permissions=True)   # fires sync_animal_etat -> EN_PRODUCTION
            undried += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e), "phase": "undry"})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Tarie reconcile (fresh ETABLE HMD 2026)")
    print(f"  listed dry={len(dry_list)}  newly set TARIE={set_dry}  "
          f"already TARIE (skipped)={skipped}  un-dried (TARIE->EN_COURS)={undried}  "
          f"errors={len(errors)}")
    print(f"  => expected end state: {74} EN_PRODUCTION / {25} TARIE")
    if missing_animal:
        print(f"  WARN animal not found: {missing_animal}")
    if no_lactation:
        print(f"  WARN no lactation to close: {no_lactation}")
    for e in errors[:8]:
        print(f"  ERR {e.get('tn')}: {e.get('error')}")
    return {"set_dry": set_dry, "skipped": skipped, "undried": undried,
            "missing_animal": missing_animal, "no_lactation": no_lactation,
            "errors": errors}
