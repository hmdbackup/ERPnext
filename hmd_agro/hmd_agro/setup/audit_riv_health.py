"""Quick variance / RIV-queue health check.

Verifies that backdated correction Stock Entries (RATION_CORRECTION_*) didn't
leave Stock Ledger Entries in an inconsistent state and that no Repost Item
Valuation jobs are stuck.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.audit_riv_health.run
"""
import frappe


def run():
    print("\n" + "=" * 70)
    print("  RIV / SLE variance health check")
    print("=" * 70)

    # 1. RIV queue
    riv_pending = frappe.get_all(
        "Repost Item Valuation",
        filters={"status": ["in", ["Queued", "In Progress", "Failed"]]},
        fields=["name", "item_code", "warehouse", "status", "posting_date"],
        order_by="creation desc",
        limit=20,
    )
    riv_done = frappe.db.count("Repost Item Valuation", {"status": "Completed"})
    riv_all = frappe.db.count("Repost Item Valuation")

    print(f"\n  RIV totals: {riv_all} all / {riv_done} completed / "
          f"{len(riv_pending)} pending")
    if riv_pending:
        print("  ! Pending RIV jobs (should be empty in steady state):")
        for r in riv_pending:
            print(f"    {r.name}  item={r.item_code}  "
                  f"wh={r.warehouse}  status={r.status}")
    else:
        print("  OK — no pending RIV jobs")

    # 2. SLE rows with NULL critical fields
    bad_nulls = frappe.db.sql(
        """
        SELECT name, item_code, warehouse, posting_date
        FROM `tabStock Ledger Entry`
        WHERE is_cancelled = 0
          AND (qty_after_transaction IS NULL OR stock_value IS NULL)
        LIMIT 20
        """,
        as_dict=True,
    )
    print(f"\n  SLE rows with NULL qty_after_transaction or stock_value: "
          f"{len(bad_nulls)}")
    if bad_nulls:
        print("  ! These need a Repost Item Valuation:")
        for b in bad_nulls:
            print(f"    {b.name}  {b.item_code}@{b.warehouse}  {b.posting_date}")
    else:
        print("  OK — all submitted SLE have qty_after_transaction + stock_value")

    # 3. Backdated correction SEs sample (confirm pattern works)
    corrections = frappe.db.sql(
        """
        SELECT name, posting_date, posting_time, remarks, total_outgoing_value
        FROM `tabStock Entry`
        WHERE docstatus = 1 AND set_posting_time = 1
          AND remarks LIKE 'RATION_CORRECTION_%%'
        ORDER BY creation DESC LIMIT 5
        """,
        as_dict=True,
    )
    print(f"\n  Recent backdated correction SEs (sample of 5):")
    print(f"  count of submitted correction SEs: "
          f"{frappe.db.count('Stock Entry', {'docstatus': 1, 'remarks': ['like', 'RATION_CORRECTION_%']})}")
    for s in corrections:
        print(f"    {s.name}  {s.posting_date} {s.posting_time}  "
              f"out_val={s.total_outgoing_value}")

    # 4. SLE rows tied to those correction SEs — confirm they have qty/value
    if corrections:
        sample_se = corrections[0].name
        sle_for_se = frappe.db.sql(
            """
            SELECT name, item_code, qty_after_transaction, stock_value,
                   valuation_rate, actual_qty
            FROM `tabStock Ledger Entry`
            WHERE voucher_no = %s AND is_cancelled = 0
            """,
            sample_se,
            as_dict=True,
        )
        print(f"\n  SLE rows for sample correction SE {sample_se}:")
        for r in sle_for_se:
            print(f"    {r.item_code}  "
                  f"actual_qty={r.actual_qty}  "
                  f"after={r.qty_after_transaction}  "
                  f"val_rate={r.valuation_rate}  "
                  f"stock_value={r.stock_value}")

    # For deeper Bin vs latest-SLE per-item diagnostics, use:
    #   bench --site hmd.localhost execute \
    #     hmd_agro.hmd_agro.setup.audit_qty_chain.run
    # That script samples 4 representative Aliment items and confirms Bin
    # matches latest SLE (the only operational truth — reports + stock_courant
    # + native reorder all read Bin.actual_qty, derived from latest non-
    # cancelled SLE's qty_after_transaction).

    print("\n" + "=" * 70 + "\n")
    return {
        "riv_pending": len(riv_pending),
        "sle_null": len(bad_nulls),
    }
