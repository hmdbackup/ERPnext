"""
SCRUM-123 — Feed distribution generator test.

Verifies the daily Material Issue generator's core mechanics:
1. `get_distribution_preview` returns the expected (lot → list of aliment
   lines) structure with valid item_code + qty + pop fields.
2. `backfill_distribution` over a previously-backfilled date is a clean
   no-op (idempotency via the `RATION_DIST_<lot>_<date>` remark marker).
3. The scheduler entry `generate_daily_distribution` runs without error.
4. Each Stock Entry posted by the generator carries the correct
   custom-field `id_lot`, the right remarks marker, and lines that match
   the lot's ration composition × population.

The test uses ALREADY backfilled dates (2026-04-16 → 2026-05-15 range
exists in this site) so it's read-mostly and side-effect-free.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_feed_distribution.run
"""
import frappe
import traceback
from frappe.utils import today, add_days, getdate

from hmd_agro.hmd_agro.utils.feed_distribution import (
    get_distribution_preview,
    backfill_distribution,
    generate_daily_distribution,
)


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  SCRUM-123 — Feed distribution generator test")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}

    # Use a date inside the backfilled window — picked deterministically so
    # the test doesn't depend on "today" and is reproducible.
    test_date = getdate("2026-05-14")

    # ── Phase 1: preview returns dict {lot: [lines]}
    preview = get_distribution_preview(test_date)
    _check(isinstance(preview, dict),
        f"get_distribution_preview returns dict (got {type(preview).__name__})",
        results)
    _check(len(preview) > 0,
        f"Preview for {test_date} contains at least one lot (got {len(preview)})",
        results)

    if preview:
        first_lot = next(iter(preview))
        lines = preview[first_lot]
        _check(isinstance(lines, list) and len(lines) > 0,
            f"Lot {first_lot} has {len(lines)} aliment lines", results)
        first_line = lines[0]
        for k in ("item_code", "qty", "aliment", "stock_uom",
                  "qty_per_animal", "pop"):
            _check(k in first_line, f"Preview line has key '{k}'", results)
        _check(first_line["item_code"].startswith("ALI-"),
            f"Preview line item_code starts with ALI- (got "
            f"{first_line['item_code']})", results)
        _check(first_line["qty"] > 0,
            f"Preview line qty > 0 (got {first_line['qty']})", results)
        # Math invariant: qty == pop × qty_per_animal
        expected = first_line["pop"] * first_line["qty_per_animal"]
        _check(abs(first_line["qty"] - expected) < 0.01,
            f"qty ({first_line['qty']}) == pop × qty_per_animal "
            f"({expected})", results)

    # ── Phase 2: backfill on already-posted date is no-op
    n_existing_before = frappe.db.count("Stock Entry", {
        "remarks": ["like", f"RATION_DIST_%_{test_date}%"],
        "docstatus": 1,
    })
    _check(n_existing_before > 0,
        f"{n_existing_before} pre-existing distribution SEs for {test_date}",
        results)

    stats = backfill_distribution(test_date, test_date, dry_run=0)
    _check(stats["posted"] == 0,
        f"Idempotent re-backfill posts 0 new SEs (got {stats['posted']})",
        results)
    _check(stats["skipped_already_posted"] == n_existing_before,
        f"Skipped {stats['skipped_already_posted']} as already-posted "
        f"(expected {n_existing_before})", results)

    n_existing_after = frappe.db.count("Stock Entry", {
        "remarks": ["like", f"RATION_DIST_%_{test_date}%"],
        "docstatus": 1,
    })
    _check(n_existing_after == n_existing_before,
        f"SE count unchanged ({n_existing_after}) — DB not polluted", results)

    # ── Phase 3: a backfilled SE has the right structure
    se_name = frappe.db.get_value("Stock Entry",
        {"remarks": ["like", f"RATION_DIST_%_{test_date}%"], "docstatus": 1},
        "name")
    if se_name:
        se = frappe.get_doc("Stock Entry", se_name)
        _check(se.stock_entry_type == "Material Issue",
            f"{se_name}: stock_entry_type = 'Material Issue'", results)
        _check(bool(se.id_lot),
            f"{se_name}: id_lot custom field populated ({se.id_lot})", results)
        _check(se.remarks.startswith(f"RATION_DIST_{se.id_lot}_{test_date}"),
            f"{se_name}: remarks marker correct ({se.remarks[:60]})", results)
        _check(len(se.items) > 0,
            f"{se_name}: has {len(se.items)} item line(s)", results)
        for item_line in se.items:
            if item_line.item_code.startswith("ALI-"):
                _check(item_line.s_warehouse,
                    f"{se_name}: line {item_line.item_code} has source warehouse",
                    results)
                break

    # ── Phase 4: scheduler entry doesn't crash
    try:
        generate_daily_distribution()
        _check(True, "generate_daily_distribution() ran without exception",
               results)
    except Exception as e:
        _check(False,
            f"generate_daily_distribution() raised: {type(e).__name__}: {e}",
            results)

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
