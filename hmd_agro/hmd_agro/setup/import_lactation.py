"""Enrich lactations with real PRODUCTION + LENGTH — Phase 2c.

Lactations are CREATED by the velage cascade (Velage.after_insert), not here. This
step fills, per lactation, from `repro_2026_data.LACT_TOTALS` (Repro2026 "Lactation
réalisée" L1-L4: total + durée, chronological):

  PRODUCTION (`production_totale`): set whenever the sheet has a total — for ANY
    lactation (closed OR a dried-off current one). If the sheet has no total: left
    untouched (the Traite import fills the current milking lactation later).

  LENGTH (`date_tarissement` + `jours_lactation`), set INDEPENDENTLY of production:
    - sheet has a duration  -> date_tarissement = date_debut + durée (REAL)
      (guard: if it runs into the next calving, use the biological fallback instead)
    - no duration but a NEXT lactation exists (historically closed) -> fallback
      = next_lactation.date_debut - tarissement_window (60)
    - no duration and NO next lactation (the current/last lactation): length left
      alone here — set by import_taries (dried-off) or left open (still milking).

So a dried-off cow whose sheet records her last lactation's total+duration gets BOTH
the real yield and the real dry-off date; import_taries then only fills a dry-off
date where the sheet didn't give one.

Written via db.set_value (no cascade). Idempotent. Run AFTER import_velage.

Run (dev):
    bench --site <site> execute hmd_agro.hmd_agro.setup.import_lactation.run --kwargs '{"dry_run": 1}'
Set dry_run=0 to commit.
"""
import frappe
from frappe.utils import getdate, add_days, date_diff

from hmd_agro.hmd_agro.setup.import_animal import HERD
from hmd_agro.hmd_agro.setup.repro_2026_data import LACT_TOTALS
from hmd_agro.hmd_agro.utils.config import get_config

ANIMALS = [tn for tn, _, _ in HERD]
TOTALS = dict(LACT_TOTALS)   # tn -> [(total, duree), ...] chronological L1..Ln


def run(dry_run=True):
    dry_run = int(dry_run)
    window = int(get_config("tarissement_window_jours", default=60))
    real = fallback = prod_set = no_length = 0
    errors = []

    for tn in ANIMALS:
        try:
            lacs = frappe.get_all("Lactation", filters={"animal": tn},
                fields=["name", "numero_lactation", "date_debut", "statut"],
                order_by="numero_lactation asc")
            debut_by_no = {l.numero_lactation: l.date_debut for l in lacs}
            recs = TOTALS.get(tn, [])

            for l in lacs:
                i = l.numero_lactation
                next_debut = debut_by_no.get(i + 1)
                rec = recs[i - 1] if (i - 1) < len(recs) else None
                total = rec[0] if (rec and rec[0]) else None
                duree = rec[1] if (rec and rec[1]) else None

                payload = {}
                # PRODUCTION — whenever the sheet has a total, any lactation
                if total is not None:
                    payload["production_totale"] = total
                    prod_set += 1

                # LENGTH — independent of production
                dry_off = mode = None
                if duree:
                    cand = add_days(getdate(l.date_debut), int(duree))
                    if next_debut and getdate(cand) >= getdate(next_debut):
                        cand = add_days(getdate(next_debut), -window)   # runs into next calving
                        if getdate(cand) < getdate(l.date_debut):
                            cand = getdate(next_debut)
                        mode = "fallback"
                    else:
                        mode = "real"
                    dry_off = cand
                elif next_debut:
                    cand = add_days(getdate(next_debut), -window)        # closed, no recorded length
                    if getdate(cand) < getdate(l.date_debut):
                        cand = getdate(next_debut)
                    dry_off, mode = cand, "fallback"
                # else: current/last lactation w/o recorded length -> leave to taries / open

                if dry_off:
                    payload["date_tarissement"] = str(dry_off)
                    payload["jours_lactation"] = date_diff(getdate(dry_off), getdate(l.date_debut))
                    real += mode == "real"
                    fallback += mode == "fallback"
                else:
                    no_length += 1

                if payload and not dry_run:
                    frappe.db.set_value("Lactation", l.name, payload)
        except Exception as e:
            errors.append({"tn": tn, "error": str(e)})

    if not dry_run:
        frappe.db.commit()

    mode_lbl = "DRY-RUN" if dry_run else "COMMITTED"
    print(f"\n[{mode_lbl}] Lactation enrichment (production + length, 2026 re-bake)")
    print(f"  production_totale set={prod_set} | length: real={real}, fallback (velage-{window})={fallback}, "
          f"left-for-taries/open={no_length} | errors={len(errors)}")
    for e in errors[:5]:
        print(f"  ERR {e['tn']}: {e['error']}")
    return {"prod_set": prod_set, "real": real, "fallback": fallback,
            "no_length": no_length, "errors": errors}
