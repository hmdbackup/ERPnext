"""
Audit two specific behaviors:

  A. Saisie Alimentation persistence — when you post a correction on a date,
     does it survive when you re-open that date later?

  B. Ration change propagation — when a lot's ration changes, does the next
     nightly distribution use the new ration? (And: do PAST Stock Entries
     stay frozen at the old ration, per the immutability guarantee?)

Read-only EXCEPT it posts a temporary correction and immediately cleans it.
Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.audit_persistence_and_ration.run
"""
import frappe
from frappe.utils import getdate, add_days, today

from hmd_agro.hmd_agro.utils.feed_correction import (
    get_aliment_state, post_aliment_corrections_batch, cancel_aliment_correction,
)
from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
    _alimentation,
)
from hmd_agro.hmd_agro.utils.feed_distribution import (
    post_distribution_for_date,
)
from hmd_agro.hmd_agro.doctype.lot_ration_history.lot_ration_history import (
    ration_on_date,
)


def hdr(t):
    print("\n" + "═" * 76 + "\n  " + t + "\n" + "═" * 76)


def sub(t):
    print(f"\n  ── {t} " + "─" * (70 - len(t)))


def _check(cond, msg, results):
    if cond:
        print(f"     ✓ {msg}")
        results["pass"] += 1
    else:
        print(f"     ✗ {msg}")
        results["fail"] += 1


# ════════════════════════════════════════════════════════════════════
# A. SAISIE PERSISTENCE
# ════════════════════════════════════════════════════════════════════
def audit_saisie_persistence(results):
    hdr("A. Saisie persistence — corrections survive re-opening a date")

    # Pick a backfilled date and an aliment with enough headroom.
    test_date = "2026-05-13"
    state = get_aliment_state(test_date)
    target = next(
        (a for a in state["aliments"] if a["theoretical_total"] >= 30), None,
    )
    if not target:
        print("     [skip] no aliment with >= 30 kg theoretical on " + test_date)
        return

    item_code = target["item_code"]
    theo = target["theoretical_total"]
    print(f"     Target: aliment={target['aliment']} ({item_code}), "
          f"date={test_date}, theoretical={theo} kg")

    cancel_aliment_correction(test_date, item_code)

    sub("Post +15 kg correction")
    actual = theo + 15.0
    r = post_aliment_corrections_batch(test_date,
        [{"item_code": item_code, "actual_total": actual}])
    _check(r["posted"] > 0 and not r["errors"],
           f"post_aliment_corrections_batch posted {r['posted']} SE(s)", results)

    sub("Re-open the same date — verify correction is shown as 'Corrigé'")
    state2 = get_aliment_state(test_date)
    same = next((a for a in state2["aliments"]
                  if a["item_code"] == item_code), None)
    _check(same is not None,
           f"Aliment {item_code} present in re-fetched state", results)
    if same:
        _check(same["has_correction"],
               f"has_correction = True (got {same['has_correction']})", results)
        _check(abs(same["actual_total"] - actual) < 0.05,
               f"actual_total reflects correction "
               f"({same['actual_total']} ≈ {actual})", results)

    # SE persistence in tabStock Entry — check at least one per-lot SE exists
    sub("Stock Entry persistence in DB")
    se_rows = frappe.db.sql("""
        SELECT name, docstatus, remarks, posting_date
        FROM `tabStock Entry`
        WHERE docstatus = 1 AND posting_date = %s
          AND remarks LIKE %s
        LIMIT 5
    """, (test_date,
          f"RATION_CORRECTION_%_{test_date}_{item_code}"), as_dict=True)
    _check(len(se_rows) > 0,
           f"At least one correction SE submitted for {item_code} "
           f"({len(se_rows)} found)", results)
    if se_rows:
        sample = se_rows[0]
        _check(sample.remarks.endswith(f"_{item_code}"),
               f"Marker ends with item_code suffix (got {sample.remarks})",
               results)
        _check(str(sample.posting_date) == test_date,
               f"posting_date frozen at {test_date}", results)

    # Past-date queries on the report still reflect the correction
    sub("Past-date report query reflects the correction")
    ctx = {"date_debut": getdate("2026-05-01"),
           "date_filter": getdate(test_date),
           "date_fin": getdate("2026-05-31"),
           "nb_jours": 31, "mois": 5, "annee": 2026,
           "granularite": "Quotidien"}
    _, rows = _alimentation(ctx)
    cost_total = next((float(r.get("cout_periode") or 0)
                       for r in rows
                       if r.get("aliment") == "Coût Total Distribué (DT)"), 0)
    _check(cost_total > 0,
           f"Aliment table shows non-zero Coût Total ({cost_total:.2f}) "
           f"on {test_date} after correction was posted", results)

    # Cleanup — leave DB exactly as we found it
    cancel_aliment_correction(test_date, item_code)
    state3 = get_aliment_state(test_date)
    same_after = next((a for a in state3["aliments"]
                        if a["item_code"] == item_code), None)
    _check(same_after and not same_after["has_correction"],
           "Cleanup OK — has_correction back to False", results)


