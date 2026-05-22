"""Prove past report cost cells are immune to Aliment.prix_unitaire edits.

Steps:
  1. Run rapport_mensuel for 2026-05-01..2026-05-31 (a past period with data)
     → capture the per-aliment cost rows AND the grand-total cost row.
  2. Pick the Aliment linked to ALI-Mais and multiply its prix_unitaire ×10.
  3. Re-run the report with identical filters.
  4. Compare: every cost cell from run 1 must equal run 2 (within 0.001 DT).
  5. ALWAYS restore the original price (try/finally).

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.test_price_change_immunity.run
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _alimentation


CTX = {
    "date_debut": getdate("2026-05-01"),
    "date_filter": getdate("2026-05-13"),
    "date_fin": getdate("2026-05-31"),
    "nb_jours": 31,
    "mois": 5,
    "annee": 2026,
    "granularite": "Quotidien",
}


def _snapshot_costs(debug=False):
    """Run the alimentation section and capture every cost-bearing field on
    every row. Returns a dict keyed by (aliment_label, field_name) → value
    so the comparison can spot any cell that changes between runs.
    """
    columns, rows = _alimentation(CTX)
    if debug:
        col_names = [c.get("fieldname") for c in columns
                     if isinstance(c, dict)]
        print(f"  [debug] {len(rows)} rows, {len(col_names)} cols")
        print(f"  [debug] columns: {col_names}")
        for r in rows[:3]:
            print(f"  [debug] row sample: {r}")

    # Collect every numeric cost-like field across all rows.
    cost_keys = ("cout_periode", "cout_jour", "cout_mois", "cout_cumul",
                 "cout_semaine", "cout")
    snapshot = {}
    for r in rows:
        label = r.get("aliment") or r.get("indicateur") or "?"
        for k in r.keys():
            if any(k.startswith(ck) for ck in cost_keys):
                v = r.get(k)
                if v is not None:
                    snapshot[(label, k)] = round(float(v), 4)
    return snapshot


def run():
    print("\n" + "=" * 76)
    print("  Past-cost immunity test — Aliment.prix_unitaire ×10")
    print("=" * 76)

    # Find the Aliment linked to ALI-Mais (the doctype name has the accent;
    # the Item code does not).
    target_aliment = frappe.db.get_value("Aliment", {"item": "ALI-Mais"}, "name")
    if not target_aliment:
        print("  [skip] No Aliment linked to ALI-Mais — nothing to test")
        return

    original_prix = frappe.db.get_value("Aliment", target_aliment, "prix_unitaire")
    print(f"\n  Target Aliment:  {target_aliment}")
    print(f"  Current prix:    {original_prix} DT/kg")
    print(f"  Period:          {CTX['date_debut']} → {CTX['date_fin']}")

    failed = 0
    passed = 0

    try:
        print("\n  ── Run 1: capture cost cells at original price ──")
        before = _snapshot_costs(debug=True)
        print(f"  Cost cells captured: {len(before)}")
        for (label, field), val in sorted(before.items()):
            print(f"    {label:35s}  {field:20s}  {val:>12.4f}")

        new_prix = (original_prix or 0.70) * 10
        print(f"\n  ── Mutating prix_unitaire: {original_prix} → {new_prix} ──")
        frappe.db.set_value("Aliment", target_aliment, "prix_unitaire", new_prix)
        frappe.db.commit()
        readback = frappe.db.get_value("Aliment", target_aliment, "prix_unitaire")
        assert abs(readback - new_prix) < 0.001, "Price didn't actually change!"

        print("\n  ── Run 2: re-run report with identical filters ──")
        after = _snapshot_costs()
        print(f"  Cost cells captured: {len(after)}")

        # Diff every cell
        print("\n  ── Diff ──")
        all_keys = set(before) | set(after)
        for key in sorted(all_keys):
            b = before.get(key)
            a = after.get(key)
            if b is None or a is None:
                print(f"  ! {key}  {'APPEARED' if b is None else 'DISAPPEARED'}")
                failed += 1
                continue
            if abs(a - b) < 0.001:
                passed += 1
            else:
                print(f"  ! {str(key):60s}  {b:>10.4f} → {a:>10.4f}  Δ={a-b:+.4f}")
                failed += 1
        if passed and failed == 0:
            print(f"  All {passed} cells unchanged.")

    finally:
        # ALWAYS restore — even on assertion failure or exception
        print(f"\n  ── Restoring original price: {original_prix} ──")
        frappe.db.set_value("Aliment", target_aliment, "prix_unitaire", original_prix)
        frappe.db.commit()
        restored = frappe.db.get_value("Aliment", target_aliment, "prix_unitaire")
        print(f"  Readback after restore: {restored}")
        assert abs((restored or 0) - (original_prix or 0)) < 0.001, \
            "RESTORE FAILED — manual intervention needed!"

    print("\n" + "=" * 76)
    print(f"  RESULT: {passed} cost cells UNCHANGED, {failed} drifted")
    if failed == 0 and passed > 0:
        print("  PASS — past report cost cells are FULLY IMMUNE to prix_unitaire edits")
    elif passed == 0:
        print("  INCONCLUSIVE — no cost cells found in the report output")
    else:
        print("  FAIL — some cells changed; live-price leak somewhere in the path")
    print("=" * 76 + "\n")
    return {"passed": passed, "failed": failed}
