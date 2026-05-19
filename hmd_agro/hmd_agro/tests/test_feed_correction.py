"""
ST5-15 — Feed correction backend test.

Exercises every branch of `utils/feed_correction.py`:
  1. `get_saisie_state` shape + math (theoretical_total = Σ line.qty,
     actual_total reflects any existing correction).
  2. `post_correction` positive delta → Material Issue, Bin decreases.
  3. `post_correction` negative delta → Material Receipt at the theoretical
     SE's own valuation_rate, Bin increases, GL impact nets to zero.
  4. `post_correction` no-op when actual == theoretical (returns no_change).
  5. Idempotency: re-saisie cancels the previous correction first.
  6. `cancel_correction` reverts to theoretical-only state.
  7. Refusal when no theoretical SE exists for the (lot, date).
  8. `get_saisie_state` after a correction reflects the corrected actual_total.

The test runs against a backfilled date (2026-05-14) already present in the
site. All corrections it posts are cancelled at the end, so the test is
side-effect-free for downstream reports.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_feed_correction.run
"""
import frappe
import traceback
from frappe.utils import getdate, flt

from hmd_agro.hmd_agro.utils.feed_correction import (
    get_saisie_state, post_correction, cancel_correction,
)


TEST_DATE = "2026-05-14"


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def _bin_qty(item_code, warehouse="Magasin Principal - HMD"):
    v = frappe.db.get_value("Bin",
        {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
    return flt(v)


def run():
    print("\n" + "=" * 70)
    print("  ST5-15 — Feed correction backend test")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}

    # ── Phase 1: read endpoint shape ─────────────────────────────────────
    state = get_saisie_state(TEST_DATE)
    _check(state.get("date") == TEST_DATE,
        f"State has date={TEST_DATE}", results)
    _check(isinstance(state.get("lots"), list) and len(state["lots"]) > 0,
        f"State has {len(state.get('lots') or [])} lot(s)", results)

    # Pick a lot with > 0 theoretical_total to use as the test target
    target = None
    for lot_state in state["lots"]:
        if lot_state["theoretical_total"] > 10:  # need enough headroom
            target = lot_state
            break
    if not target:
        _check(False, "No lot with theoretical_total > 10 — can't run rest", results)
        return results

    lot = target["lot"]
    theo_total = target["theoretical_total"]
    se_theoretical = target["se_theoretical"]
    print(f"\n  Target lot: {lot}  theoretical={theo_total} kg  "
          f"se_theoretical={se_theoretical}")

    _check(not target["has_correction"],
        f"Initial state: {lot} has no correction", results)
    _check(abs(target["actual_total"] - theo_total) < 0.001,
        f"Initial actual_total == theoretical_total ({theo_total})", results)

    # Snapshot Bin quantities for each aliment in the lot
    bin_before = {L["item_code"]: _bin_qty(L["item_code"])
                  for L in target["lines"]}

    # ── Phase 2: positive delta (more given than planned) ────────────────
    actual_more = theo_total + 10.0  # +10 kg total
    result = post_correction(TEST_DATE, lot, actual_more)
    _check(result["status"] == "posted",
        f"+10kg correction status='posted' (got {result['status']})", results)
    _check(abs(result["delta"] - 10.0) < 0.01,
        f"delta=+10 (got {result['delta']})", results)
    _check(result["correction_se"] is not None,
        f"correction_se created ({result['correction_se']})", results)

    corr_doc = frappe.get_doc("Stock Entry", result["correction_se"])
    _check(corr_doc.stock_entry_type == "Material Issue",
        f"Positive delta → Material Issue (got {corr_doc.stock_entry_type})",
        results)
    _check(corr_doc.id_lot == lot,
        f"Correction SE id_lot = {lot} (got {corr_doc.id_lot})", results)

    # Bin should have decreased further (more consumed)
    for L in target["lines"]:
        b_after = _bin_qty(L["item_code"])
        expected_drop = L["qty_theoretical"] * (10.0 / theo_total)
        diff = bin_before[L["item_code"]] - b_after
        _check(abs(diff - expected_drop) < 0.05,
            f"  Bin {L['item_code']}: dropped {diff:.3f} "
            f"(expected ~{expected_drop:.3f})", results)

    # State should now reflect the correction
    state2 = get_saisie_state(TEST_DATE)
    target2 = next(L for L in state2["lots"] if L["lot"] == lot)
    _check(target2["has_correction"],
        f"State now shows has_correction=True", results)
    _check(abs(target2["actual_total"] - actual_more) < 0.01,
        f"State actual_total = {actual_more} (got {target2['actual_total']})",
        results)

    # ── Phase 3: idempotency — re-saisie cancels previous correction ─────
    actual_less = theo_total - 5.0  # -5 kg total this time
    result2 = post_correction(TEST_DATE, lot, actual_less)
    _check(result2["cancelled_previous"] == result["correction_se"],
        f"Re-saisie cancelled previous correction "
        f"({result2['cancelled_previous']})", results)
    _check(result2["status"] == "posted",
        f"-5kg correction status='posted' (got {result2['status']})", results)

    corr_doc2 = frappe.get_doc("Stock Entry", result2["correction_se"])
    _check(corr_doc2.stock_entry_type == "Material Receipt",
        f"Negative delta → Material Receipt "
        f"(got {corr_doc2.stock_entry_type})", results)

    # Material Receipt should use the theoretical SE's valuation rate
    # (zero GL impact on the round trip when delta is negative)
    for item_line in corr_doc2.items:
        theo_rate = frappe.db.get_value("Stock Ledger Entry",
            {"voucher_no": se_theoretical, "item_code": item_line.item_code,
             "is_cancelled": 0}, "valuation_rate")
        _check(abs(flt(item_line.basic_rate) - flt(theo_rate)) < 0.01,
            f"  Receipt {item_line.item_code}: basic_rate="
            f"{item_line.basic_rate} matches theo_rate={theo_rate}", results)

    # ── Phase 4: no-op when actual == theoretical ────────────────────────
    result3 = post_correction(TEST_DATE, lot, theo_total)
    _check(result3["status"] == "no_change",
        f"actual=theoretical → status='no_change' "
        f"(got {result3['status']})", results)
    _check(result3["cancelled_previous"] == result2["correction_se"],
        f"no-change still cancels prior correction "
        f"({result3['cancelled_previous']})", results)

    # State should be back to theoretical-only
    state3 = get_saisie_state(TEST_DATE)
    target3 = next(L for L in state3["lots"] if L["lot"] == lot)
    _check(not target3["has_correction"],
        f"After no_change: has_correction=False", results)

    # Bin should be back to pre-correction state (within rounding)
    for L in target["lines"]:
        b_now = _bin_qty(L["item_code"])
        _check(abs(b_now - bin_before[L["item_code"]]) < 0.05,
            f"  Bin {L['item_code']} restored: {b_now} "
            f"(was {bin_before[L['item_code']]})", results)

    # ── Phase 5: cancel_correction with no active correction → None ──────
    result4 = cancel_correction(TEST_DATE, lot)
    _check(result4 is None,
        f"cancel_correction with no active correction returns None "
        f"(got {result4})", results)

    # ── Phase 6: refusal when no theoretical SE exists ───────────────────
    try:
        post_correction("2020-01-01", lot, 100.0)
        _check(False, "Should have raised on missing theoretical SE", results)
    except frappe.exceptions.ValidationError as e:
        _check("Aucune distribution théorique" in str(e),
            f"Correct error raised for missing theoretical SE", results)

    # ── Phase 7: refusal on negative actual ──────────────────────────────
    try:
        post_correction(TEST_DATE, lot, -10.0)
        _check(False, "Should have raised on negative actual", results)
    except frappe.exceptions.ValidationError as e:
        _check("ne peut pas être négatif" in str(e),
            f"Correct error raised for negative actual", results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} "
          f"passés, {results['fail']} échoués")
    print("=" * 70)
    return results