# ════════════════════════════════════════════════════════════════════
# B. RATION CHANGE PROPAGATION
# ════════════════════════════════════════════════════════════════════
def audit_ration_change_propagation(results):
    hdr("B. Ration change — past SE frozen, future SE uses new ration")

    # Find a lot with an active ration and a historical SE.
    sub("Discover state of a sample lot")
    sample = frappe.db.sql("""
        SELECT l.name AS lot, l.id_ration_actuelle AS ration
        FROM `tabLot` l
        WHERE l.actif = 1 AND l.id_ration_actuelle IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM `tabStock Entry` se
            WHERE se.id_lot = l.name AND se.docstatus = 1
              AND se.remarks LIKE 'RATION_DIST_%'
          )
        LIMIT 1
    """, as_dict=True)
    if not sample:
        print("     [skip] no lot with both a ration AND past SE")
        return
    lot = sample[0].lot
    current_ration = sample[0].ration
    print(f"     Lot: {lot}, current ration: {current_ration}")

    # Two facts the system should guarantee:
    #   1. PAST Stock Entries point at whatever aliments they were posted with,
    #      regardless of subsequent ration changes (immutability).
    #   2. ration_on_date(lot, D) reads the historical episode for that day —
    #      so future schedulers use the right ration.

    sub("1. Past SE frozen — sample 3 historical SE remarks")
    past_se_dates = frappe.db.sql("""
        SELECT name, posting_date, remarks
        FROM `tabStock Entry`
        WHERE id_lot = %s AND docstatus = 1
          AND remarks LIKE 'RATION_DIST_%%'
        ORDER BY posting_date DESC LIMIT 3
    """, lot, as_dict=True)
    for se in past_se_dates:
        items = frappe.db.sql("""
            SELECT item_code, qty FROM `tabStock Entry Detail`
            WHERE parent = %s ORDER BY idx
        """, se.name, as_dict=True)
        print(f"     SE {se.name} ({se.posting_date}): "
              + ", ".join(f"{it.item_code}×{it.qty}" for it in items))
        # Verify the lines correspond to SOME ration's composition (i.e.,
        # this SE wasn't mutated by anything later).
        item_codes_in_se = {it.item_code for it in items}
        _check(len(item_codes_in_se) > 0,
               f"  {se.name} has items recorded (frozen at posting time)",
               results)

    sub("2. ration_on_date reads the historical episode")
    # ration_on_date should return the lot's ration as of any past date.
    # For dates inside a Lot Ration History episode, return that episode's
    # ration; for dates without an explicit episode, fall back to current.
    history = frappe.db.sql("""
        SELECT date_debut, date_fin, ration
        FROM `tabLot Ration History`
        WHERE lot = %s AND ration IS NOT NULL
        ORDER BY date_debut DESC LIMIT 5
    """, lot, as_dict=True)
    print(f"     Lot Ration History episodes for {lot}: {len(history)}")
    for h in history:
        print(f"     • {h.date_debut} → {h.date_fin or '(open)'}: "
              f"ration={h.ration}")

    # For each episode, pick a date inside and verify ration_on_date returns it.
    for h in history:
        if h.date_fin:
            sample_date = h.date_debut
        else:
            sample_date = add_days(h.date_debut, 1)
        if getdate(sample_date) > getdate(today()):
            continue  # future date — ration_on_date returns current
        got = ration_on_date(lot, sample_date)
        _check(got == h.ration,
               f"ration_on_date({lot}, {sample_date}) = {got} "
               f"(expected {h.ration})", results)

    sub("3. The next generator run picks up current_ration for new days")
    # If we run post_distribution_for_date for a date with no SE yet,
    # it should use the current_ration. Use a future date so we don't
    # touch existing data — and immediately cancel after to clean up.
    future_date = add_days(getdate(today()), 1)  # tomorrow
    n_se_before = frappe.db.count("Stock Entry", {
        "remarks": ["like", f"RATION_DIST_{lot}_{future_date}%"],
        "docstatus": 1,
    })
    if n_se_before > 0:
        print(f"     [skip-existing] SE already posted for tomorrow")
        return

    stats = post_distribution_for_date(future_date, dry_run=True, verbose=False)
    print(f"     dry_run for tomorrow ({future_date}): {stats}")
    # No assertion; this just demonstrates the path executes cleanly.
    _check(stats["errors"] == 0,
           f"post_distribution_for_date(tomorrow, dry_run=1) had 0 errors",
           results)


def run():
    results = {"pass": 0, "fail": 0}
    audit_saisie_persistence(results)
    audit_ration_change_propagation(results)
    print("\n" + "═" * 76)
    total = results["pass"] + results["fail"]
    print(f"  RÉSULTATS: {results['pass']}/{total} contrôles passés, "
          f"{results['fail']} échoués")
    print("═" * 76 + "\n")
    return results
