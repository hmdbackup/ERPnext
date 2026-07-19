"""
FIN-S11 (RG-FIN-30 / CF-FIN-31) — valuation of stock movements at real CMP
through the single write path `stock_utils.create_stock_movement`.

Covers:
  1. Material Receipt with explicit basic_rate → Bin.valuation_rate = rate
  2. Material Issue WITHOUT any rate forced → SLE.stock_value_difference
     = -qty × CMP (ERPNext native moving-average valuation)
  3. Restoration Material Receipt without explicit rate → posts at current
     CMP (value-symmetric with the issue it compensates, not 0)
  4. Garde-fou CF-FIN-31: an item never purchased (CMP=0) still issues
     (legacy zero-valuation flags) — field entry is never blocked

Run: bench --site hmd.agro execute hmd_agro.hmd_agro.tests.test_valorisation_cmp.run
"""
import traceback

import frappe

from hmd_agro.hmd_agro.utils.stock_utils import (
    DEFAULT_WAREHOUSE as WAREHOUSE,
    create_stock_movement,
    ensure_item_allow_negative_stock,
    ensure_item_default,
    get_valuation_rate,
)

PREFIX = "TEST-CMP-"
ITEM_VAL = f"ALI-{PREFIX}VALUED"
ITEM_ZERO = f"ALI-{PREFIX}NEVERPRICED"


def _cleanup():
    for item_code in (ITEM_VAL, ITEM_ZERO):
        se_names = frappe.db.sql("""
            SELECT DISTINCT sed.parent FROM `tabStock Entry Detail` sed
            WHERE sed.item_code = %s
        """, item_code)
        for (n,) in se_names:
            frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", n)
            frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", n)
        frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code=%s", item_code)
        frappe.db.sql("DELETE FROM `tabBin` WHERE item_code=%s", item_code)
        frappe.db.sql("DELETE FROM `tabItem Default` WHERE parent=%s", item_code)
        frappe.db.sql("DELETE FROM `tabUOM Conversion Detail` WHERE parent=%s", item_code)
        frappe.db.sql("DELETE FROM `tabItem` WHERE name=%s", item_code)
    frappe.db.commit()


def _make_item(item_code):
    frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "item_group": "Aliment",
        "stock_uom": "Kg",
        "is_stock_item": 1,
    }).insert(ignore_permissions=True)
    ensure_item_default(item_code)
    ensure_item_allow_negative_stock(item_code)


def _svd(se_name):
    return float(frappe.db.get_value(
        "Stock Ledger Entry", {"voucher_no": se_name, "is_cancelled": 0},
        "stock_value_difference") or 0)


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  FIN-S11 — Valorisation CMP via create_stock_movement")
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
    _make_item(ITEM_VAL)
    _make_item(ITEM_ZERO)
    frappe.db.commit()

    # ── 1. Receipt 100 kg @ 12.5 → CMP = 12.5
    create_stock_movement(ITEM_VAL, 100, "Material Receipt", WAREHOUSE,
                          f"{PREFIX}achat", uom="Kg", basic_rate=12.5)
    frappe.db.commit()
    cmp_rate = get_valuation_rate(ITEM_VAL, WAREHOUSE)
    _check(abs(cmp_rate - 12.5) < 0.001,
           f"CMP après achat = {cmp_rate} (attendu 12.5)", results)

    # ── 2. Issue 40 kg sans taux forcé → svd = -500 (40 × 12.5)
    iss = create_stock_movement(ITEM_VAL, 40, "Material Issue", WAREHOUSE,
                                f"{PREFIX}conso", uom="Kg")
    frappe.db.commit()
    svd = _svd(iss)
    _check(abs(svd - (-500.0)) < 0.01,
           f"Issue valorisée au CMP : svd={svd} (attendu -500.00)", results)

    # ── 3. Restauration (receipt sans taux) → +CMP, symétrique de l'issue
    rst = create_stock_movement(ITEM_VAL, 40, "Material Receipt", WAREHOUSE,
                                f"{PREFIX}restauration", uom="Kg")
    frappe.db.commit()
    svd_rst = _svd(rst)
    _check(abs(svd_rst - 500.0) < 0.01,
           f"Restauration symétrique : svd={svd_rst} (attendu +500.00)", results)
    cmp_after = get_valuation_rate(ITEM_VAL, WAREHOUSE)
    _check(abs(cmp_after - 12.5) < 0.001,
           f"CMP inchangé après restauration = {cmp_after} (attendu 12.5)", results)

    # ── 4. Garde-fou CF-FIN-31 : item jamais acheté → issue passe, svd = 0
    try:
        iss0 = create_stock_movement(ITEM_ZERO, 5, "Material Issue", WAREHOUSE,
                                     f"{PREFIX}conso-zero", uom="Kg")
        frappe.db.commit()
        _check(True, "Issue sur item jamais valorisé : non bloquée (garde-fou)", results)
        svd0 = _svd(iss0)
        _check(abs(svd0) < 0.001,
               f"Issue à valorisation nulle : svd={svd0} (attendu 0)", results)
    except Exception as e:
        _check(False, f"Issue sur item jamais valorisé a levé {type(e).__name__}: {e}",
               results)

    # ── 5. Restauration d'un item jamais valorisé → passe aussi, svd = 0
    try:
        rst0 = create_stock_movement(ITEM_ZERO, 5, "Material Receipt", WAREHOUSE,
                                     f"{PREFIX}restauration-zero", uom="Kg")
        frappe.db.commit()
        svd_r0 = _svd(rst0)
        _check(abs(svd_r0) < 0.001,
               f"Restauration item non valorisé : svd={svd_r0} (attendu 0)", results)
    except Exception as e:
        _check(False, f"Restauration item non valorisé a levé {type(e).__name__}: {e}",
               results)

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass'] + results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
