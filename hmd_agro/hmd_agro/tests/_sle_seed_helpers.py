"""
Shared test helpers for the R2 fixture migration. The report tests previously
relied on `_aliment_data_per_lot` recomputing quantities from
ration × population on the fly. After R2, quantities come from Stock Ledger
Entry — so test fixtures must also post the SEs that the production
generator would have posted nightly.

These helpers do the minimum needed:
  - `migrate_test_aliments(prefix)` ensures every TEST-prefix Aliment has
    an ERPNext Item linked (via the existing _migrate_one_aliment).
  - `seed_test_distribution(lot, ration, start, end, n_pop)` posts one
    Material Issue per day for the given lot with `qty = qty_per_animal
    × n_pop` per aliment line. Mirrors `_build_stock_entry` from
    feed_distribution.py exactly so the SLE looks identical to production.
  - `clean_test_stock(prefix)` cancels every test-posted SE, deletes the
    SLE/Bin/Item rows so re-running tests is clean.

All helpers are idempotent. They never touch non-TEST-prefix data.
"""
import frappe
from frappe.utils import getdate, add_days

from hmd_agro.hmd_agro.setup.aliment_migration import _migrate_one_aliment
from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as WAREHOUSE


def migrate_test_aliments(prefix):
    """Ensure every Aliment with name LIKE `{prefix}%` has an Item linked.
    Idempotent — already-migrated Aliments are skipped."""
    for ali_name in frappe.db.sql_list(
        "SELECT name FROM `tabAliment` WHERE name LIKE %s", f"{prefix}%"
    ):
        ali = frappe.db.get_value("Aliment", ali_name,
            ["name", "nom_aliment", "type_aliment", "unite", "ms_pct", "item",
             "prix_unitaire"], as_dict=True)
        if ali:
            _migrate_one_aliment(ali, verbose=False)


def seed_test_distribution(lot, ration_name, start, end, n_pop,
                            remarks_prefix="RATION_DIST"):
    """Constant-population, constant-ration variant: posts one Material Issue
    per day in [start, end] for `lot` using `ration_name`'s composition × n_pop.
    Use for the simplest test scenarios (e.g. test_indicateurs_report)."""
    start = getdate(start)
    end = getdate(end)

    composition = frappe.db.sql("""
        SELECT c.aliment, c.quantite, a.item, a.ms_pct
        FROM `tabComposition Ration` c
        JOIN `tabAliment` a ON c.aliment = a.name
        WHERE c.parent = %s
    """, ration_name, as_dict=True)
    composition = [c for c in composition if c.item]

    posted = []
    day = start
    while day <= end:
        marker = f"{remarks_prefix}_{lot}_{day}"
        if frappe.db.exists("Stock Entry",
                            {"remarks": marker, "docstatus": 1}):
            day = add_days(day, 1)
            continue
        items = []
        for c in composition:
            qty = float(c.quantite or 0) * int(n_pop)
            if qty <= 0:
                continue
            items.append({
                "item_code": c.item, "qty": round(qty, 3),
                "uom": "Kg", "stock_uom": "Kg", "conversion_factor": 1,
                "s_warehouse": WAREHOUSE, "allow_zero_valuation_rate": 1,
            })
        if items:
            se = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Issue",
                "company": "hmd-agro",
                "posting_date": day, "posting_time": "00:00:00",
                "set_posting_time": 1, "id_lot": lot,
                "items": items, "remarks": marker,
            })
            se.insert(ignore_permissions=True)
            se.submit()
            posted.append(se.name)
        day = add_days(day, 1)

    frappe.db.commit()
    return posted


def seed_distribution_walk(lots, start, end):
    """Day-walking variant: for each day in [start, end] and each lot in
    `lots`, computes population from Animal + Allotement History and ration
    from Lot Ration History, then posts a Material Issue. Mirrors the
    SCRUM-123 generator exactly, but iterates only the supplied lots
    (avoids polluting unrelated production lots when running tests).

    Use this for fixtures with mid-period population changes or ration
    switches — populations_on_date and ration_on_date handle the
    historical reconstruction.
    """
    from hmd_agro.hmd_agro.utils.feed_distribution import (
        _prefetch_population_data, _populations_on_date,
        _composition_for_ration, _build_stock_entry,
    )
    from hmd_agro.hmd_agro.doctype.lot_ration_history.lot_ration_history import (
        ration_on_date,
    )

    start = getdate(start)
    end = getdate(end)
    prefetched = _prefetch_population_data(end)

    posted = []
    day = start
    while day <= end:
        pop = _populations_on_date(day, prefetched)
        for lot in lots:
            n = pop.get(lot, 0)
            if n == 0:
                continue
            if frappe.db.exists("Stock Entry", {
                "remarks": f"RATION_DIST_{lot}_{day}", "docstatus": 1,
            }):
                continue
            ration = ration_on_date(lot, day)
            if not ration:
                continue
            lines = []
            for c in _composition_for_ration(ration):
                qty = c["qty_per_animal"] * n
                if qty <= 0:
                    continue
                lines.append({"item_code": c["item_code"],
                              "qty": round(qty, 3),
                              "stock_uom": c["stock_uom"]})
            if lines:
                posted.append(_build_stock_entry(lot, day, lines))
        day = add_days(day, 1)

    frappe.db.commit()
    return posted


def clean_test_stock(prefix):
    """Cancel + delete every Stock Entry whose remarks reference a lot or
    aliment matching `{prefix}%`. Then delete the Items + Bin + SLE rows
    they touched so re-running tests is clean.

    Uses two passes:
      1. SEs tagged for test lots (remarks LIKE 'RATION_DIST_{prefix}%')
      2. SEs touching test Aliments via items table join
    """
    # ── Pass 1: SEs by remarks pattern ──
    se_names = frappe.db.sql_list("""
        SELECT name FROM `tabStock Entry`
        WHERE (remarks LIKE %s OR remarks LIKE %s)
    """, (f"RATION_DIST_{prefix}%", f"RATION_CORRECTION_{prefix}%"))

    # ── Pass 2: SEs touching test Items (in case any test created its own SEs) ──
    se_via_items = frappe.db.sql_list("""
        SELECT DISTINCT sed.parent FROM `tabStock Entry Detail` sed
        WHERE sed.item_code LIKE %s
    """, (f"ALI-{prefix}%",))

    all_se = set(se_names) | set(se_via_items)
    for name in all_se:
        ds = frappe.db.get_value("Stock Entry", name, "docstatus")
        if ds == 1:
            try:
                frappe.get_doc("Stock Entry", name).cancel()
            except Exception:
                pass
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", name)
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", name)

    # ── SLE rows that referenced these SEs ──
    frappe.db.sql("""
        DELETE FROM `tabStock Ledger Entry`
        WHERE item_code LIKE %s
    """, (f"ALI-{prefix}%",))

    # ── Bin rows for test items ──
    frappe.db.sql("""
        DELETE FROM `tabBin` WHERE item_code LIKE %s
    """, (f"ALI-{prefix}%",))

    # ── Item child tables, then Item ──
    test_items = frappe.db.sql_list(
        "SELECT name FROM `tabItem` WHERE item_code LIKE %s",
        (f"ALI-{prefix}%",),
    )
    for it in test_items:
        frappe.db.sql("DELETE FROM `tabItem Price` WHERE item_code=%s", it)
        frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent=%s", it)
        frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent=%s", it)
        frappe.db.sql("DELETE FROM `tabItem` WHERE name=%s", it)

    frappe.db.commit()
