"""Import current-cycle inseminations for the pregnant cows — Phase 2b-i.

Data BAKED IN (extracted offline from Etable HMD 2025 (1).xls > REPRO2025:
IA1-8 dates cols 51-58, Iad col 59, Taureau Utilisé col 64; joined to the 99
current cows on the 4-digit Tunisien N°). 80 currently-pregnant cows, 191 IA
records.

SCOPE: only the CURRENT reproductive cycle (the IAs since each cow's last velage
that led to her current pregnancy). The 11 ex-génisses' FIRST-cycle IAs live in
génisses_IA and are a SEPARATE step (2b-ii). Middle-cycle IAs (V2/V3/V4
conceptions) are not in any sheet — permanent gap.

RESULT LOGIC: REUSSIE = the IA on the Iad date (col 59 = the authoritative
fecundating date — NOT necessarily the last attempt; 1 cow, 2300254604, has a
later failed IA after the fecundating one). All other dates = ECHOUEE. Inserting
the REUSSIE one fires update_animal_on_resultat -> sets the cow GESTANTE +
date_velage_prevue (= date_ia + 280, matches Excel Vn+1) + date_tarissement. This
establishes correct CURRENT gestation state. A later ECHOUEE does not undo it
(its branch only resets if it is itself the fecondante IA).

SIRE: col 64 (fecundating bull) applied to all of a cow's IAs (failed-attempt
sires not recorded — approximation). Typo pairs mapped at extraction:
OXYBUL->OXIBUL, OBERNEY->OBERNAY. type_semence=CONVENTIONNELLE (no source data).

FLAGS: skip_semence_decrement (NO stock movements — historical) + ignore_validate
(skip chronology/eligibility checks; numero_ia + lactation set manually) +
ignore_mandatory. Inserts in chronological order; idempotent on (animal, date_ia).

STALENESS: snapshot ~Feb 2026. ~10 of these pregnancies are now past due (the cow
likely already calved) -> on a live system the scheduler would raise overdue
VELAGE/TARISSEMENT alerts. Harmless on dev; at go-live re-bake from a fresh export.

Run (dev):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_insemination.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

# (animal identification_tn, taureau, iad date [=REUSSIE], [all IA dates ascending])
IA_DATA = [
    ("2300254525", "PANACLOC", "2025-05-19", ["2024-09-20", "2024-10-09", "2024-11-04", "2024-12-10", "2025-02-11", "2025-04-30", "2025-05-19"]),
    ("2300254578", "OXIBUL", "2025-10-08", ["2025-10-08"]),
    ("2300254598", "OGOOD", "2025-11-26", ["2025-06-23", "2025-10-15", "2025-11-26"]),
    ("2300254583", "PANACLOC", "2025-05-31", ["2024-11-30", "2025-01-31", "2025-05-31"]),
    ("2300254592", "OBERNAY", "2025-12-16", ["2025-06-14", "2025-12-16"]),
    ("2300254597", "REDBOY", "2025-05-05", ["2025-02-24", "2025-04-15", "2025-05-05"]),
    ("2300254540", "RIMAC", "2025-12-04", ["2025-11-14", "2025-12-04"]),
    ("2300254550", "PARAGUAY", "2025-12-04", ["2025-10-23", "2025-12-04"]),
    ("2300254568", "OXIBUL", "2025-12-15", ["2025-12-15"]),
    ("2300254544", "PARAGUAY", "2025-10-08", ["2025-10-08"]),
    ("2300254541", "TOBLERONE", "2026-01-10", ["2026-01-10"]),
    ("2300254577", "OXIBUL", "2025-10-29", ["2025-10-29"]),
    ("2300254587", "PARAGUAY", "2025-11-09", ["2025-09-24", "2025-10-11", "2025-11-09"]),
    ("2300254575", "OXIBUL", "2025-12-27", ["2025-05-27", "2025-12-27"]),
    ("2300254549", "PANACLOC", "2025-09-07", ["2025-09-07"]),
    ("2300254556", "OUIOUI", "2025-06-15", ["2025-03-12", "2025-03-30", "2025-04-20", "2025-05-08", "2025-06-15"]),
    ("2300254519", "OXIBUL", "2025-10-15", ["2025-05-12", "2025-08-04", "2025-09-16", "2025-10-15"]),
    ("2300254607", "PANACLOC", "2025-09-05", ["2025-06-27", "2025-09-05"]),
    ("2300254585", "OBERNAY", "2025-12-15", ["2025-09-22", "2025-12-15"]),
    ("2300254551", "OXIBUL", "2025-12-11", ["2025-04-20", "2025-07-28", "2025-09-16", "2025-11-16", "2025-12-11"]),
    ("2300254576", "PARAGUAY", "2026-01-06", ["2025-08-20", "2025-10-16", "2025-11-11", "2026-01-06"]),
    ("2300254603", "PARAGUAY", "2026-01-05", ["2026-01-05"]),
    ("2300254559", "OXIBUL", "2025-10-15", ["2025-10-15"]),
    ("2300254529", "PARAGUAY", "2025-11-19", ["2025-03-13", "2025-04-04", "2025-05-19", "2025-11-02", "2025-11-19"]),
    ("2300254573", "PANACLOC", "2025-06-08", ["2025-03-16", "2025-04-06", "2025-05-18", "2025-06-08"]),
    ("2300254574", "PARAGUAY", "2025-12-27", ["2025-09-21", "2025-11-05", "2025-12-27"]),
    ("2300254581", "RIMAC", "2026-01-27", ["2025-03-10", "2025-04-26", "2025-08-04", "2025-10-08", "2025-11-24", "2026-01-27"]),
    ("2300254609", "TOBLERONE", "2026-02-05", ["2026-01-15", "2026-02-05"]),
    ("2300254582", "OXIBUL", "2025-12-27", ["2024-12-29", "2025-02-04", "2025-02-27", "2025-04-15", "2025-07-28", "2025-10-06", "2025-12-27"]),
    ("2300254610", "PARAGUAY", "2025-11-07", ["2025-08-18", "2025-09-08", "2025-11-07"]),
    ("2300254604", "TOBLERONE", "2026-01-04", ["2025-12-22", "2026-01-04", "2026-01-14"]),
    ("2300254566", "OUIOUI", "2025-05-22", ["2025-04-09", "2025-05-22"]),
    ("2300254546", "RIMAC", "2025-09-26", ["2025-09-07", "2025-09-26"]),
    ("2300254579", "OGOOD", "2025-11-05", ["2025-11-05"]),
    ("2300254518", "OBERNAY", "2025-12-30", ["2025-12-10", "2025-12-30"]),
    ("2300254532", "OGOOD", "2026-01-26", ["2026-01-26"]),
    ("2300254565", "OGOOD", "2025-11-03", ["2025-11-03"]),
    ("2300254543", "PANACLOC", "2025-09-18", ["2025-09-18"]),
    ("2300254562", "PARAGUAY", "2025-11-28", ["2025-11-28"]),
    ("2300254589", "OXIBUL", "2025-10-15", ["2025-02-06", "2025-10-15"]),
    ("2300254600", "OXIBUL", "2026-01-18", ["2026-01-18"]),
    ("2300254595", "STEVENSON", "2025-07-27", ["2025-03-13", "2025-07-27"]),
    ("2300254570", "OBERNAY", "2025-12-16", ["2025-02-06", "2025-03-19", "2025-10-15", "2025-12-16"]),
    ("2300254538", "PARAGUAY", "2025-12-27", ["2025-12-27"]),
    ("2300254590", "OXIBUL", "2025-10-30", ["2025-05-12", "2025-10-30"]),
    ("2300254539", "TOBLERONE", "2026-01-29", ["2025-12-26", "2026-01-29"]),
    ("2300254553", "OXIBUL", "2025-10-15", ["2025-07-14", "2025-08-23", "2025-10-15"]),
    ("2300254599", "OBERNAY", "2025-12-10", ["2025-02-06", "2025-03-19", "2025-09-14", "2025-10-11", "2025-10-29", "2025-11-05", "2025-11-16", "2025-12-10"]),
    ("2300254557", "OXIBUL", "2025-07-17", ["2025-05-27", "2025-06-07", "2025-07-17"]),
    ("2300254555", "PARAGUAY", "2025-10-15", ["2025-10-15"]),
    ("2300254516", "PARAGUAY", "2026-01-26", ["2026-01-26"]),
    ("2300254602", "PARAGUAY", "2025-12-27", ["2025-12-27"]),
    ("2300254548", "STEVENSON", "2025-10-18", ["2025-08-26", "2025-10-18"]),
    ("2300254547", "PARAGUAY", "2025-11-15", ["2025-09-04", "2025-10-16", "2025-11-15"]),
    ("2300254608", "STEVENSON", "2025-08-23", ["2025-07-30", "2025-08-23"]),
    ("2300254612", "OXIBUL", "2025-12-19", ["2025-12-19"]),
    ("2300259224", "PANACLOC", "2025-05-18", ["2025-04-24", "2025-05-18"]),
    ("2300254613", "OXIBUL", "2025-10-15", ["2025-10-15"]),
    ("2300261968", "PANACLOC", "2025-09-06", ["2025-08-14", "2025-09-06"]),
    ("2300261976", "OXIBUL", "2025-12-10", ["2025-08-28", "2025-10-06", "2025-11-17", "2025-12-10"]),
    ("2300261957", "OXIBUL", "2025-10-12", ["2025-09-21", "2025-10-12"]),
    ("2300259222", "OXIBUL", "2025-10-07", ["2025-09-18", "2025-10-07"]),
    ("2300261984", "OGOOD", "2026-01-08", ["2025-10-15", "2025-12-18", "2026-01-08"]),
    ("2300259229", "OXIBUL", "2025-10-18", ["2025-10-18"]),
    ("2300261979", "PANACLOC", "2025-09-03", ["2025-08-14", "2025-09-03"]),
    ("2300261964", "OXIBUL", "2025-11-18", ["2025-08-23", "2025-10-06", "2025-11-18"]),
    ("2300261953", "OXIBUL", "2025-10-29", ["2025-10-29"]),
    ("2300261974", "OXIBUL", "2025-12-08", ["2025-12-08"]),
    ("2300261975", "OXIBUL", "2025-10-12", ["2025-09-21", "2025-10-12"]),
    ("2300261983", "OXIBUL", "2026-02-02", ["2026-01-16", "2026-02-02"]),
    ("2300259203", "OXIBUL", "2025-12-27", ["2025-04-05", "2025-06-10", "2025-06-30", "2025-08-09", "2025-09-03", "2025-09-11", "2025-10-25", "2025-11-16", "2025-12-27"]),
    ("2300261971", "OBERNAY", "2026-01-19", ["2025-12-30", "2026-01-19"]),
    ("2300273394", "TOBLERONE", "2026-02-02", ["2025-11-11", "2025-12-10", "2026-02-02"]),
    ("2300273397", "OBERNAY", "2025-12-27", ["2025-09-21", "2025-12-27"]),
    ("2300273411", "OBERNAY", "2025-12-15", ["2025-12-15"]),
    ("2300261999", "OXIBUL", "2025-11-10", ["2025-11-10"]),
    ("2300273410", "PARAGUAY", "2025-12-29", ["2025-11-08", "2025-12-29"]),
    ("2300273406", "PARAGUAY", "2025-11-10", ["2025-11-10"]),
    ("2300273405", "PARAGUAY", "2025-12-09", ["2025-12-09"]),
    ("2300273385", "OGOOD", "2026-01-22", ["2026-01-22"]),
]


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = reussie = 0
    errors = []
    missing_animal, missing_taureau, no_lactation = [], [], []

    for tn, taureau, iad, dates in IA_DATA:
        if not frappe.db.exists("Animal", tn):
            missing_animal.append(tn)
            continue
        if taureau and not frappe.db.exists("Taureau", taureau):
            missing_taureau.append((tn, taureau))
            continue
        # IAs belong to the cow's current (EN_COURS) lactation
        lactation = frappe.db.get_value("Lactation",
            {"animal": tn, "statut": "EN_COURS"}, "name")
        if not lactation:
            no_lactation.append(tn)

        for i, date in enumerate(dates):  # chronological
            try:
                if frappe.db.exists("Insemination", {"animal": tn, "date_ia": date}):
                    skipped += 1
                    continue
                resultat = "REUSSIE" if date == iad else "ECHOUEE"
                if resultat == "REUSSIE":
                    reussie += 1
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Insemination",
                        "animal": tn,
                        "date_ia": date,
                        "taureau": taureau,
                        "type_semence": "CONVENTIONNELLE",
                        "resultat": resultat,
                        "numero_ia": i + 1,
                        "lactation": lactation,
                    })
                    doc.flags.ignore_validate = True
                    doc.flags.ignore_mandatory = True
                    doc.flags.skip_semence_decrement = True   # historical: no stock
                    doc.insert(ignore_permissions=True)
                created += 1
            except Exception as e:
                errors.append({"tn": tn, "date": date, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Insemination import — current cycle (pregnant cows)")
    print(f"  IA records would-create={created} (REUSSIE={reussie}), skipped(existing)={skipped}, errors={len(errors)}")
    if missing_animal:
        print(f"  WARN animal not found ({len(missing_animal)}): {missing_animal}")
    if missing_taureau:
        print(f"  WARN taureau not found ({len(missing_taureau)}): {missing_taureau}")
    if no_lactation:
        print(f"  WARN no EN_COURS lactation ({len(no_lactation)}): {no_lactation}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']} {e['date']}: {e['error']}")

    return {
        "created": created,
        "reussie": reussie,
        "skipped": skipped,
        "errors": errors,
        "missing_animal": missing_animal,
        "missing_taureau": missing_taureau,
        "no_lactation": no_lactation,
    }
