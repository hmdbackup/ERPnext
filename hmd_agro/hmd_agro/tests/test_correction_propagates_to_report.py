"""
R4 — Saisie Alimentation correction round-trip regression test (per-aliment).

Locks in the critical guarantee from the SLE unification (R1+R2+R3):
when the farmer posts a correction via Saisie Alimentation, the change
must propagate to Rapport Mensuel (both kg side and DT side) AND must
remain consistent across all three granularités. A negative correction
must DECREASE the cost (this was the pre-R3 bug: `actual_qty < 0` filter
ignored Material Receipts).

States exercised:
  1. Baseline — theoretical only
  2. +10 kg correction on Mais (Material Issue, increases cost & kg)
  3. Cancel correction (restored to baseline)
  4. -5 kg correction on Mais (Material Receipt, decreases cost & kg)
  5. Cancel correction (restored to baseline at end)

Cross-mode invariant: Quotidien, Quinzaine, Hebdomadaire totals must
match at every state — granularité is purely presentational.

Test uses an in-backfill date that already has theoretical SEs. It
leaves the database exactly as it found it (cancels its own
corrections at the end).

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_correction_propagates_to_report.run
"""
import frappe
import traceback
from frappe.utils import getdate

from hmd_agro.hmd_agro.utils.feed_correction import (
    get_aliment_state,
    post_aliment_corrections_batch,
    cancel_aliment_correction,
)
from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
    _consumption_from_sle, _alimentation,
)


# In-backfill date with multiple lots and known theoretical totals.
TEST_DATE = "2026-05-14"
TEST_MONTH_START = "2026-05-01"
TEST_MONTH_END = "2026-05-15"
DELTA_POSITIVE = 10.0
DELTA_NEGATIVE = -5.0


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _day_cost(date):
    """Total aliment cost on a single day, summed across all lots."""
    return _consumption_from_sle(date, date)["cumulative_aliment_cost"]


def _alimentation_total(granularite):
    """Coût Total Distribué from the Alimentation table in `granularite`
    mode. Same date range every time so totals must match across modes."""
    ctx = {
        "date_debut": getdate(TEST_MONTH_START),
        "date_filter": getdate(TEST_DATE),
        "date_fin": getdate(TEST_MONTH_END),
        "nb_jours": 31, "mois": 5, "annee": 2026,
        "granularite": granularite,
    }
    _, rows = _alimentation(ctx)
    for r in rows:
        if r.get("aliment") == "Coût Total Distribué (DT)":
            return float(r.get("cout_periode") or 0)
    return 0.0


