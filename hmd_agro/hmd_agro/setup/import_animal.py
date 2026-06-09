"""Import the current milking herd into the Animal doctype — reads animals.csv.

Generic: farm data in an external CSV (see data_source.py), not baked here.
CSV columns: identification_tn, date_naissance, pere, mere
  - pere = sire name (uppercase Taureau), may be blank
  - mere = real dam's identification_tn where recovered (e.g. from génisses_IA), else blank

PHASE 1 ONLY: bare Animal records, no events.

MOTHER HANDLING — to keep id_mere non-empty without a chain of fake cows, a single
placeholder founder (PLACEHOLDER_TN, est_achat=1, statut=REFORME, no parent link) is
created first; every cow links to it, then a post-pass overrides id_mere with the REAL
dam (the CSV `mere` column) for the cows that have one (dam must already exist → post-pass).

INSERT FLAGS: ignore_validate + ignore_mandatory + lot_change_source=IMPORT.
Idempotent / dry-run. Run AFTER import_lot + import_taureau.

Run: bench --site <site> execute hmd_agro.hmd_agro.setup.import_animal.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

from hmd_agro.hmd_agro.setup import data_source

PLACEHOLDER_TN = "0009999999"   # founder mother; LOW so it never collides with calf auto-IDs
IMPORT_LOT = "LOT1"


def _placeholder_doc():
    return {
        "doctype": "Animal",
        "identification_tn": PLACEHOLDER_TN,
        "nom": "Mère placeholder (import)",
        "nom_metier": PLACEHOLDER_TN[-4:],
        "race": "Holstein",
        "categorie": "VACHE",
        "sexe": "F",
        "date_naissance": "2010-01-01",
        "est_achat": 1,
        "date_entree": "2010-01-01",
        "prix_achat": 0,
        "statut": "REFORME",
        "date_sortie": "2015-01-01",
        "etat_gestation": "VIDE",
    }


def _insert(doc_dict):
    doc = frappe.get_doc(doc_dict)
    doc.flags.ignore_validate = True
    doc.flags.ignore_mandatory = True
    doc.flags.lot_change_source = "IMPORT"
    doc.insert(ignore_permissions=True)
    return doc


def run(dry_run=True, source=None):
    dry_run = int(dry_run)
    created = skipped = 0
    errors = []
    missing_sire, missing_date, unresolved_pere = [], [], []

    if not frappe.db.exists("Lot", IMPORT_LOT):
        print(f"[ABORT] target lot '{IMPORT_LOT}' does not exist.")
        return {"aborted": True}

    rows = data_source.read(source, "animals.csv")
    dam_links = {r["identification_tn"].strip(): data_source.txt(r.get("mere"))
                 for r in rows if r.get("identification_tn") and data_source.txt(r.get("mere"))}

    # 1. placeholder founder mother (before the cows link to it)
    if frappe.db.exists("Animal", PLACEHOLDER_TN):
        ph_state = "exists"
    else:
        ph_state = "create"
        if not dry_run:
            _insert(_placeholder_doc())

    # 2. the cows
    for r in rows:
        tn = (r.get("identification_tn") or "").strip()
        if not tn:
            continue
        naissance = data_source.txt(r.get("date_naissance"))
        pere = data_source.txt(r.get("pere"))
        try:
            if frappe.db.exists("Animal", tn):
                skipped += 1
                continue
            if not pere:
                missing_sire.append(tn)
            elif not frappe.db.exists("Taureau", pere):
                unresolved_pere.append((tn, pere))
            if not naissance:
                missing_date.append(tn)

            doc_dict = {
                "doctype": "Animal",
                "identification_tn": tn,
                "nom_metier": tn[-4:],
                "race": "Holstein",
                "categorie": "VACHE",
                "sexe": "F",
                "date_naissance": naissance,
                "est_achat": 0,
                "id_mere": PLACEHOLDER_TN,
                "id_pere": pere,
                "id_lot": IMPORT_LOT,
                "statut": "ACTIF",
                "etat_gestation": "VIDE",
            }
            if not dry_run:
                _insert(doc_dict)
            created += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    # 3. real dams (replace placeholder for the cows that have one)
    dam_applied = 0
    if not dry_run:
        for daughter, dam in dam_links.items():
            if frappe.db.exists("Animal", daughter) and frappe.db.exists("Animal", dam):
                frappe.db.set_value("Animal", daughter, "id_mere", dam)
                dam_applied += 1

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Animal import (CSV) — current herd into lot '{IMPORT_LOT}'")
    print(f"  placeholder mother {PLACEHOLDER_TN}: {ph_state}")
    print(f"  real dams applied: {dam_applied}/{len(dam_links)}")
    print(f"  cows would-create={created}, skipped(existing)={skipped}, errors={len(errors)}")
    print(f"  gap - no sire ({len(missing_sire)}): {missing_sire}")
    print(f"  gap - no birth date ({len(missing_date)}): {missing_date}")
    if unresolved_pere:
        print(f"  WARN - sire not found as Taureau ({len(unresolved_pere)}): {unresolved_pere}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']}: {e['error']}")

    return {
        "placeholder": ph_state, "dams_applied": dam_applied, "created": created,
        "skipped": skipped, "errors": errors, "missing_sire": missing_sire,
        "missing_date": missing_date, "unresolved_pere": unresolved_pere,
    }
