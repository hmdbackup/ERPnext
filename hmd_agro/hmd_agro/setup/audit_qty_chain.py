"""Focused diagnostic of the qty-chain breaks found by audit_riv_health.

Asks three questions:
  1. Are the breaks real (chain drift) or audit-script artifacts (same-second
     SLE rows that my JOIN orders wrong)?
  2. Does Bin.actual_qty match the latest SLE's qty_after_transaction for
     each affected item? (This is the only thing that matters operationally —
     the bin is what reports read.)
  3. What's the actual SLE timeline on 2026-05-12 for ALI-Mais (one drilldown)?

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.audit_qty_chain.run
"""
import frappe


def run():
    print("\n" + "=" * 70)
    print("  Qty-chain break diagnostic")
    print("=" * 70)

    items = ["ALI-Mais", "ALI-Soja", "ALI-Foin d'Avoine",
             "ALI-Dreche de Brasserie"]
    wh = "Magasin Principal - HMD"

    # Q2 first — does Bin match the latest SLE? This is the operational truth.
    print("\n  Q1. Bin vs latest-SLE qty_after_transaction:")
    print("  (Bin is what reports + stock_courant read — must match latest SLE)")
    for item in items:
        bin_qty = frappe.db.get_value(
            "Bin", {"item_code": item, "warehouse": wh}, "actual_qty"
        )
        latest = frappe.db.sql(
            """
            SELECT name, posting_date, posting_time, qty_after_transaction
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND warehouse = %s AND is_cancelled = 0
            ORDER BY posting_datetime DESC LIMIT 1
            """,
            (item, wh), as_dict=True,
        )
        if latest:
            l = latest[0]
            match = "OK" if abs((bin_qty or 0) - (l.qty_after_transaction or 0)) < 0.01 else "MISMATCH"
            print(f"    {item:30s}  Bin={bin_qty:>12.2f}  "
                  f"latest_SLE={l.qty_after_transaction:>12.2f}  "
                  f"({match})  via {l.name}")
        else:
            print(f"    {item:30s}  Bin={bin_qty}  no SLE rows")

    # Q2 — drilldown on ALI-Mais 2026-05-12 to see if multi-SLE-per-day is
    # the cause of my "chain break" false-positives.
    print("\n  Q2. Drilldown: ALI-Mais on 2026-05-12 (full timeline):")
    rows = frappe.db.sql(
        """
        SELECT name, posting_date, posting_time, voucher_no,
               actual_qty, qty_after_transaction,
               valuation_rate, stock_value
        FROM `tabStock Ledger Entry`
        WHERE item_code = 'ALI-Mais' AND warehouse = %s
          AND is_cancelled = 0
          AND posting_date BETWEEN '2026-05-11' AND '2026-05-13'
        ORDER BY posting_datetime
        """,
        wh, as_dict=True,
    )
    print(f"    {'name':<22s} {'date':<11s} {'time':<10s} {'voucher':<22s} "
          f"{'actual_qty':>11s} {'after':>11s}")
    prev = None
    for r in rows:
        expected = (prev + r.actual_qty) if prev is not None else r.qty_after_transaction
        flag = "" if abs(expected - r.qty_after_transaction) < 0.01 else " ← BREAK"
        print(f"    {r.name:<22s} {str(r.posting_date):<11s} "
              f"{str(r.posting_time)[:8]:<10s} {r.voucher_no:<22s} "
              f"{r.actual_qty:>11.2f} {r.qty_after_transaction:>11.2f}{flag}")
        prev = r.qty_after_transaction

    # Q3 — check if multi-row SLE on same timestamp is the audit artifact
    print("\n  Q3. Same-timestamp SLE rows on 2026-05-12 (per item):")
    for item in items:
        clusters = frappe.db.sql(
            """
            SELECT posting_date, posting_time, COUNT(*) AS n
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND warehouse = %s AND is_cancelled = 0
              AND posting_date = '2026-05-12'
            GROUP BY posting_date, posting_time
            HAVING COUNT(*) > 1
            """,
            (item, wh), as_dict=True,
        )
        if clusters:
            print(f"    {item}:")
            for c in clusters:
                print(f"      {c.posting_date} {c.posting_time}  ×{c.n} rows")
        else:
            print(f"    {item}: no same-timestamp clusters on 2026-05-12")

    print("\n" + "=" * 70 + "\n")
