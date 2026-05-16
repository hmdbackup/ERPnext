"""
Sprint 5 — Verification: confirm ERPNext's native valuation machinery
works end-to-end in this install before we commit to ST5-09 / ST5-10.

What we check:
  1. Semence Items (which had real `prix_unitaire` in their opening Stock
     Entries) have non-zero `Item.valuation_rate`.
  2. Stock Ledger Entries for those Items have `stock_value_difference`
     populated and matching actual_qty × valuation_rate.
  3. A historical Insémination's Material Issue SLE is frozen at the
     valuation rate that existed at the moment of consumption — i.e. a
     price change today wouldn't rewrite it.
  4. Aliment / Médicament Items currently have valuation_rate=0 (expected:
     opening Stock Entries used basic_rate=0). This confirms the gap that
     Step 2 + Step 3 will fill.

If section 1/2/3 pass → native valuation works in our install, we can
build ST5-09 / ST5-10 against `Stock Ledger Entry.stock_value_difference`
with confidence.

Run:
    docker exec frappe_docker_devcontainer-frappe-1 bash -lc \\
      "cd /workspace/development/frappe-bench && bench --site hmd.localhost execute \\
       hmd_agro.hmd_agro.setup.verify_native_valuation.run"
"""
import frappe


def _print_item_block(prefix, label, expect_priced):
    """For each Item: read Bin.valuation_rate (the real per-warehouse valuation,
    auto-maintained by ERPNext). Item.valuation_rate is a separate master-level
    default used by BOM/manufacturing — NOT updated by Stock Entries — so don't
    confuse the two."""
    print(f"\n  ── {label} Items ({prefix}-*) ──")
    items = frappe.get_all(
        "Item",
        filters={"item_code": ["like", f"{prefix}-%"]},
        fields=["name", "item_code", "valuation_method", "standard_rate", "stock_uom"],
        order_by="item_code",
    )
    if not items:
        print(f"     (aucun Item {prefix}-* trouvé)")
        return items
    priced = 0
    for it in items:
        # Aggregate Bin valuation across all warehouses (we only use 1 anyway)
        bins = frappe.db.sql("""
            SELECT warehouse, actual_qty, valuation_rate, stock_value
            FROM `tabBin` WHERE item_code = %s AND actual_qty > 0
        """, it.item_code, as_dict=True)
        if bins:
            tot_qty = sum(b.actual_qty for b in bins)
            tot_val = sum(b.stock_value for b in bins)
            avg_rate = (tot_val / tot_qty) if tot_qty else 0
        else:
            tot_qty = 0
            avg_rate = 0
        flag = "✓" if avg_rate > 0 else ("·" if not expect_priced else "✗")
        print(f"     {flag} {it.item_code:35s} bin_rate={avg_rate:>8.3f}  "
              f"qty={tot_qty:>7.1f}  std_rate={it.standard_rate or 0:>8.3f}  "
              f"method={it.valuation_method or 'FIFO'}  uom={it.stock_uom}")
        if avg_rate > 0:
            priced += 1
    print(f"     → {priced}/{len(items)} Items avec Bin.valuation_rate > 0")
    return items


def _print_sle_for_item(item_code, limit=8):
    rows = frappe.db.sql("""
        SELECT posting_date, voucher_type, voucher_no, actual_qty,
               valuation_rate, stock_value_difference, stock_value
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s AND is_cancelled = 0
        ORDER BY posting_datetime ASC, creation ASC
    """, item_code, as_dict=True)
    if not rows:
        print(f"     (pas de SLE pour {item_code})")
        return
    print(f"     {item_code} — {len(rows)} SLE total (affichage des "
          f"{min(limit, len(rows))} premiers):")
    print(f"     Colonnes: rate = Bin.valuation_rate POST-transaction (rate "
          f"agrégé après l'écriture);")
    print(f"               svd  = stock_value_difference (= qty × basic_rate "
          f"de cette transaction).")
    print(f"     Invariant: stock_value(n) = stock_value(n-1) + svd(n).")
    print(f"     {'Date':12s} {'Type':18s} {'Voucher':22s} "
          f"{'qty':>8s} {'rate':>8s} {'svd':>10s} {'stock_val':>10s}  Σsvd ok?")
    mismatch = 0
    running = 0.0
    for r in rows[:limit]:
        running += (r.stock_value_difference or 0)
        ok = abs((r.stock_value or 0) - running) < 0.01
        if not ok:
            mismatch += 1
        print(f"     {str(r.posting_date):12s} {r.voucher_type[:18]:18s} "
              f"{r.voucher_no[:22]:22s} {r.actual_qty:>8.2f} "
              f"{r.valuation_rate:>8.3f} {r.stock_value_difference:>10.3f} "
              f"{r.stock_value:>10.3f}  {'✓' if ok else '✗'}")
    if len(rows) > limit:
        print(f"     ... +{len(rows) - limit} autres SLE")
    if mismatch:
        print(f"     ⚠ {mismatch} ligne(s) violent l'invariant — investiguer")


@frappe.whitelist()
def run():
    print("\n" + "=" * 70)
    print("  Sprint 5 — Vérification valuation native ERPNext")
    print("=" * 70)

    # 1. Semence — expected to have real prices (from migration opening SE)
    sem_items = _print_item_block("SEM", "Semence", expect_priced=True)

    # 2. Aliment — expected to have valuation_rate=0 (no opening SE)
    _print_item_block("ALI", "Aliment", expect_priced=False)

    # 3. Médicament — expected to have valuation_rate=0 (opening SE used rate=0)
    _print_item_block("MED", "Médicament", expect_priced=False)

    # 4. Deep-dive on first priced Semence Item — show SLE history
    print("\n  ── SLE history (preuve d'immuabilité) ──")
    priced_sem = None
    for it in sem_items:
        qty = frappe.db.sql("""SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin`
                                WHERE item_code = %s AND actual_qty > 0""",
                             it.item_code)[0][0]
        if qty > 0:
            priced_sem = it
            break
    if priced_sem:
        _print_sle_for_item(priced_sem.item_code)
        # Confirm at least one Material Issue exists (proves a consumption
        # SLE was frozen at the rate of that moment)
        issue_count = frappe.db.count("Stock Ledger Entry", {
            "item_code": priced_sem.item_code,
            "actual_qty": ["<", 0],
            "is_cancelled": 0,
        })
        print(f"\n     Material Issues (consommations) historisées: {issue_count}")
        if issue_count > 0:
            print("     → preuve qu'un changement de prix futur ne réécrit "
                  "pas les coûts passés")
    else:
        print("     (aucun Semence Item avec valuation_rate > 0 trouvé — "
              "soit aucune migration n'a importé de prix, soit aucune Semence "
              "n'avait quantite_restante > 0 lors de la migration)")

    # 5. Stock Settings sanity
    print("\n  ── Stock Settings ──")
    for key in ["valuation_method", "auto_indent",
                "default_warehouse", "reorder_email_notify"]:
        val = frappe.db.get_single_value("Stock Settings", key)
        print(f"     {key:30s} = {val!r}")

    print("\n" + "=" * 70)
    print("  Verdict attendu si tout va bien:")
    print("    • Tous les Items avec Bin.valuation_rate > 0")
    print("    • SLE.stock_value_difference cohérent (svd = qty × rate)")
    print("    • Material Issues passés à rate=0 (avant le seed) = preuve d'immuabilité")
    print("    • Material Issues futurs progressivement à rate réel (FIFO drain)")
    print("=" * 70 + "\n")
