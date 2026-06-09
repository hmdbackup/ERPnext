"""Import historical velages (calving events) for the current herd — Phase 2a.

Data: `repro_2026_data.VELAGES` — AUTO-GENERATED from ETABLE HMD 2026.xlsx
(Repro2026 V1-V5 columns), joined to the 99 current cows. 325 velages across 99
cows, each cow's dates sorted oldest->newest. Re-bake supersedes the old REPRO2025
snapshot (adds the 7 new 2026 calvings + 1 corrected date).

WHAT THIS DOES / WHY IT IS SAFE
  We import each velage as a BARE CALVING EVENT (date only). The sheet has no
  reliable per-velage calf identity, so we do NOT record calves.
  CRITICAL: Velage.after_insert ALWAYS runs (ignore_validate does not skip it):
    - create_calves()    -> we set vivant_veau1=0 so NO calves are created.
    - create_lactation() -> opens a Lactation EN_COURS, auto-closes the previous one
                            as TARIE. Inserting oldest->newest builds the chain.
    - update_mother()    -> resets gestation to VIDE.
  We then set date_premier_velage ourselves (the cascade skips already-VACHE cows).

ORDER: velages for a cow must be inserted ascending by date (the list is pre-sorted).
Run AFTER import_reset_reproduction (clean slate) and import_taureau.
Idempotent on (animal, date_velage).

Run (dev):
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_velage.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

from hmd_agro.hmd_agro.setup.repro_2026_data import VELAGES


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = 0
    cows_done = 0
    errors = []
    missing_animal = []

    for tn, dates in VELAGES:
        if not frappe.db.exists("Animal", tn):
            missing_animal.append(tn)
            continue
        cows_done += 1
        for date in dates:  # ascending — required for the lactation chain
            try:
                if frappe.db.exists("Velage", {"animal": tn, "date_velage": date}):
                    skipped += 1
                    continue
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Velage",
                        "animal": tn,
                        "date_velage": date,
                        "type_velage": "FACILE",   # source has no type; benign default
                        "nombre_veaux": "1",
                        "vivant_veau1": 0,          # CRITICAL: suppress calf creation
                    })
                    doc.flags.ignore_validate = True
                    doc.flags.ignore_mandatory = True   # sexe_veau1 left blank
                    doc.insert(ignore_permissions=True)
                created += 1
            except Exception as e:
                errors.append({"tn": tn, "date": date, "error": str(e)})

        # update_mother does not set date_premier_velage for already-VACHE cows
        if not dry_run and dates:
            frappe.db.set_value("Animal", tn, "date_premier_velage", dates[0])

    if not dry_run:
        # vivant_veau1=0 was only a switch to SUPPRESS calf creation at insert
        # (create_calves fires on after_insert and only when vivant_veau1 is truthy).
        # That work is now done, so flip it to 1: these were NOT stillbirths, and the
        # reports (count_avortements_mort_nes) read vivant_veau1=0 as "mort-né" — which
        # would wrongly count every imported vêlage as a stillbirth. No calf Animal is
        # created retroactively (after_insert already ran). Also fixes re-runs on data
        # imported by the older version. Bulk + idempotent.
        frappe.db.sql("UPDATE `tabVelage` SET vivant_veau1=1 WHERE vivant_veau1=0")
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Velage import (current herd, re-bake 2026)")
    print(f"  cows processed: {cows_done}")
    print(f"  velages would-create={created}, skipped(existing)={skipped}, errors={len(errors)}")
    if missing_animal:
        print(f"  WARN - animal not found ({len(missing_animal)}): {missing_animal}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']} {e['date']}: {e['error']}")

    return {
        "cows": cows_done,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "missing_animal": missing_animal,
    }
