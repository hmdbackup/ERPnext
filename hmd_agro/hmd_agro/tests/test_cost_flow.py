"""
ST5-09 / ST5-10 — end-to-end cost flow test.

Verifies the chain that gives the supervisor the price-history immutability
guarantee:

    Material Receipt at known basic_rate
    → SLE row written with stock_value_difference = qty × rate
    → Material Issue consumes the stock
    → SLE row written with negative stock_value_difference (cost of the issue)
    → _frais_consumption() aggregates over the date range, returns the cost
    → _frais_consumption_per_aliment() maps it back to the Aliment master

After this test passes, the cost columns in Rapport Mensuel's Indicateurs
section ("Frais Concentré" etc.) and Alimentation section ("Coût période")
are guaranteed to read the same frozen numbers — a future Aliment price
change can never rewrite them.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_cost_flow.run
"""
import frappe
import traceback
from frappe.utils import today

from hmd_agro.hmd_agro.utils.stock_utils import DEFAULT_WAREHOUSE as WAREHOUSE
from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
    _consumption_from_sle,
)


PREFIX = "TEST-COST-"


def _cleanup():
    test_aliment = f"{PREFIX}TESTFEED"
    test_item = f"ALI-{test_aliment}"
    test_lot = f"{PREFIX}LOT"
    frappe.db.sql("DELETE FROM `tabLot` WHERE name=%s", test_lot)
    # Stock Entries + SLE + Bin
    se_names = frappe.db.sql("""
        SELECT name FROM `tabStock Entry` WHERE remarks LIKE %s
    """, (f"%{PREFIX}%",))
    for (n,) in se_names:
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", n)
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", n)
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code=%s", test_item)
    frappe.db.sql("DELETE FROM `tabBin` WHERE item_code=%s", test_item)
    # Item child tables before Item
    frappe.db.sql("DELETE FROM `tabItem Price` WHERE item_code=%s", test_item)
    frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent=%s", test_item)
    frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent=%s", test_item)
    frappe.db.sql("DELETE FROM `tabItem` WHERE name=%s", test_item)
    frappe.db.sql("DELETE FROM `tabAliment` WHERE name=%s", test_aliment)
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  ST5-09/10 — End-to-end cost flow test")
    print("=" * 70)
    try:
        return _run_inner()
    except Exception:
        print("\n  ❌ Test crashed mid-flight:")
        print(traceback.format_exc())
        return {"pass": 0, "fail": 1}


def _run_inner():
    results = {"pass": 0, "fail": 0}

    _cleanup()

    # ── Setup: create a test Aliment (auto-creates Item via after_insert)
    ali_name = f"{PREFIX}TESTFEED"
    ali = frappe.get_doc({
        "doctype": "Aliment",
        "nom_aliment": ali_name,
        "type_aliment": "CONCENTRE",
        "unite": "KG",
        "prix_unitaire": 10.0,
        "ms_pct": 90,
    })
    ali.insert(ignore_permissions=True)
    frappe.db.commit()
    item_code = f"ALI-{ali_name}"
    _check(frappe.db.exists("Item", item_code),
        f"Item {item_code} auto-created by Aliment.after_insert", results)

    # ── Phase 1: Receipt at 10 TND/kg, 100 kg → SLE = +1000 TND value
    rcv = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Receipt",
        "company": "hmd-agro", "posting_date": today(),
        "items": [{
            "item_code": item_code, "qty": 100, "uom": "Kg",
            "stock_uom": "Kg", "conversion_factor": 1,
            "t_warehouse": WAREHOUSE, "basic_rate": 10.0,
        }],
        "remarks": f"{PREFIX}receipt",
    })
    rcv.insert(ignore_permissions=True)
    rcv.submit()
    frappe.db.commit()

    rcv_sle = frappe.db.get_value("Stock Ledger Entry",
        {"voucher_no": rcv.name, "is_cancelled": 0},
        ["actual_qty", "stock_value_difference", "valuation_rate"], as_dict=True)
    _check(rcv_sle and abs(rcv_sle.stock_value_difference - 1000.0) < 0.01,
        f"Receipt SLE: svd={rcv_sle.stock_value_difference if rcv_sle else None} "
        f"(expected 1000.00)", results)

    # ── Phase 2: Issue 30 kg via the production marker pattern
    # `_consumption_from_sle` filters on remarks LIKE 'RATION_DIST_%' AND a
    # non-null id_lot, so we mirror the SCRUM-123 generator's posting shape.
    test_lot = f"{PREFIX}LOT"
    lot_doc = frappe.get_doc({
        "doctype": "Lot", "nom": test_lot, "actif": 1,
    })
    lot_doc.name = test_lot
    lot_doc.db_insert()
    frappe.db.commit()
    iss = frappe.get_doc({
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Issue",
        "company": "hmd-agro", "posting_date": today(),
        "id_lot": test_lot,
        "items": [{
            "item_code": item_code, "qty": 30, "uom": "Kg",
            "stock_uom": "Kg", "conversion_factor": 1,
            "s_warehouse": WAREHOUSE,
        }],
        "remarks": f"RATION_DIST_{test_lot}_{today()}",
    })
    iss.insert(ignore_permissions=True)
    iss.submit()
    frappe.db.commit()

    iss_sle = frappe.db.get_value("Stock Ledger Entry",
        {"voucher_no": iss.name, "is_cancelled": 0},
        ["actual_qty", "stock_value_difference"], as_dict=True)
    _check(iss_sle and abs(iss_sle.stock_value_difference - (-300.0)) < 0.01,
        f"Issue SLE: svd={iss_sle.stock_value_difference if iss_sle else None} "
        f"(expected -300.00)", results)

    # ── Phase 3: _consumption_from_sle aggregates the cost
    d = _consumption_from_sle(today(), today())
    _check(abs(d["cumulative_aliment_cost"] - 300.0) < 0.01,
        f"cumulative_aliment_cost = {d['cumulative_aliment_cost']:.2f} "
        f"(expected 300.00 — our single test issue)", results)
    _check(abs(d["cumulative_concentre_cost"] - 300.0) < 0.01,
        f"cumulative_concentre_cost = {d['cumulative_concentre_cost']:.2f} "
        f"(expected 300.00 — Aliment is CONCENTRE)", results)
    _check(d["cumulative_fourrage_cost"] == 0,
        f"cumulative_fourrage_cost = {d['cumulative_fourrage_cost']:.2f} "
        f"(expected 0 — Aliment is not FOURRAGE)", results)

    # ── Phase 4: cumulative_cost_per_aliment maps Aliment master → cost
    _check(abs(d["cumulative_cost_per_aliment"].get(ali_name, 0) - 300.0) < 0.01,
        f"cumulative_cost_per_aliment[{ali_name}] = "
        f"{d['cumulative_cost_per_aliment'].get(ali_name, 0):.2f} "
        f"(expected 300.00)", results)

    # ── Phase 5: empty date range (no SLEs) → 0 (honest, not fabricated)
    d_empty = _consumption_from_sle("2020-01-01", "2020-01-02")
    _check(d_empty["cumulative_aliment_cost"] == 0,
        f"cumulative_aliment_cost on empty range = "
        f"{d_empty['cumulative_aliment_cost']} (expected 0)", results)
    _check(d_empty["cumulative_concentre_cost"] == 0,
        f"cumulative_concentre_cost on empty range = "
        f"{d_empty['cumulative_concentre_cost']} (expected 0)", results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
