"""
Per-aliment Saisie Alimentation backend test.

Covers the same properties the legacy per-lot test_feed_correction did, but
at the per-aliment level (which is what the UI actually exercises):
  - State structure (get_aliment_state)
  - Positive correction (Material Issue) — qty/type/bin
  - Negative correction (Material Receipt) — basic_rate pinned to theoretical SE
    rate (GL-neutral round trip)
  - Idempotent re-save (cancel + repost is net-zero on bin)
  - no_change (actual == theoretical → no SE posted)
  - Cancel (cancel_aliment_correction returns count, restores bin)
  - Error paths (unknown item, negative actual, missing item_code)

Opportunistic pattern: picks a recent in-backfill date with theoretical SEs,
finds an aliment with enough headroom. Cleans up after itself.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_aliment_correction.run
"""
import frappe
import traceback
from frappe.utils import getdate

from hmd_agro.hmd_agro.utils.feed_correction import (
    get_aliment_state,
    post_aliment_corrections_batch,
    cancel_aliment_correction,
    CORR_MARKER_PREFIX,
)


TEST_DATE = "2026-05-14"
DELTA_POSITIVE = 10.0
DELTA_NEGATIVE = -5.0


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _bin_qty(item_code):
    return float(frappe.db.get_value("Bin",
        {"item_code": item_code}, "actual_qty") or 0)


def _correction_se_types(item_code):
    return frappe.db.sql_list("""
        SELECT DISTINCT stock_entry_type FROM `tabStock Entry`
        WHERE docstatus = 1 AND posting_date = %s AND remarks LIKE %s
    """, (TEST_DATE,
          f"{CORR_MARKER_PREFIX}%_{getdate(TEST_DATE)}_{item_code}"))