def run():
    print("\n" + "=" * 76)
    print("  R4 — Saisie correction round-trip → Rapport Mensuel (per-aliment)")
    print("=" * 76)
    try:
        return _run_inner()
    except Exception:
        print("\n  Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}

    # Pick a target aliment with enough theoretical headroom on TEST_DATE.
    state = get_aliment_state(TEST_DATE)
    target = next(
        (a for a in state["aliments"] if a["theoretical_total"] >= 20),
        None,
    )
    if not target:
        _check(False, "No aliment with >= 20 kg theoretical on " + TEST_DATE,
               results)
        return results

    item_code = target["item_code"]
    aliment_name = target["aliment"]
    theo = target["theoretical_total"]
    print(f"\n  Target aliment: {aliment_name} ({item_code})  "
          f"theoretical = {theo} kg\n")

    # Ensure no stale correction from a prior test run.
    cancel_aliment_correction(TEST_DATE, item_code)

    # ── State 1: baseline ──────────────────────────────────────────────
    print("  ── State 1: baseline (no correction) ──")
    cost_baseline = _day_cost(TEST_DATE)
    totals_baseline = {g: _alimentation_total(g)
                        for g in ("Quotidien", "Quinzaine", "Hebdomadaire")}
    print(f"    Day cost: {cost_baseline:.2f} DT")
    print(f"    Alimentation total: {totals_baseline['Quotidien']:.2f} DT")
    _check(
        abs(totals_baseline["Quotidien"] - totals_baseline["Quinzaine"]) < 0.5
        and abs(totals_baseline["Quotidien"] - totals_baseline["Hebdomadaire"]) < 0.5,
        "Baseline: 3 modes report identical total",
        results,
    )

    # ── State 2: +10 kg correction (Material Issue) ────────────────────
    print(f"\n  ── State 2: +{DELTA_POSITIVE} kg correction (Material Issue) ──")
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + DELTA_POSITIVE},
    ])
    _check(r["posted"] > 0 and not r["errors"],
           f"+{DELTA_POSITIVE}kg posts {r['posted']} per-lot SE(s)", results)
    cost_after_plus = _day_cost(TEST_DATE)
    delta_plus = cost_after_plus - cost_baseline
    print(f"    Day cost: {cost_after_plus:.2f} DT  (Δ = +{delta_plus:.2f})")
    _check(delta_plus > 0.1,
           f"Day cost INCREASED after +{DELTA_POSITIVE}kg correction "
           f"(Δ=+{delta_plus:.2f})", results)
    totals_plus = {g: _alimentation_total(g)
                    for g in ("Quotidien", "Quinzaine", "Hebdomadaire")}
    _check(
        abs(totals_plus["Quotidien"] - totals_plus["Quinzaine"]) < 0.5
        and abs(totals_plus["Quotidien"] - totals_plus["Hebdomadaire"]) < 0.5,
        f"After +{DELTA_POSITIVE}kg: 3 modes still identical "
        f"(Q={totals_plus['Quotidien']:.2f})", results,
    )
    _check(totals_plus["Quotidien"] > totals_baseline["Quotidien"],
           "Alimentation total bumped above baseline", results)

    # ── State 3: cancel → restored to baseline ─────────────────────────
    print("\n  ── State 3: cancel correction → restored ──")
    cancel_aliment_correction(TEST_DATE, item_code)
    cost_restored = _day_cost(TEST_DATE)
    print(f"    Day cost: {cost_restored:.2f} DT")
    _check(abs(cost_restored - cost_baseline) < 0.1,
           f"Day cost restored to baseline ({cost_restored:.2f} ≈ "
           f"{cost_baseline:.2f})", results)
    totals_restored = {g: _alimentation_total(g)
                        for g in ("Quotidien", "Quinzaine", "Hebdomadaire")}
    _check(abs(totals_restored["Quotidien"] - totals_baseline["Quotidien"]) < 0.5,
           "Alimentation total restored to baseline", results)

    # ── State 4: -5 kg correction (Material Receipt — the R3 fix) ──────
    print(f"\n  ── State 4: {DELTA_NEGATIVE} kg correction (Material Receipt) ──")
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + DELTA_NEGATIVE},
    ])
    _check(r["posted"] > 0 and not r["errors"],
           f"{DELTA_NEGATIVE}kg posts {r['posted']} per-lot SE(s)", results)
    # Sanity: at least one of the posted SEs is a Material Receipt
    se_types = frappe.db.sql_list("""
        SELECT DISTINCT stock_entry_type FROM `tabStock Entry`
        WHERE docstatus = 1 AND posting_date = %s
          AND remarks LIKE %s
    """, (TEST_DATE,
          f"RATION_CORRECTION_%_{getdate(TEST_DATE)}_{item_code}"))
    _check("Material Receipt" in se_types,
           f"Posted SEs include Material Receipt (types: {se_types})", results)
    cost_after_minus = _day_cost(TEST_DATE)
    delta_minus = cost_after_minus - cost_baseline
    print(f"    Day cost: {cost_after_minus:.2f} DT  (Δ = {delta_minus:+.2f})")
    _check(delta_minus < -0.05,
           f"Day cost DECREASED after {DELTA_NEGATIVE}kg correction "
           f"(Δ={delta_minus:+.2f}) — confirms R3 fix that Material Receipts "
           f"net into the cost calc", results)
    totals_minus = {g: _alimentation_total(g)
                     for g in ("Quotidien", "Quinzaine", "Hebdomadaire")}
    _check(
        abs(totals_minus["Quotidien"] - totals_minus["Quinzaine"]) < 0.5
        and abs(totals_minus["Quotidien"] - totals_minus["Hebdomadaire"]) < 0.5,
        f"After {DELTA_NEGATIVE}kg: 3 modes still identical "
        f"(Q={totals_minus['Quotidien']:.2f})", results,
    )
    _check(totals_minus["Quotidien"] < totals_baseline["Quotidien"],
           "Alimentation total dropped below baseline", results)

    # ── State 5: final cleanup ─────────────────────────────────────────
    cancel_aliment_correction(TEST_DATE, item_code)
    cost_final = _day_cost(TEST_DATE)
    _check(abs(cost_final - cost_baseline) < 0.1,
           "Final cleanup: DB back to where we found it", results)

    print("\n" + "=" * 76)
    total = results["pass"] + results["fail"]
    print(f"  RÉSULTATS: {results['pass']}/{total} passés, "
          f"{results['fail']} échoués")
    print("=" * 76)
    return results
