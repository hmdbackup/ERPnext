"""Import the FIRST-cycle (heifer) inseminations for the 11 ex-génisses — Phase 2b-ii.

These 11 cows are already in the herd (animal + velages + lactations + current-cycle
IAs all imported). The ONLY thing missing is their *first* insemination cycle — the
breeding that produced their FIRST calving, recorded back when they were heifers in the
`génisses_IA` sheet (NOT in REPRO2025, which only keeps the current cycle).

Data BAKED IN (extracted offline from génisses_IA cols 31-36 IA dates, col 37 Iad,
col 40 Taureau Utilisé; joined to the 99 herd on code+N°). 11 cows, 22 IA records.

KEY DIFFERENCE vs import_insemination.py — these are CLOSED past pregnancies (each
already produced a calving that's in the system). So they must NOT fire the gestation
cascade (which would wrongly flag the cow pregnant *now* from a 2023/24 IA). Therefore:
  insert with resultat=EN_ATTENTE, then db.set_value the final result → bypasses
  Insemination.on_update (update_animal_on_resultat) → current gestation state untouched.

RESULT LOGIC (biology checksum, NOT the sheet's "Iad" label):
  fecundating IA = the one ~250-295 days before the cow's REAL first velage (REPRO2025
  V1). That one → REUSSIE; the rest → ECHOUEE. For 2300273415 NO IA lands in that
  window (its real fecundating IA is missing from the sheet) → ALL ECHOUEE, flagged.

OTHER FIELDS: lactation=None (heifer IAs precede the first lactation); numero_ia =
position in the first cycle; type_semence=CONVENTIONNELLE; sires already exist (MARLEY/
OMALET/POTEMKINE). Flags: ignore_validate + ignore_mandatory + skip_semence_decrement.

VELAGE LINK: the fecundating first-cycle IA is linked to the cow's first velage
(Velage.insemination) — only if that link is empty — closing the causal chain.

Idempotent on (animal, date_ia). Run AFTER import_velage + import_insemination.

Run (dev):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_insemination_genisses.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

# (animal identification_tn, taureau, fecundating date | None, [first-cycle IA dates ascending])
GEN_IA = [
    ("2300259203", "MARLEY", "2023-12-14", ["2023-06-12", "2023-07-06", "2023-08-14", "2023-09-05", "2023-10-15", "2023-12-14"]),
    ("2300261986", "OMALET", "2024-10-27", ["2024-06-11", "2024-09-16", "2024-10-27"]),
    ("2300273385", "POTEMKINE", "2025-02-13", ["2025-02-13"]),
    ("2300273393", "OMALET", "2025-02-03", ["2025-02-03"]),
    ("2300273394", "OMALET", "2024-10-09", ["2024-10-09"]),
    ("2300273397", "OMALET", "2024-10-30", ["2024-10-30"]),
    ("2300273405", "OMALET", "2025-01-07", ["2024-10-20", "2024-11-23", "2024-12-16", "2025-01-07"]),
    ("2300273406", "OMALET", "2024-12-10", ["2024-12-10"]),
    ("2300273410", "OMALET", "2024-11-29", ["2024-11-29"]),
    ("2300273411", "OMALET", "2024-11-03", ["2024-11-03"]),
    ("2300273415", "OMALET", None, ["2024-11-12", "2025-01-30"]),  # no fecundating match → all ECHOUEE
]


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = reussie = velage_linked = 0
    errors = []
    no_fecundating = []

    for tn, taureau, fec, dates in GEN_IA:
        if not frappe.db.exists("Animal", tn):
            errors.append({"tn": tn, "error": "animal not found"})
            continue
        if taureau and not frappe.db.exists("Taureau", taureau):
            errors.append({"tn": tn, "error": f"taureau {taureau} not found"})
            continue
        if not fec:
            no_fecundating.append(tn)

        fecundating_ia_name = None
        for i, date in enumerate(dates):
            resultat = "REUSSIE" if (fec and date == fec) else "ECHOUEE"
            try:
                existing = frappe.db.exists("Insemination", {"animal": tn, "date_ia": date})
                if existing:
                    skipped += 1
                    if resultat == "REUSSIE":
                        fecundating_ia_name = existing
                    continue
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Insemination",
                        "animal": tn,
                        "date_ia": date,
                        "taureau": taureau,
                        "type_semence": "CONVENTIONNELLE",
                        "resultat": "EN_ATTENTE",   # pending first, then set final via db (no cascade)
                        "numero_ia": i + 1,
                        "lactation": None,          # heifer IA: precedes the first lactation
                    })
                    doc.flags.ignore_validate = True
                    doc.flags.ignore_mandatory = True
                    doc.flags.skip_semence_decrement = True
                    doc.insert(ignore_permissions=True)
                    # bypass on_update → does NOT touch the cow's current gestation
                    frappe.db.set_value("Insemination", doc.name, "resultat", resultat)
                    if resultat == "REUSSIE":
                        fecundating_ia_name = doc.name
                created += 1
                if resultat == "REUSSIE":
                    reussie += 1
            except Exception as e:
                errors.append({"tn": tn, "date": date, "error": str(e)})

        # link the fecundating first-cycle IA to the already-imported FIRST velage
        if not dry_run and fecundating_ia_name:
            first_velage = frappe.db.get_value("Velage", {"animal": tn}, "name",
                                               order_by="date_velage asc")
            if first_velage and not frappe.db.get_value("Velage", first_velage, "insemination"):
                frappe.db.set_value("Velage", first_velage, "insemination", fecundating_ia_name)
                velage_linked += 1

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Insemination import — first cycle (ex-génisses)")
    print(f"  IA records would-create={created} (REUSSIE={reussie}), skipped(existing)={skipped}, errors={len(errors)}")
    print(f"  fecundating IA linked to first velage: {velage_linked}")
    print(f"  cows with NO fecundating match (all ECHOUEE, gap): {no_fecundating}")
    for e in errors[:5]:
        print(f"  ERR {e.get('tn')} {e.get('date','')}: {e['error']}")

    return {"created": created, "reussie": reussie, "skipped": skipped,
            "velage_linked": velage_linked, "no_fecundating": no_fecundating, "errors": errors}