def run():
    print("\n" + "=" * 76)
    print("  ST5-15 — Per-aliment Saisie Alimentation backend")
    print("=" * 76)
    try:
        return _run_inner()
    except Exception:
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}

    # ── State structure
    state = get_aliment_state(TEST_DATE)
    _check(state["date"] == TEST_DATE, f"State has date={TEST_DATE}", results)
    _check(len(state["aliments"]) > 0, "State has aliment rows", results)

    # Pick a target aliment with enough theoretical headroom
    target = next(
        (a for a in state["aliments"] if a["theoretical_total"] >= 20), None,
    )
    if not target:
        _check(False, f"No aliment with >= 20 kg theoretical on {TEST_DATE}",
               results)
        return results
    item_code = target["item_code"]
    aliment_name = target["aliment"]
    theo = target["theoretical_total"]
    print(f"\n  Target: {aliment_name} ({item_code})  theoretical = {theo} kg")

    cancel_aliment_correction(TEST_DATE, item_code)  # clean start
    state0 = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                   if a["item_code"] == item_code)
    _check(not state0["has_correction"], "Initial: no correction", results)
    _check(abs(state0["actual_total"] - theo) < 0.01,
           f"Initial: actual_total == theoretical ({theo})", results)
    _check(isinstance(state0.get("lots"), list) and len(state0["lots"]) > 0,
           f"State has per-lot drill-down ({len(state0.get('lots') or [])} lots)",
           results)

    bin_before = _bin_qty(item_code)

    # ── Positive correction
    print(f"\n  ── +{DELTA_POSITIVE} kg correction (Material Issue) ──")
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + DELTA_POSITIVE},
    ])
    _check(r["posted"] > 0 and not r["errors"],
           f"+{DELTA_POSITIVE}kg: {r['posted']} SEs posted, 0 errors", results)
    _check(_correction_se_types(item_code) == ["Material Issue"],
           f"All correction SEs are Material Issue", results)

    bin_after = _bin_qty(item_code)
    drop = bin_before - bin_after
    _check(abs(drop - DELTA_POSITIVE) < 0.1,
           f"Bin dropped {drop:.3f} kg (expected ~{DELTA_POSITIVE})", results)

    state1 = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                   if a["item_code"] == item_code)
    _check(state1["has_correction"], "has_correction=True", results)
    _check(abs(state1["actual_total"] - (theo + DELTA_POSITIVE)) < 0.05,
           f"actual_total = {state1['actual_total']:.2f} ≈ "
           f"{theo + DELTA_POSITIVE}", results)

    # ── Idempotent re-save
    print("\n  ── Idempotent re-save ──")
    post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + DELTA_POSITIVE},
    ])
    _check(abs(_bin_qty(item_code) - bin_after) < 0.1,
           "Bin unchanged across re-saves (cancel + repost net-zero)", results)

    # ── Cancel → restored
    cancel_aliment_correction(TEST_DATE, item_code)
    _check(abs(_bin_qty(item_code) - bin_before) < 0.1,
           f"Bin restored to baseline after cancel", results)

    # ── Negative correction — Material Receipt with pinned basic_rate
    print(f"\n  ── {DELTA_NEGATIVE} kg correction (Material Receipt) ──")
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + DELTA_NEGATIVE},
    ])
    _check(r["posted"] > 0 and not r["errors"],
           f"{DELTA_NEGATIVE}kg posts SEs", results)
    _check(_correction_se_types(item_code) == ["Material Receipt"],
           "All correction SEs are Material Receipt", results)

    # Verify each Receipt line's basic_rate matches the theoretical SE's
    # valuation_rate for this item (the GL-neutral guarantee).
    theo_se_rows = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE docstatus = 1 AND posting_date = %s
          AND remarks LIKE %s LIMIT 1
    """, (TEST_DATE, f"RATION_DIST_%_{TEST_DATE}%"))
    theo_se = theo_se_rows[0][0] if theo_se_rows else None
    theo_rate = frappe.db.get_value("Stock Ledger Entry",
        {"voucher_no": theo_se, "item_code": item_code, "is_cancelled": 0},
        "valuation_rate") if theo_se else None
    if theo_rate:
        receipt_rates = frappe.db.sql_list("""
            SELECT sed.basic_rate FROM `tabStock Entry Detail` sed
            JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE se.docstatus = 1 AND se.posting_date = %s
              AND se.remarks LIKE %s AND sed.item_code = %s
        """, (TEST_DATE,
              f"{CORR_MARKER_PREFIX}%_{getdate(TEST_DATE)}_{item_code}",
              item_code))
        all_match = all(abs(float(r or 0) - float(theo_rate)) < 0.001
                        for r in receipt_rates)
        _check(all_match and len(receipt_rates) > 0,
               f"Receipt basic_rate = {theo_rate} on every per-lot line "
               f"(GL-neutral round trip)", results)

    cancel_aliment_correction(TEST_DATE, item_code)

    # ── no_change (actual == theoretical)
    print("\n  ── no_change ──")
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo},
    ])
    _check(r["no_change"] >= 1 and r["posted"] == 0,
           f"no_change reported, no SEs posted (got {r})", results)
    state_nc = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                     if a["item_code"] == item_code)
    _check(not state_nc["has_correction"],
           "no_change leaves has_correction=False", results)

    # Cancel on clean state → returns 0
    res_clean = cancel_aliment_correction(TEST_DATE, item_code)
    _check(res_clean["cancelled"] == 0,
           f"cancel on clean state: cancelled=0 (got {res_clean})", results)

    # ── Error paths
    print("\n  ── Error paths ──")
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": "ALI-DoesNotExist", "actual_total": 100.0},
    ])
    _check(r["errors"] and "Aucune ration" in r["errors"][0]["error"],
           "Unknown item rejected", results)

    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": -1},
    ])
    _check(r["errors"] and "négatif" in r["errors"][0]["error"],
           "Negative actual_total rejected", results)

    r = post_aliment_corrections_batch(TEST_DATE, [
        {"actual_total": 50.0},
    ])
    _check(r["errors"] and "missing" in r["errors"][0]["error"],
           "Missing item_code rejected", results)

    # Final cleanup — back to where we found it
    cancel_aliment_correction(TEST_DATE, item_code)
    _check(abs(_bin_qty(item_code) - bin_before) < 0.1,
           "Final state: bin matches baseline", results)

    # ── Drill-down proportional math (per-lot split)
    print("\n  ── Drill-down: per-lot proportional math ──")
    delta = 8.0
    post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + delta},
    ])
    after = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                  if a["item_code"] == item_code)
    lot_sum = 0.0
    all_correct = True
    for L in after["lots"]:
        share = L["qty_theoretical"] / theo if theo else 0
        expected = L["qty_theoretical"] + share * delta
        lot_sum += (L["qty_actual"] - L["qty_theoretical"])
        if abs(L["qty_actual"] - expected) > 0.05:
            all_correct = False
            print(f"     drift: {L['lot']} got {L['qty_actual']} expected {expected}")
    _check(all_correct,
           f"Per-lot qty_actual = theo + share*delta on every drill-down row",
           results)
    _check(abs(lot_sum - delta) < 0.05,
           f"Sum of per-lot deltas = {lot_sum:.3f} ≈ total delta {delta}",
           results)
    cancel_aliment_correction(TEST_DATE, item_code)

    # ── Mixed-direction batch: pick another aliment that SHARES at least one
    # lot with our target — required to exercise the multi-SE aggregation in
    # get_saisie_state (the bug we fixed).
    state_full = get_aliment_state(TEST_DATE)
    target_lots = {L["lot"] for L in target["lots"]}
    other = next(
        (a for a in state_full["aliments"]
         if a["item_code"] != item_code
         and a["theoretical_total"] >= 20
         and target_lots & {L["lot"] for L in a["lots"]}),
        None,
    )
    if other:
        print(f"\n  ── Mixed-direction batch: +5kg {target['aliment']}, "
              f"-3kg {other['aliment']} ──")
        bin_t1 = _bin_qty(item_code)
        bin_t2 = _bin_qty(other["item_code"])
        r = post_aliment_corrections_batch(TEST_DATE, [
            {"item_code": item_code,
             "actual_total": theo + 5.0},
            {"item_code": other["item_code"],
             "actual_total": other["theoretical_total"] - 3.0},
        ])
        _check(r["posted"] > 0 and not r["errors"],
               f"Mixed batch posts {r['posted']} SEs across both aliments",
               results)
        # Issue exists for one, Receipt for the other
        types_a = _correction_se_types(item_code)
        types_b = _correction_se_types(other["item_code"])
        _check(types_a == ["Material Issue"] and types_b == ["Material Receipt"],
               f"{target['aliment']}: Issue / {other['aliment']}: Receipt — "
               f"directions separated cleanly", results)
        bin_t1_after = _bin_qty(item_code)
        bin_t2_after = _bin_qty(other["item_code"])
        _check(abs((bin_t1 - bin_t1_after) - 5.0) < 0.1
               and abs((bin_t2_after - bin_t2) - 3.0) < 0.1,
               f"Bin shifts: {target['aliment']} -5.0, "
               f"{other['aliment']} +3.0 — both directions applied", results)

        # Now the critical test — aggregation in get_saisie_state across multiple
        # per-aliment SEs for the SAME lot (the bug we fixed). Pick any lot that
        # uses BOTH aliments — its has_correction must be True, and per-line
        # qty_actual must reflect BOTH corrections.
        a_after = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                        if a["item_code"] == item_code)
        b_after = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                        if a["item_code"] == other["item_code"])
        lots_a = {L["lot"]: L for L in a_after["lots"]}
        lots_b = {L["lot"]: L for L in b_after["lots"]}
        shared_lots = set(lots_a) & set(lots_b)
        _check(len(shared_lots) > 0,
               f"At least one lot uses both aliments ({len(shared_lots)} shared)",
               results)
        # For one shared lot, both aliment lines should show actual != theoretical
        if shared_lots:
            sample_lot = next(iter(shared_lots))
            la = lots_a[sample_lot]
            lb = lots_b[sample_lot]
            _check(abs(la["qty_actual"] - la["qty_theoretical"]) > 0.001
                   and abs(lb["qty_actual"] - lb["qty_theoretical"]) > 0.001,
                   f"Shared lot {sample_lot}: BOTH aliment lines reflect "
                   f"corrections in get_aliment_state — proves multi-SE "
                   f"aggregation works", results)

        cancel_aliment_correction(TEST_DATE, item_code)
        cancel_aliment_correction(TEST_DATE, other["item_code"])

    # ── no_change cancels prior correction
    print("\n  ── no_change after prior correction cancels it ──")
    post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + 7.0},
    ])
    state_before_noop = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                              if a["item_code"] == item_code)
    _check(state_before_noop["has_correction"],
           "Pre-condition: correction is present", results)
    r = post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo},
    ])
    _check(r["no_change"] >= 1 and r["posted"] == 0,
           f"Resubmit at theoretical → no_change={r['no_change']}, "
           f"posted={r['posted']}", results)
    state_after_noop = next(a for a in get_aliment_state(TEST_DATE)["aliments"]
                             if a["item_code"] == item_code)
    _check(not state_after_noop["has_correction"]
           and abs(state_after_noop["actual_total"] - theo) < 0.05,
           "Prior correction was cleared (has_correction=False, actual=theo)",
           results)

    # ── Unrelated aliments stay untouched when correcting one
    print("\n  ── Correcting one aliment leaves others' state unchanged ──")
    snap = {a["item_code"]: a["actual_total"]
            for a in get_aliment_state(TEST_DATE)["aliments"]}
    post_aliment_corrections_batch(TEST_DATE, [
        {"item_code": item_code, "actual_total": theo + 12.0},
    ])
    snap_after = {a["item_code"]: a["actual_total"]
                   for a in get_aliment_state(TEST_DATE)["aliments"]}
    untouched = [ic for ic in snap if ic != item_code
                  and abs(snap[ic] - snap_after[ic]) < 0.05]
    _check(len(untouched) == len(snap) - 1,
           f"All other aliments unchanged "
           f"({len(untouched)}/{len(snap)-1} match)", results)
    cancel_aliment_correction(TEST_DATE, item_code)

    # ── Aliments with theoretical=0 are hidden
    print("\n  ── get_aliment_state hides aliments with theo=0 ──")
    all_aliments = get_aliment_state(TEST_DATE)["aliments"]
    none_zero = all(a["theoretical_total"] > 0 for a in all_aliments)
    _check(none_zero,
           f"No aliment row has theoretical_total = 0 "
           f"(all {len(all_aliments)} > 0)", results)

    print("\n" + "=" * 76)
    total = results["pass"] + results["fail"]
    print(f"  RÉSULTATS: {results['pass']}/{total} passés, "
          f"{results['fail']} échoués")
    print("=" * 76)
    return results
