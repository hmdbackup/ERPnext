"""Import current-cycle inseminations from the 2026 re-bake — Phase 2b-i.

Data: `repro_2026_data.IA_DATA` — AUTO-GENERATED from ETABLE HMD 2026.xlsx
(Repro2026 IA1-9 date/bull columns + Etat). Each cow carries her current-cycle IAs
as explicit (date, bull, resultat) triples, so every case is unambiguous:

  RESULTAT RULE (encoded at generation, from the farm's Etat column):
    - GESTANTE cow (Etat pleine/ok/a suiv): the fecundating IA (Repro2026 "IA D")
      -> REUSSIE; all her other IAs -> ECHOUEE.
    - open cow (blank Etat): her LAST IA -> EN_ATTENTE (bred, not yet confirmed);
      earlier -> ECHOUEE.
    - VIDE cow: all -> ECHOUEE.

Inserting the REUSSIE IA fires update_animal_on_resultat -> sets the cow GESTANTE +
date_velage_prevue (= date_ia + 280) + date_tarissement. EN_ATTENTE/ECHOUEE do not
set gestation (a later ECHOUEE only resets if it is itself the fecondante IA, which
it is not). Inserted chronologically.

The 11 ex-genisses' FIRST-cycle IAs are a SEPARATE step (import_insemination_genisses,
re-run after this — that data is not in Repro2026).

FLAGS: skip_semence_decrement (no stock movements — historical) + ignore_validate
+ ignore_mandatory. Idempotent on (animal, date_ia). Bull typos normalised at
generation (TOBLERONRE->TOBLERONE, OXYBUL->OXIBUL, PARAGAUAY->PARAGUAY, "X S"->X).

Run order: AFTER import_velage (needs the EN_COURS lactation) and import_taureau.
Run (dev):
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_insemination.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe

from hmd_agro.hmd_agro.setup.repro_2026_data import IA_DATA


def run(dry_run=True):
    dry_run = int(dry_run)
    created = skipped = reussie = en_attente = echouee = 0
    errors = []
    missing_animal, missing_taureau, no_lactation = [], [], []

    for tn, ias in IA_DATA:
        if not frappe.db.exists("Animal", tn):
            missing_animal.append(tn)
            continue
        lactation = frappe.db.get_value("Lactation",
            {"animal": tn, "statut": "EN_COURS"}, "name")
        if not lactation:
            no_lactation.append(tn)

        for i, (date, bull, resultat) in enumerate(ias):  # chronological
            try:
                if bull and not frappe.db.exists("Taureau", bull):
                    missing_taureau.append((tn, bull))
                    bull = None  # don't fail the insert; record the gap
                if frappe.db.exists("Insemination", {"animal": tn, "date_ia": date}):
                    skipped += 1
                    continue
                if not dry_run:
                    doc = frappe.get_doc({
                        "doctype": "Insemination",
                        "animal": tn,
                        "date_ia": date,
                        "taureau": bull,
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
                reussie += resultat == "REUSSIE"
                en_attente += resultat == "EN_ATTENTE"
                echouee += resultat == "ECHOUEE"
            except Exception as e:
                errors.append({"tn": tn, "date": date, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode}] Insemination import — 2026 re-bake (all 99 cows)")
    print(f"  IA records would-create={created} "
          f"(REUSSIE={reussie}, EN_ATTENTE={en_attente}, ECHOUEE={echouee}), "
          f"skipped(existing)={skipped}, errors={len(errors)}")
    if missing_animal:
        print(f"  WARN animal not found ({len(missing_animal)}): {missing_animal}")
    if missing_taureau:
        print(f"  WARN taureau not found ({len(missing_taureau)}): {missing_taureau}")
    if no_lactation:
        print(f"  WARN no EN_COURS lactation ({len(no_lactation)}): {no_lactation}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']} {e['date']}: {e['error']}")

    return {
        "created": created, "reussie": reussie, "en_attente": en_attente,
        "echouee": echouee, "skipped": skipped, "errors": errors,
        "missing_animal": missing_animal, "missing_taureau": missing_taureau,
        "no_lactation": no_lactation,
    }
