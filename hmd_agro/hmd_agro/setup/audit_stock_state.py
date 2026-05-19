"""
Sprint 5 — Stock state audit (read-only).

Inventory of what's currently in the system that touches the Stock module,
to surface duplicates, orphans, and misalignments before we proceed with
prix_unitaire / valuation seeding.

Run:
    docker exec frappe_docker_devcontainer-frappe-1 bash -lc \\
      "cd /workspace/development/frappe-bench && bench --site hmd.localhost execute \\
       hmd_agro.hmd_agro.setup.audit_stock_state.run"
"""
import frappe

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as WAREHOUSE


def _section(title):
    print("\n" + "─" * 70)
    print(f"  {title}")
    print("─" * 70)


@frappe.whitelist()
def run():
    print("\n" + "=" * 70)
    print("  STOCK STATE AUDIT — hmd-agro")
    print("=" * 70)

    # 1. Companies
    _section("1. Companies")
    for c in frappe.get_all("Company", fields=["name", "abbr", "default_currency", "country", "creation"]):
        marker = ""
        if c.name == "hmd-agro":
            marker = "  ← PRIMARY"
        elif c.name == "hmd-agro (Demo)":
            marker = "  ← DEMO (probably safe to delete)"
        elif c.name.startswith("_Test"):
            marker = "  ← ERPNext test-suite artifact"
        print(f"     {c.name:42s} abbr={c.abbr:5s} {c.default_currency} {c.country}{marker}")

    # 2. Warehouses for hmd-agro only
    _section("2. Warehouses (hmd-agro company)")
    whs = frappe.get_all(
        "Warehouse",
        filters={"company": "hmd-agro"},
        fields=["name", "is_group", "parent_warehouse", "creation", "owner"],
        order_by="creation asc",
    )
    for w in whs:
        marker = ""
        if w.name == WAREHOUSE:
            marker = "  ← OUR warehouse (created by stock_foundation.py)"
        elif w.is_group:
            marker = "  ← group (ERPNext default scaffold)"
        else:
            # qty in this warehouse?
            qty = frappe.db.sql("SELECT COALESCE(SUM(actual_qty),0) FROM `tabBin` WHERE warehouse = %s",
                                w.name)[0][0]
            marker = f"  ← ERPNext default scaffold (qty in Bin: {qty})"
        print(f"     {w.name:38s} {'group' if w.is_group else 'leaf '}  {marker}")

    # 3. Stock Settings
    _section("3. Stock Settings (defaults)")
    for key in ["valuation_method", "auto_indent", "default_warehouse",
                "stock_uom", "item_naming_by", "reorder_email_notify"]:
        val = frappe.db.get_single_value("Stock Settings", key)
        flag = ""
        if key == "default_warehouse" and val and "Magasin Principal" not in str(val):
            flag = "  ⚠ different from our Magasin Principal — see below"
        print(f"     {key:30s} = {val!r}{flag}")

    # 4. Items per code-prefix, by Item Group
    _section("4. Items by prefix")
    for prefix in ["MED-", "ALI-", "SEM-"]:
        items = frappe.get_all(
            "Item",
            filters={"item_code": ["like", f"{prefix}%"]},
            fields=["item_code", "item_group", "stock_uom", "has_batch_no",
                    "is_stock_item", "valuation_rate", "disabled"],
            order_by="item_code",
        )
        print(f"     {prefix} → {len(items)} Items")
        for it in items:
            flags = []
            if it.disabled:
                flags.append("DISABLED")
            if not it.is_stock_item:
                flags.append("non-stock")
            if it.has_batch_no:
                flags.append("batched")
            tag = (" [" + ",".join(flags) + "]") if flags else ""
            print(f"        {it.item_code:36s} grp={it.item_group:25s} uom={it.stock_uom:10s}{tag}")

    # 5. Item Default warehouses (per-Item override of Stock Settings.default_warehouse)
    _section("5. Item Defaults (item_defaults child table)")
    item_codes = frappe.get_all("Item",
        filters={"item_code": ["like", "%-%"]},
        or_filters=[["item_code", "like", "MED-%"], ["item_code", "like", "ALI-%"], ["item_code", "like", "SEM-%"]],
        pluck="name")
    if item_codes:
        defaults = frappe.db.sql("""
            SELECT parent, company, default_warehouse, default_supplier
            FROM `tabItem Default`
            WHERE parent IN %s
            ORDER BY parent
        """, (item_codes,), as_dict=True)
        if defaults:
            for d in defaults:
                print(f"     {d.parent:36s} company={d.company:25s} wh={d.default_warehouse!r}")
        else:
            print("     (aucun Item Default défini pour nos Items — ERPNext utilisera Stock Settings.default_warehouse)")
            print(f"     ⚠ ce dernier est 'Stores - HMD' actuellement, pas '{WAREHOUSE}'")
            print("       → impact: si quelqu'un crée un Stock Entry sans préciser de warehouse,")
            print("         il ira dans 'Stores - HMD', pas dans notre Magasin Principal.")
            print("       Notre code passe toujours warehouse explicitement → OK pour l'instant.")

    # 6. Item Groups (ours + duplicates ?)
    _section("6. Item Groups (HMD-relevant)")
    igs = frappe.get_all("Item Group",
        fields=["name", "parent_item_group", "is_group", "creation", "owner"],
        order_by="lft asc")
    parents_we_care = {"Médicament", "Aliment", "Semence"}
    for ig in igs:
        if ig.name in parents_we_care or ig.parent_item_group in parents_we_care:
            print(f"     {ig.name:30s} parent={ig.parent_item_group or '—':30s} group={ig.is_group}")

    # 7. UOMs (look for ours + duplicates)
    _section("7. UOMs (custom + frequently-used)")
    target_uoms = ["Dose", "Paillette", "Unit", "Kg", "Gram", "Nos", "Liter"]
    for u in target_uoms:
        exists = frappe.db.exists("UOM", u)
        if exists:
            mbwn = frappe.db.get_value("UOM", u, "must_be_whole_number")
            print(f"     {u:15s} ✓  must_be_whole_number={mbwn}")
        else:
            print(f"     {u:15s} ✗  (n'existe pas)")

    # 8. Stock Entries — where the stock actually lives
    _section("8. Stock Entries (toutes Companies confondues, par warehouse)")
    rows = frappe.db.sql("""
        SELECT
          COALESCE(NULLIF(sed.t_warehouse, ''), sed.s_warehouse) AS warehouse,
          se.stock_entry_type,
          COUNT(*) AS n_lines,
          SUM(ABS(sed.qty)) AS total_qty
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.docstatus = 1
          AND (sed.item_code LIKE 'MED-%' OR sed.item_code LIKE 'ALI-%' OR sed.item_code LIKE 'SEM-%')
        GROUP BY warehouse, se.stock_entry_type
        ORDER BY warehouse, se.stock_entry_type
    """, as_dict=True)
    if not rows:
        print("     (aucun Stock Entry pour nos Items)")
    for r in rows:
        flag = ""
        if r.warehouse and r.warehouse != WAREHOUSE:
            flag = "  ⚠ pas dans notre Magasin Principal !"
        print(f"     {(r.warehouse or '—'):35s} {r.stock_entry_type:18s} n={r.n_lines:>4d} qty={r.total_qty}{flag}")

    # 9. Bins — current stock state
    _section("9. Bins (stock courant pour nos Items)")
    bins = frappe.db.sql("""
        SELECT warehouse, item_code, actual_qty, valuation_rate
        FROM `tabBin`
        WHERE actual_qty != 0
          AND (item_code LIKE 'MED-%' OR item_code LIKE 'ALI-%' OR item_code LIKE 'SEM-%')
        ORDER BY warehouse, item_code
    """, as_dict=True)
    if not bins:
        print("     (aucun Bin avec actual_qty != 0 pour nos Items)")
    for b in bins:
        flag = ""
        if b.warehouse != WAREHOUSE:
            flag = "  ⚠ stock dans le mauvais warehouse"
        print(f"     {b.warehouse:35s} {b.item_code:30s} qty={b.actual_qty} val={b.valuation_rate}{flag}")

    # 10. Material Requests / Purchase Orders / Purchase Receipts touching our Items
    _section("10. Documents Buying liés à nos Items")
    for dt, fld in [("Material Request Item", "parent"),
                    ("Purchase Order Item", "parent"),
                    ("Purchase Receipt Item", "parent")]:
        rows = frappe.db.sql(f"""
            SELECT DISTINCT {fld}, item_code
            FROM `tab{dt}`
            WHERE item_code LIKE 'MED-%' OR item_code LIKE 'ALI-%' OR item_code LIKE 'SEM-%'
        """, as_dict=True)
        print(f"     {dt}: {len(rows)} ligne(s)")
        for r in rows[:5]:
            print(f"        {r.get(fld)} — {r.item_code}")
        if len(rows) > 5:
            print(f"        ... +{len(rows) - 5}")

    # 11. Item Reorder rows
    _section("11. Item Reorder (rows poussées par utils/reorder_sync.py)")
    reorders = frappe.db.sql("""
        SELECT parent, warehouse, warehouse_reorder_level, warehouse_reorder_qty, material_request_type
        FROM `tabItem Reorder`
        WHERE parent LIKE 'MED-%' OR parent LIKE 'ALI-%' OR parent LIKE 'SEM-%'
        ORDER BY parent
    """, as_dict=True)
    if not reorders:
        print("     (aucune ligne Item Reorder définie)")
    for r in reorders:
        flag = ""
        if r.warehouse != WAREHOUSE:
            flag = "  ⚠"
        print(f"     {r.parent:36s} wh={r.warehouse:30s} level={r.warehouse_reorder_level} qty={r.warehouse_reorder_qty} type={r.material_request_type}{flag}")

    # 12. Orphans / mismatches between HMD masters and Items
    _section("12. Cohérence HMD masters ↔ Items")
    for dt, prefix in [("Medicament", "MED-"), ("Aliment", "ALI-"), ("Semence", "SEM-")]:
        masters = frappe.get_all(dt, fields=["name", "item"], order_by="name")
        unlinked = [m.name for m in masters if not m.item]
        print(f"     {dt}: {len(masters)} masters, {len(unlinked)} sans `item` link")
        if unlinked:
            print(f"        manquent: {unlinked[:5]}{'...' if len(unlinked) > 5 else ''}")

    print("\n" + "=" * 70)
    print("  Fin de l'audit. Examine les ⚠ ci-dessus avant de continuer.")
    print("=" * 70 + "\n")
