"""Enrich the closed historical lactations with correct LENGTH — Phase 2c.

Lactations are CREATED by the velage cascade (Velage.after_insert), not here.
This step only corrects, on each cow's CLOSED (TARIE) lactation, the
`date_tarissement` (real dry-off) and `jours_lactation` (days-in-milk), which the
velage auto-close can only estimate.

Per closed lactation #i (numero_lactation), for each of the 99 import cows
(reused from import_animal.HERD):
  - If the sheet recorded L_i days (REPRO2025 cols 18/20/22/24, baked below):
        date_tarissement = date_debut + L_i days     (the real recorded length)
        jours_lactation  = L_i days
    Guard: if that would land on/after the NEXT calving (data error,
    lactation longer than the calving interval) -> use the fallback instead.
  - Else (no L-data for that lactation):
        date_tarissement = next_lactation.date_debut - tarissement_window (60)
        jours_lactation  = that - date_debut
    (Same biological fallback as Velage.create_lactation.)

The CURRENT EN_COURS lactation is skipped (no closure yet — Traite fills it).
production_totale is NOT touched here (filled by the Traite import later).

Written via db.set_value (no cascade; lactations are already TARIE). Idempotent.
Run order: AFTER import_velage. Self-contained / baked — no Excel on the server.

Run (dev):
    bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.import_lactation.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe
from frappe.utils import getdate, add_days, date_diff

from hmd_agro.hmd_agro.setup.import_animal import HERD
from hmd_agro.hmd_agro.utils.config import get_config

ANIMALS = [tn for tn, _, _ in HERD]

# identification_tn -> [L1_days, L2_days, ...] (per closed lactation; null = gap -> fallback)
L_DAYS = {
    "2300254525": [380, 429, 529],
    "2300254578": [394, 305, 341],
    "2300254598": [334, 319, 279],
    "2300254583": [460, 319, 540],
    "2300254592": [263, 319, 343],
    "2300254597": [322, 463, 496],
    "2300254586": [244, 573, 375],
    "2300254591": [284, 271, 355, 303],
    "2300254560": [483, 289, 397],
    "2300254540": [326, 493, 343],
    "2300254550": [312, 362, 465],
    "2300254568": [255, 512, 386],
    "2300254544": [255, 369, 459],
    "2300254541": [358, 403, 439],
    "2300254605": [401, 571, 286],
    "2300254577": [287, 289, 453],
    "2300254572": [301, 344, 446],
    "2300254587": [346, 432, 326],
    "2300254575": [308, 338, 317],
    "2300254549": [524, 445],
    "2300254556": [283, 432, 292, 291],
    "2300254519": [313, 318, 309],
    "2300254607": [319, 337, 284],
    "2300254585": [279, 319, 357],
    "2300254520": [536, 333, 338],
    "2300254551": [318, 305, 301],
    "2300254576": [336, 394, 307],
    "2300254603": [303, 230, 280, 302],
    "2300254559": [303, 334, 260],
    "2300254529": [252, 289, 261],
    "2300254573": [289, 305, 296, 382],
    "2300254574": [467, 310, 304],
    "2300254581": [495, 430],
    "2300254609": [376, None, 442],
    "2300254582": [304, 545],
    "2300254610": [633, 384],
    "2300254604": [345, 433],
    "2300254569": [441, 355, 425],
    "2300254566": [270, 432, 516],
    "2300254546": [355, 346, 361],
    "2300254579": [373, 371, 353],
    "2300254528": [256, 591, 312],
    "2300254518": [538, 637],
    "2300254532": [284, 449],
    "2300254565": [389, 389],
    "2300254561": [277, 273, 307],
    "2300254543": [272, 428],
    "2300254527": [273, 270, 316],
    "2300254534": [421, 361],
    "2300254562": [419, 266],
    "2300254589": [531, 294],
    "2300254554": [505],
    "2300254600": [432, 349],
    "2300254595": [285, 274, 285],
    "2300254570": [441, 405],
    "2300254538": [359, 450],
    "2300254590": [290, 305, 308],
    "2300254539": [424, 359],
    "2300254553": [316, 271],
    "2300254599": [237, 301, 297],
    "2300254557": [294, 304, 317],
    "2300254555": [265, 458],
    "2300254516": [285, 307],
    "2300254602": [487, 323],
    "2300254548": [567, 399],
    "2300254558": [302, 614],
    "2300254547": [442, 315],
    "2300254584": [458, 357],
    "2300254608": [289, 300, 297],
    "2300254521": [464, 364],
    "2300254612": [281],
    "2300259224": [324],
}


def run(dry_run=True):
    dry_run = int(dry_run)
    window = int(get_config("tarissement_window_jours", default=60))
    real = fallback = skipped_current = 0
    errors = []

    for tn in ANIMALS:
        try:
            lacs = frappe.get_all("Lactation", filters={"animal": tn},
                fields=["name", "numero_lactation", "date_debut", "statut"],
                order_by="numero_lactation asc")
            debut_by_no = {l.numero_lactation: l.date_debut for l in lacs}
            ldays = L_DAYS.get(tn, [])

            for l in lacs:
                if l.statut != "TARIE":      # only closed lactations; skip EN_COURS/INTERROMPUE
                    skipped_current += 1
                    continue
                i = l.numero_lactation
                next_debut = debut_by_no.get(i + 1)
                rec = ldays[i - 1] if (i - 1) < len(ldays) else None

                dry_off = None
                mode = None
                if rec is not None:
                    cand = add_days(getdate(l.date_debut), int(rec))
                    # guard: a real recorded length must not run into the next calving
                    if next_debut and getdate(cand) >= getdate(next_debut):
                        rec = None  # fall through to fallback
                    else:
                        dry_off, mode = cand, "real"
                if rec is None:
                    if not next_debut:
                        continue  # closed but no following lactation — shouldn't happen
                    cand = add_days(getdate(next_debut), -window)
                    if getdate(cand) < getdate(l.date_debut):
                        cand = getdate(next_debut)
                    dry_off, mode = cand, "fallback"

                jours = date_diff(getdate(dry_off), getdate(l.date_debut))
                if not dry_run:
                    frappe.db.set_value("Lactation", l.name, {
                        "date_tarissement": str(dry_off),
                        "jours_lactation": jours,
                    })
                if mode == "real":
                    real += 1
                else:
                    fallback += 1
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode_lbl = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode_lbl}] Lactation length enrichment (closed lactations)")
    print(f"  set from sheet L-days (real)={real}, fallback (velage-{window})={fallback}, "
          f"skipped(current/non-TARIE)={skipped_current}, errors={len(errors)}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']}: {e['error']}")
    return {"real": real, "fallback": fallback, "skipped_current": skipped_current, "errors": errors}
